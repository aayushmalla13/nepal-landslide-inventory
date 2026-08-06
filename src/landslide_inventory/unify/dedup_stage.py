"""Safe dedup clustering for Class 1 in-scope article events."""

from __future__ import annotations

import csv
import logging
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
from .similarity import (
    CasualtyVector,
    TfidfIndex,
    merge_rate_by_language_pair,
    structured_similarity,
)

LOGGER = logging.getLogger(__name__)


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
    # Added for cross-language dedup: all language-neutral, all previously
    # available in article_events but never read here (review section 8.2).
    missing: int | None
    injured: int | None
    trigger: str | None
    route_lang: str | None
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
    # IDF is computed over the eligible corpus so monsoon boilerplate ("rescue
    # teams", "police said", "district") is down-weighted rather than treated
    # as evidence of a match.
    tfidf = TfidfIndex(event.body_text for event in events)
    clusters, merge_rates = cluster_events(events, dedup_config, tfidf)
    cluster_ids, identity_collisions = assign_cluster_ids(clusters)
    persisted_at = utc_now_iso()

    for pair, counts in merge_rates.items():
        rate = counts['merged'] / counts['candidates'] if counts['candidates'] else 0.0
        LOGGER.info(
            'dedup merge rate %-7s %4d/%-6d (%.1f%%)',
            pair, counts['merged'], counts['candidates'], 100.0 * rate,
        )
    cross = merge_rates.get('en-np', {})
    if cross.get('candidates') and cross.get('merged', 0) == 0:
        # Review section 8.2: "If en-np merges stay near zero after the fix, the
        # fix did not work." Surfaced automatically rather than left to memory.
        LOGGER.warning(
            'No en-np merges across %d cross-language candidate pairs -- '
            'cross-language dedup is not working.', cross['candidates'],
        )

    if identity_collisions:
        # Two clusters claiming the same (district, date, municipality) are
        # usually one event that dedup failed to merge, so this doubles as an
        # under-merge metric rather than a mere id-uniqueness nuisance.
        LOGGER.warning(
            '%d clusters share a (district, date, municipality) identity with '
            'another cluster -- likely missed merges; ids disambiguated with a suffix',
            identity_collisions,
        )

    with connect_sqlite(config.sqlite_path) as connection:
        reset_dedup_outputs(connection)
        for index, cluster in enumerate(clusters):
            summary = build_cluster_summary(cluster, persisted_at, cluster_ids[index])
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
            canonical = build_canonical_event(cluster, persisted_at, cluster_ids[index])
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
                   e.ward, e.place_name_raw, e.deaths, e.missing, e.injured,
                   e.trigger, e.route_lang, e.class, e.in_nepal,
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
            missing=int(row['missing']) if row['missing'] is not None else None,
            injured=int(row['injured']) if row['injured'] is not None else None,
            trigger=row['trigger'],
            route_lang=row['route_lang'],
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


def structured_pair_similarity(left: EventRecord, right: EventRecord, tfidf: TfidfIndex | None):
    """Language-neutral score for one candidate pair. See unify/similarity.py."""

    return structured_similarity(
        left_municipality=left.municipality, right_municipality=right.municipality,
        left_ward=left.ward, right_ward=right.ward,
        left_casualties=CasualtyVector(left.deaths, left.missing, left.injured),
        right_casualties=CasualtyVector(right.deaths, right.missing, right.injured),
        left_trigger=left.trigger, right_trigger=right.trigger,
        left_place=left.place_name_raw, right_place=right.place_name_raw,
        left_text=left.body_text, right_text=right.body_text,
        left_lang=left.route_lang, right_lang=right.route_lang,
        tfidf=tfidf,
    )


def cluster_events(
    events: list[EventRecord],
    config: DedupConfig,
    tfidf: TfidfIndex | None = None,
) -> tuple[list[list[EventRecord]], dict[str, dict[str, int]]]:
    """Cluster candidate events using deterministic union-find.

    Two merge paths, unioned:

    1. The original string-similarity path (rapidfuzz over title/body). Kept
       as-is because its thresholds are tuned, even if tuned on the test set,
       and changing them would confound this fix with a retuning.

    2. The structured, language-neutral path added for review section 8.2.
       Devanagari and Latin share no tokens, so path 1 scores every
       cross-language pair at ~0 and they can never merge -- 1,031 of 1,112
       clusters were singletons. Path 2 compares gazetteer-normalised
       municipality, casualty vectors and transliterated place names instead,
       none of which depend on script.

    Fully replacing path 1 with TF-IDF cosine (review section 8.2) is deferred:
    it needs weights fitted on a dev set, and the locked test set is unlabelled.

    Also returns merge counts by language pair, which is the acceptance test:
    if en-np merges stay near zero, the fix did not work.
    """

    if not events:
        return [], {}

    parents = {event.url: event.url for event in events}
    grouped_by_district: dict[str, list[EventRecord]] = {}
    for event in events:
        grouped_by_district.setdefault(event.district, []).append(event)

    observed: list[tuple[str, str, bool]] = []
    for district in sorted(grouped_by_district):
        district_events = sorted(grouped_by_district[district], key=event_sort_key)
        for index, left in enumerate(district_events):
            for right in district_events[index + 1 :]:
                day_diff = abs((right.event_date - left.event_date).days)
                if day_diff > config.candidate_window_days:
                    break
                similarity = compute_similarity(left, right)
                merged = should_merge(left, right, similarity, config)
                # Path 2 applies ONLY to cross-language pairs. That restriction
                # is deliberate and worth stating: path 1 is *structurally*
                # blind across scripts -- Devanagari and Latin share no tokens,
                # so it scores every such pair at ~0 no matter how obviously
                # they match. Within a language it can see fine; whether it
                # sees *well* is a separate question that needs weights fitted
                # on a labelled dev set.
                #
                # Applying these unfitted weights to same-language pairs would
                # confound a structural fix with an untested retuning, and
                # would over-merge in ways nothing can currently measure. On
                # the existing test fixture it merges two Dhading reports with
                # identical dates and death counts that the tuned path keeps
                # apart -- plausibly correct, but "plausibly" is not a
                # standard this project can afford right now.
                if not merged and (left.route_lang or '?') != (right.route_lang or '?'):
                    structured = structured_pair_similarity(left, right, tfidf)
                    if structured.should_merge:
                        merged = True
                if merged:
                    union(parents, left.url, right.url)
                observed.append((left.route_lang or '?', right.route_lang or '?', merged))

    grouped: dict[str, list[EventRecord]] = {}
    for event in events:
        grouped.setdefault(find(parents, event.url), []).append(event)

    clusters = sorted(
        [sorted(cluster, key=event_sort_key) for cluster in grouped.values()],
        key=lambda cluster: event_sort_key(cluster[0]),
    )
    return clusters, merge_rate_by_language_pair(observed)


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


def build_cluster_summary(cluster: list[EventRecord], inserted_at: str, cluster_id: str | None = None) -> dict[str, Any]:
    """Build one cluster_summary row."""

    urls = sorted(event.url for event in cluster)
    sources = sorted({event.source for event in cluster})
    dates = sorted(event.event_date_ad for event in cluster)
    return {
        # Must use the caller-assigned id when given: build_cluster_id alone is
        # not unique (see assign_cluster_ids), and cluster_summary.cluster_id
        # carries a UNIQUE constraint.
        'cluster_id': cluster_id or build_cluster_id(cluster),
        'district': cluster[0].district,
        'date_min': dates[0],
        'date_max': dates[-1],
        'size': len(cluster),
        'sources': json.dumps(sources, ensure_ascii=False, sort_keys=True),
        'urls': json.dumps(urls, ensure_ascii=False, sort_keys=True),
        'inserted_at': inserted_at,
    }


def build_canonical_event(cluster: list[EventRecord], inserted_at: str, cluster_id: str | None = None) -> dict[str, Any]:
    """Build one canonical_events row from a cluster."""

    representative = choose_representative(cluster)
    cluster_id = cluster_id or build_cluster_id(cluster)
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
    """Return a content-stable cluster identifier.

    Hashes the event's *identity* -- district, canonical date, municipality --
    not its member URL set (review section 8.2).

    Why this matters: hashing the URL set means every ``cluster_id``, and
    therefore every ``event_id``, changes whenever coverage changes. Add a
    source, re-fetch a failed article, or merge one extra duplicate, and the
    identifiers of *unrelated* events churn. That breaks any longitudinal audit
    and makes a DOI'd dataset version impossible to reconcile with the next one
    -- a reader cannot ask "is event X still in the v2 inventory?".

    Under this scheme, an event keeps its identity as long as it happened in
    the same place on the same day, which is what identity should mean here.
    Adding the ekantipur report of a landslide already covered by setopati now
    grows the cluster instead of renaming the event.

    Collision note: two clusters sharing (district, date, municipality) produce
    the same identity. Measured on the current inventory that is 82 identities
    covering 176 clusters -- far from rare.

    Inspecting them turned out to be informative rather than merely annoying:
    almost every collision is a *missed merge*. Baglung 2024-08-06, Badigad
    Rural Municipality appears twice with tolls of 6 and 7; Arghakhanchi
    2021-08-31 appears twice, once with a casualty count and once without. So
    the collision count doubles as an under-merge metric -- see
    ``assign_cluster_ids``, which reports it.

    Collisions are disambiguated with a deterministic suffix so the identifier
    stays unique. Identifiers for non-colliding clusters -- the large majority --
    remain content-stable across coverage changes, which is the point.
    """

    canonical_date = min(event.event_date_ad for event in cluster)
    districts = sorted({event.district for event in cluster})
    municipalities = sorted({event.municipality for event in cluster if event.municipality})
    identity = (
        districts[0] if districts else '',
        canonical_date,
        municipalities[0] if municipalities else '',
    )
    return f"cluster_{stable_hash('dedup_v2', identity)[:16]}"


def assign_cluster_ids(clusters: list[list[EventRecord]]) -> tuple[dict[int, str], int]:
    """Map each cluster index to a unique id, disambiguating collisions.

    Returns the mapping and the number of colliding identities. That count is a
    useful diagnostic in its own right: two clusters claiming the same
    (district, date, municipality) are usually the same event that dedup failed
    to merge, so a rising collision count means under-merging.

    Disambiguation is by position in a deterministic ordering (earliest member
    URL), so a given run always produces the same ids.
    """

    seen: dict[str, int] = {}
    assignments: dict[int, str] = {}
    collisions = 0
    ordered = sorted(
        range(len(clusters)),
        key=lambda index: min(event.url for event in clusters[index]),
    )
    for index in ordered:
        base = build_cluster_id(clusters[index])
        occurrence = seen.get(base, 0)
        seen[base] = occurrence + 1
        if occurrence == 0:
            assignments[index] = base
        else:
            collisions += 1
            assignments[index] = f'{base}_{occurrence}'
    return assignments, collisions


def export_cluster_summary_csv(path: Path, clusters: list[list[EventRecord]], inserted_at: str) -> None:
    """Export cluster summary rows to CSV."""

    ensure_directory(path.parent)
    ids, _ = assign_cluster_ids(clusters)
    rows = [build_cluster_summary(c, inserted_at, ids[i]) for i, c in enumerate(clusters)]
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
    ids, _ = assign_cluster_ids(clusters)
    rows = [build_canonical_event(c, inserted_at, ids[i]) for i, c in enumerate(clusters)]
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
