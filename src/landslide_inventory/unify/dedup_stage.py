"""Safe dedup clustering for Class 1 in-scope article events."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
import json
from pathlib import Path
import sqlite3
from typing import Any

from rapidfuzz import fuzz

from ..config import AppConfig
from ..db import connect_sqlite, initialize_sqlite
from ..gazetteer import district_to_province
from ..utils import ensure_directory, stable_hash, utc_now_iso


@dataclass(frozen=True)
class DedupConfig:
    """Thresholds controlling safe event clustering."""

    candidate_window_days: int
    primary_window_days: int
    headline_sim_threshold: float
    body_sim_threshold: float
    high_body_sim_threshold: float
    guard_deaths_delta: int
    prefer_same_municipality: bool


@dataclass(frozen=True)
class EventRecord:
    """One in-scope Class 1 article event eligible for dedup."""

    url: str
    source: str
    title: str | None
    body_text: str
    event_date_ad: str
    district: str
    province: str | None
    municipality: str | None
    ward: str | None
    place_name_raw: str | None
    deaths: int | None
    event_class: int
    in_nepal: int
    conf_class: float
    conf_date: float
    conf_district: float
    conf_place: float
    conf_fatalities: float
    conf_trigger: float

    @property
    def event_date(self) -> date:
        """Return the parsed event date."""

        return date.fromisoformat(self.event_date_ad)

    @property
    def confidence_score(self) -> float:
        """Return a deterministic aggregate confidence score."""

        return (
            self.conf_class
            + self.conf_date
            + self.conf_district
            + self.conf_place
            + self.conf_fatalities
            + self.conf_trigger
        )


@dataclass(frozen=True)
class PairSimilarity:
    """Similarity metrics for one candidate pair."""

    headline_sim: float
    body_sim: float
    day_diff: int


def build_dedup_config(config: AppConfig) -> DedupConfig:
    """Read dedup thresholds from config."""

    values = dict(config.raw['dedup'])
    return DedupConfig(
        candidate_window_days=int(values['candidate_window_days']),
        primary_window_days=int(values['primary_window_days']),
        headline_sim_threshold=float(values['headline_sim_threshold']),
        body_sim_threshold=float(values['body_sim_threshold']),
        high_body_sim_threshold=float(values['high_body_sim_threshold']),
        guard_deaths_delta=int(values['guard_deaths_delta']),
        prefer_same_municipality=bool(values.get('prefer_same_municipality', True)),
    )


def run_dedup_stage(config: AppConfig) -> int:
    """Cluster in-scope Class 1 article events into canonical events."""

    initialize_sqlite(config.sqlite_path)
    dedup_config = build_dedup_config(config)
    events = load_dedup_events(config.sqlite_path)
    clusters = cluster_events(events, dedup_config)
    persisted_at = utc_now_iso()

    with connect_sqlite(config.sqlite_path) as connection:
        reset_dedup_outputs(connection)
        for cluster in clusters:
            summary = build_cluster_summary(cluster, persisted_at)
            connection.execute(
                """
                INSERT INTO cluster_summary (
                    cluster_id, district, date_min, date_max, size, sources, urls, inserted_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    summary['cluster_id'],
                    summary['district'],
                    summary['date_min'],
                    summary['date_max'],
                    summary['size'],
                    summary['sources'],
                    summary['urls'],
                    summary['inserted_at'],
                ),
            )
            canonical = build_canonical_event(cluster, persisted_at)
            connection.execute(
                """
                INSERT INTO canonical_events (
                    event_id, dedup_cluster_id, event_date_ad, district, province,
                    municipality, municipality_candidates_json, ward_candidates_json,
                    place_name_candidates_json, event_payload, inserted_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(event_id) DO UPDATE SET
                    dedup_cluster_id = excluded.dedup_cluster_id,
                    event_date_ad = excluded.event_date_ad,
                    district = excluded.district,
                    province = excluded.province,
                    municipality = excluded.municipality,
                    municipality_candidates_json = excluded.municipality_candidates_json,
                    ward_candidates_json = excluded.ward_candidates_json,
                    place_name_candidates_json = excluded.place_name_candidates_json,
                    event_payload = excluded.event_payload,
                    inserted_at = excluded.inserted_at
                """,
                (
                    canonical['event_id'],
                    canonical['dedup_cluster_id'],
                    canonical['event_date_ad'],
                    canonical['district'],
                    canonical['province'],
                    canonical['municipality'],
                    canonical['municipality_candidates_json'],
                    canonical['ward_candidates_json'],
                    canonical['place_name_candidates_json'],
                    canonical['event_payload'],
                    canonical['inserted_at'],
                ),
            )
            for event in cluster:
                connection.execute(
                    'UPDATE article_events SET dedup_cluster_id = ? WHERE url = ?',
                    (summary['cluster_id'], event.url),
                )
        connection.commit()

    export_cluster_summary_csv(config.resolve_path('outputs_dir') / 'cluster_summary.csv', clusters, persisted_at)
    export_canonical_events_csv(config.resolve_path('outputs_dir') / 'canonical_events.csv', clusters, persisted_at)
    return len(clusters)


def load_dedup_events(database_path: Path) -> list[EventRecord]:
    """Load only Class 1, in-scope article events eligible for dedup."""

    with connect_sqlite(database_path) as connection:
        rows = connection.execute(
            """
            SELECT e.url, e.source, e.title, COALESCE(r.text, '') AS body_text,
                   e.event_date_ad, e.district, e.province, e.municipality,
                   e.ward, e.place_name_raw, e.deaths, e.class, e.in_nepal,
                   COALESCE(e.conf_class, 0.0) AS conf_class,
                   COALESCE(e.conf_date, 0.0) AS conf_date,
                   COALESCE(e.conf_district, 0.0) AS conf_district,
                   COALESCE(e.conf_place, 0.0) AS conf_place,
                   COALESCE(e.conf_fatalities, 0.0) AS conf_fatalities,
                   COALESCE(e.conf_trigger, 0.0) AS conf_trigger
            FROM article_events e
            LEFT JOIN raw_articles r ON r.url = e.url
            WHERE e.class = 1
              AND COALESCE(e.in_nepal, 0) = 1
              AND e.event_date_ad IS NOT NULL
              AND e.district IS NOT NULL
            ORDER BY e.district ASC, e.event_date_ad ASC, COALESCE(e.municipality, '') ASC, e.url ASC
            """
        ).fetchall()

    return [
        EventRecord(
            url=str(row['url']),
            source=str(row['source']),
            title=row['title'],
            body_text=str(row['body_text'] or ''),
            event_date_ad=str(row['event_date_ad']),
            district=str(row['district']),
            province=row['province'],
            municipality=row['municipality'],
            ward=row['ward'],
            place_name_raw=row['place_name_raw'],
            deaths=int(row['deaths']) if row['deaths'] is not None else None,
            event_class=int(row['class']),
            in_nepal=int(row['in_nepal']),
            conf_class=float(row['conf_class']),
            conf_date=float(row['conf_date']),
            conf_district=float(row['conf_district']),
            conf_place=float(row['conf_place']),
            conf_fatalities=float(row['conf_fatalities']),
            conf_trigger=float(row['conf_trigger']),
        )
        for row in rows
    ]


def cluster_events(events: list[EventRecord], config: DedupConfig) -> list[list[EventRecord]]:
    """Cluster candidate events using deterministic union-find."""

    if not events:
        return []

    parents = {event.url: event.url for event in events}
    grouped_by_district: dict[str, list[EventRecord]] = {}
    for event in events:
        grouped_by_district.setdefault(event.district, []).append(event)

    for district in sorted(grouped_by_district):
        district_events = sorted(grouped_by_district[district], key=event_sort_key)
        for index, left in enumerate(district_events):
            for right in district_events[index + 1 :]:
                day_diff = abs((right.event_date - left.event_date).days)
                if day_diff > config.candidate_window_days:
                    break
                similarity = compute_similarity(left, right)
                if should_merge(left, right, similarity, config):
                    union(parents, left.url, right.url)

    grouped: dict[str, list[EventRecord]] = {}
    for event in events:
        grouped.setdefault(find(parents, event.url), []).append(event)

    return sorted(
        [sorted(cluster, key=event_sort_key) for cluster in grouped.values()],
        key=lambda cluster: event_sort_key(cluster[0]),
    )


def compute_similarity(left: EventRecord, right: EventRecord) -> PairSimilarity:
    """Compute normalized title/body similarity for one candidate pair."""

    headline_sim = fuzz.token_set_ratio(left.title or '', right.title or '') / 100.0
    body_sim = 0.0
    if left.body_text and right.body_text:
        body_sim = fuzz.token_set_ratio(left.body_text[:2000], right.body_text[:2000]) / 100.0
    return PairSimilarity(
        headline_sim=headline_sim,
        body_sim=body_sim,
        day_diff=abs((right.event_date - left.event_date).days),
    )


def should_merge(left: EventRecord, right: EventRecord, similarity: PairSimilarity, config: DedupConfig) -> bool:
    """Return whether two candidate rows should be clustered together."""

    headline_threshold = config.headline_sim_threshold
    body_threshold = config.body_sim_threshold
    if similarity.day_diff > config.primary_window_days:
        headline_threshold = min(0.99, headline_threshold + 0.05)
        body_threshold = min(0.99, body_threshold + 0.04)

    if left.municipality and right.municipality and left.municipality != right.municipality:
        if similarity.headline_sim < 0.92 and similarity.body_sim < config.high_body_sim_threshold:
            return False

    if bool(left.municipality) != bool(right.municipality):
        stricter_headline = max(0.90, headline_threshold + 0.06)
        if similarity.headline_sim < stricter_headline and similarity.body_sim < config.high_body_sim_threshold:
            return False

    similarity_ok = (
        similarity.headline_sim >= headline_threshold
        or similarity.body_sim >= body_threshold
    )
    if not similarity_ok:
        return False

    municipality_guard = True
    if config.prefer_same_municipality and left.municipality and right.municipality:
        municipality_guard = left.municipality == right.municipality
    deaths_guard = deaths_within_delta(left.deaths, right.deaths, config.guard_deaths_delta)
    body_guard = similarity.body_sim >= config.high_body_sim_threshold
    return municipality_guard or deaths_guard or body_guard


def deaths_within_delta(left: int | None, right: int | None, delta: int) -> bool:
    """Return whether both death counts are present and close enough."""

    if left is None or right is None:
        return False
    return abs(left - right) <= delta


def build_cluster_summary(cluster: list[EventRecord], inserted_at: str) -> dict[str, Any]:
    """Build one cluster_summary row."""

    urls = sorted(event.url for event in cluster)
    sources = sorted({event.source for event in cluster})
    dates = sorted(event.event_date_ad for event in cluster)
    return {
        'cluster_id': build_cluster_id(cluster),
        'district': cluster[0].district,
        'date_min': dates[0],
        'date_max': dates[-1],
        'size': len(cluster),
        'sources': json.dumps(sources, ensure_ascii=False, sort_keys=True),
        'urls': json.dumps(urls, ensure_ascii=False, sort_keys=True),
        'inserted_at': inserted_at,
    }


def build_canonical_event(cluster: list[EventRecord], inserted_at: str) -> dict[str, Any]:
    """Build one canonical_events row from a cluster."""

    representative = choose_representative(cluster)
    cluster_id = build_cluster_id(cluster)
    municipalities = sorted({event.municipality for event in cluster if event.municipality})
    wards = sorted({event.ward for event in cluster if event.ward})
    place_names = sorted({event.place_name_raw for event in cluster if event.place_name_raw})
    payload = {
        'urls': sorted(event.url for event in cluster),
        'sources': sorted({event.source for event in cluster}),
        'size': len(cluster),
        'representative_url': representative.url,
        'municipality_candidates': municipalities,
        'ward_candidates': wards,
        'place_name_candidates': place_names,
    }
    return {
        'event_id': f"event_{stable_hash('canonical', cluster_id)[:16]}",
        'dedup_cluster_id': cluster_id,
        'event_date_ad': representative.event_date_ad,
        'district': representative.district,
        'province': representative.province or district_to_province(representative.district),
        'municipality': representative.municipality,
        'municipality_candidates_json': json.dumps(municipalities, ensure_ascii=False, sort_keys=True),
        'ward_candidates_json': json.dumps(wards, ensure_ascii=False, sort_keys=True),
        'place_name_candidates_json': json.dumps(place_names, ensure_ascii=False, sort_keys=True),
        'event_payload': json.dumps(payload, ensure_ascii=False, sort_keys=True),
        'inserted_at': inserted_at,
    }


def choose_representative(cluster: list[EventRecord]) -> EventRecord:
    """Choose a deterministic representative article for a cluster."""

    return sorted(
        cluster,
        key=lambda event: (
            -event.confidence_score,
            event.event_date_ad,
            event.municipality or '',
            event.url,
        ),
    )[0]


def build_cluster_id(cluster: list[EventRecord]) -> str:
    """Return a deterministic cluster identifier."""

    urls = sorted(event.url for event in cluster)
    return f"cluster_{stable_hash('dedup', urls)[:16]}"


def export_cluster_summary_csv(path: Path, clusters: list[list[EventRecord]], inserted_at: str) -> None:
    """Export cluster summary rows to CSV."""

    ensure_directory(path.parent)
    rows = [build_cluster_summary(cluster, inserted_at) for cluster in clusters]
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=['cluster_id', 'district', 'date_min', 'date_max', 'size', 'sources', 'urls', 'inserted_at'],
        )
        writer.writeheader()
        for row in sorted(rows, key=lambda item: item['cluster_id']):
            writer.writerow(row)


def export_canonical_events_csv(path: Path, clusters: list[list[EventRecord]], inserted_at: str) -> None:
    """Export canonical event rows to CSV."""

    ensure_directory(path.parent)
    rows = [build_canonical_event(cluster, inserted_at) for cluster in clusters]
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                'event_id', 'dedup_cluster_id', 'event_date_ad', 'district', 'province', 'municipality',
                'municipality_candidates_json', 'ward_candidates_json', 'place_name_candidates_json',
                'event_payload', 'inserted_at',
            ],
        )
        writer.writeheader()
        for row in sorted(rows, key=lambda item: item['event_id']):
            writer.writerow(row)


def reset_dedup_outputs(connection: sqlite3.Connection) -> None:
    """Clear prior dedup outputs before rebuilding them deterministically."""

    connection.execute('UPDATE article_events SET dedup_cluster_id = NULL')
    connection.execute('DELETE FROM cluster_summary')
    connection.execute('DELETE FROM canonical_events')


def find(parents: dict[str, str], item: str) -> str:
    """Find a union-find root with path compression."""

    root = parents[item]
    if root != item:
        root = find(parents, root)
        parents[item] = root
    return root


def union(parents: dict[str, str], left: str, right: str) -> None:
    """Union two union-find sets deterministically."""

    left_root = find(parents, left)
    right_root = find(parents, right)
    if left_root == right_root:
        return
    parent, child = sorted((left_root, right_root))
    parents[child] = parent


def event_sort_key(event: EventRecord) -> tuple[str, str, str, str]:
    """Return a stable sort key for event records."""

    return (event.district, event.event_date_ad, event.municipality or '', event.url)
