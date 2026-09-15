"""Explicit comparison of external observations with canonical news events."""

from __future__ import annotations

import csv
import json
import logging
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from ..bipad.agreement import (
    InventoryEvent,
    Match,
    collapse_to_incidents,
    full_agreement_report,
    match_inventories,
)
from ..config import AppConfig
from ..db import connect_sqlite, initialize_sqlite
from ..gazetteer import normalize_district
from ..gazetteer_municipality import municipality_to_district, normalize_municipality
from ..utils import ensure_directory, stable_hash, utc_now_iso

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class EventDetail:
    title: str | None = None
    url: str | None = None
    missing: int | None = None
    injured: int | None = None
    raw_json: str | None = None


def _integer(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _municipality(value: Any, district: str) -> str | None:
    """Normalize suffixed news names and bare BIPAD names district-safely."""

    if value is None or not str(value).strip():
        return None
    raw = str(value).strip()
    candidates = [raw]
    candidates.extend(
        f"{raw} {suffix}"
        for suffix in (
            "Municipality",
            "Rural Municipality",
            "Metropolitan City",
            "Sub-metropolitan City",
        )
    )
    for candidate in candidates:
        normalized = normalize_municipality(candidate, "en")
        if normalized and municipality_to_district(normalized) == district:
            return normalized
    return raw


def load_external_bipad(
    database_path: Path,
    study_start: date,
    study_end: date,
) -> tuple[list[InventoryEvent], dict[str, EventDetail]]:
    """Load normalized BIPAD observations directly from the external table."""

    with connect_sqlite(database_path) as connection:
        rows = connection.execute(
            """
            SELECT source_record_id, incident_date_ad, district, municipality,
                   deaths, missing, injured, title, source_url, raw_json
            FROM external_records
            WHERE source = 'bipad'
              AND incident_date_ad BETWEEN ? AND ?
            ORDER BY incident_date_ad, district, municipality, source_record_id
            """,
            (study_start.isoformat(), study_end.isoformat()),
        ).fetchall()
    events: list[InventoryEvent] = []
    details: dict[str, EventDetail] = {}
    for row in rows:
        event_id = str(row["source_record_id"])
        raw_district = str(row["district"])
        district = normalize_district(raw_district, "en") or raw_district
        events.append(
            InventoryEvent(
                event_id=event_id,
                district=district,
                event_date=date.fromisoformat(str(row["incident_date_ad"])),
                municipality=_municipality(row["municipality"], district),
                deaths=_integer(row["deaths"]),
                source="bipad",
            )
        )
        details[event_id] = EventDetail(
            title=row["title"],
            url=row["source_url"],
            missing=_integer(row["missing"]),
            injured=_integer(row["injured"]),
            raw_json=row["raw_json"],
        )
    return events, details


def load_canonical_news(
    database_path: Path,
    study_start: date,
    comparison_end: date,
) -> tuple[list[InventoryEvent], dict[str, EventDetail]]:
    """Load canonical news events over the common BIPAD observation window."""

    with connect_sqlite(database_path) as connection:
        rows = connection.execute(
            """
            SELECT c.event_id, c.event_date_ad, c.district, c.municipality,
                   e.deaths, e.missing, e.injured, e.title,
                   json_extract(c.event_payload, '$.representative_url') AS url
            FROM canonical_events c
            LEFT JOIN article_events e
              ON e.url = json_extract(c.event_payload, '$.representative_url')
            WHERE c.event_date_ad BETWEEN ? AND ?
              AND c.district IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1
                  FROM json_each(c.event_payload, '$.urls') AS member
                  JOIN raw_articles assisted ON assisted.url = member.value
                  WHERE assisted.method LIKE 'external_seed_bipad%'
              )
            ORDER BY c.event_date_ad, c.district, c.event_id
            """,
            (study_start.isoformat(), comparison_end.isoformat()),
        ).fetchall()
    events: list[InventoryEvent] = []
    details: dict[str, EventDetail] = {}
    for row in rows:
        event_id = str(row["event_id"])
        raw_district = str(row["district"])
        district = normalize_district(raw_district, "en") or raw_district
        events.append(
            InventoryEvent(
                event_id=event_id,
                district=district,
                event_date=date.fromisoformat(str(row["event_date_ad"])),
                municipality=_municipality(row["municipality"], district),
                deaths=_integer(row["deaths"]),
                source="news",
            )
        )
        details[event_id] = EventDetail(
            title=row["title"],
            url=row["url"],
            missing=_integer(row["missing"]),
            injured=_integer(row["injured"]),
        )
    return events, details


def _write_csv(path: Path, fieldnames: list[str], rows: Iterable[dict[str, Any]]) -> int:
    materialized = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(materialized)
    return len(materialized)


def write_match_candidates(
    path: Path,
    matches: list[Match],
    news_by_id: dict[str, InventoryEvent],
    bipad_by_id: dict[str, InventoryEvent],
    news_details: dict[str, EventDetail],
    bipad_details: dict[str, EventDetail],
) -> int:
    rows: list[dict[str, Any]] = []
    for match in sorted(matches, key=lambda item: (item.tier, item.day_gap, item.news_id)):
        news = news_by_id[match.news_id]
        bipad = bipad_by_id[match.bipad_id]
        news_detail = news_details.get(news.event_id, EventDetail())
        member_ids = bipad.member_ids or (bipad.event_id,)
        representative = bipad_details.get(member_ids[0], EventDetail())
        rows.append(
            {
                "tier": match.tier,
                "day_gap": match.day_gap,
                "death_gap": "" if match.death_gap is None else match.death_gap,
                "news_event_id": news.event_id,
                "news_date": news.event_date.isoformat(),
                "news_district": news.district,
                "news_municipality": news.municipality or "",
                "news_deaths": "" if news.deaths is None else news.deaths,
                "news_title": news_detail.title or "",
                "news_url": news_detail.url or "",
                "bipad_cluster_id": bipad.event_id,
                "bipad_member_count": len(member_ids),
                "bipad_member_ids": "|".join(member_ids),
                "bipad_date": bipad.event_date.isoformat(),
                "bipad_district": bipad.district,
                "bipad_municipality": bipad.municipality or "",
                "bipad_deaths": "" if bipad.deaths is None else bipad.deaths,
                "bipad_title": representative.title or "",
            }
        )
    return _write_csv(path, list(rows[0]) if rows else _match_fields(), rows)


def _match_fields() -> list[str]:
    return [
        "tier",
        "day_gap",
        "death_gap",
        "news_event_id",
        "news_date",
        "news_district",
        "news_municipality",
        "news_deaths",
        "news_title",
        "news_url",
        "bipad_cluster_id",
        "bipad_member_count",
        "bipad_member_ids",
        "bipad_date",
        "bipad_district",
        "bipad_municipality",
        "bipad_deaths",
        "bipad_title",
    ]


def write_search_seeds(
    path: Path,
    bipad: list[InventoryEvent],
    matches: list[Match],
    details: dict[str, EventDetail],
) -> tuple[int, dict[str, int]]:
    """Write BIPAD gaps using strict A/B matches; Tier C remains a weak lead."""

    tiers_by_bipad: dict[str, set[str]] = {}
    for match in matches:
        tiers_by_bipad.setdefault(match.bipad_id, set()).add(match.tier)
    rows: list[dict[str, Any]] = []
    status_counts = {"strong_match": 0, "weak_candidate": 0, "unmatched": 0}
    for event in bipad:
        tiers = tiers_by_bipad.get(event.event_id, set())
        if tiers & {"A", "B"}:
            status_counts["strong_match"] += 1
            continue
        status = "weak_candidate" if "C" in tiers else "unmatched"
        status_counts[status] += 1
        member_ids = event.member_ids or (event.event_id,)
        detail = details.get(member_ids[0], EventDetail())
        start = event.event_date - timedelta(days=3)
        end = event.event_date + timedelta(days=3)
        place = " ".join(filter(None, (event.district, event.municipality)))
        priority = "high" if (event.deaths or 0) > 0 else "standard"
        date_filter = f"after:{start.isoformat()} before:{end.isoformat()}"
        rows.append(
            {
                "match_status": status,
                "priority": priority,
                "bipad_cluster_id": event.event_id,
                "bipad_member_count": len(member_ids),
                "bipad_member_ids": "|".join(member_ids),
                "event_date": event.event_date.isoformat(),
                "search_date_from": start.isoformat(),
                "search_date_to": end.isoformat(),
                "district": event.district,
                "municipality": event.municipality or "",
                "deaths": "" if event.deaths is None else event.deaths,
                "title": detail.title or "",
                "query_en": f'landslide "{place}" {date_filter}',
                "query_np": f'पहिरो "{place}" {date_filter}',
            }
        )
    rows.sort(
        key=lambda row: (
            0 if row["match_status"] == "unmatched" else 1,
            0 if row["priority"] == "high" else 1,
            -int(row["deaths"] or 0),
            row["event_date"],
            row["district"],
        )
    )
    fields = (
        list(rows[0])
        if rows
        else [
            "match_status",
            "priority",
            "bipad_cluster_id",
            "bipad_member_count",
            "bipad_member_ids",
            "event_date",
            "search_date_from",
            "search_date_to",
            "district",
            "municipality",
            "deaths",
            "title",
            "query_en",
            "query_np",
        ]
    )
    return _write_csv(path, fields, rows), status_counts


def write_unmatched_news(
    path: Path,
    news: list[InventoryEvent],
    matches: list[Match],
    details: dict[str, EventDetail],
) -> int:
    matched = {match.news_id for match in matches if match.tier in {"A", "B"}}
    rows = []
    for event in news:
        if event.event_id in matched:
            continue
        detail = details.get(event.event_id, EventDetail())
        rows.append(
            {
                "news_event_id": event.event_id,
                "event_date": event.event_date.isoformat(),
                "district": event.district,
                "municipality": event.municipality or "",
                "deaths": "" if event.deaths is None else event.deaths,
                "title": detail.title or "",
                "url": detail.url or "",
            }
        )
    return _write_csv(
        path,
        ["news_event_id", "event_date", "district", "municipality", "deaths", "title", "url"],
        rows,
    )


def write_coolr_inventory_summary(database_path: Path, path: Path) -> tuple[int, int]:
    """Aggregate COOLR polygons into inventory groups, never incident counts."""

    with connect_sqlite(database_path) as connection:
        rows = connection.execute(
            """
            SELECT incident_date_ad,
                   json_extract(raw_json, '$.event_title') AS title,
                   json_extract(raw_json, '$.source_name') AS source_name,
                   json_extract(raw_json, '$.method') AS method,
                   json_extract(raw_json, '$.landslide_category') AS category,
                   json_extract(raw_json, '$.location_description') AS location,
                   json_extract(raw_json, '$.citation') AS citation,
                   COUNT(*) AS feature_count,
                   MIN(latitude) AS lat_min, MAX(latitude) AS lat_max,
                   MIN(longitude) AS lon_min, MAX(longitude) AS lon_max,
                   AVG(latitude) AS centroid_lat, AVG(longitude) AS centroid_lon
            FROM external_records
            WHERE source = 'nasa-coolr'
            GROUP BY incident_date_ad, title, source_name, method, category, location, citation
            ORDER BY incident_date_ad, title, location
            """
        ).fetchall()
    output_rows = []
    feature_count = 0
    for row in rows:
        count = int(row["feature_count"])
        feature_count += count
        key = stable_hash(str(row["incident_date_ad"]), str(row["title"]), str(row["location"]))[
            :20
        ]
        output_rows.append({"inventory_key": key, **dict(row)})
    fields = [
        "inventory_key",
        "incident_date_ad",
        "title",
        "source_name",
        "method",
        "category",
        "location",
        "citation",
        "feature_count",
        "lat_min",
        "lat_max",
        "lon_min",
        "lon_max",
        "centroid_lat",
        "centroid_lon",
    ]
    return _write_csv(path, fields, output_rows), feature_count


def write_summary_report(
    path: Path,
    *,
    generated_at: str,
    comparison_end: date,
    news_count: int,
    bipad_raw_count: int,
    bipad_cluster_count: int,
    collapse_summary: dict[str, Any],
    overlap_summary: dict[str, Any],
    status_counts: dict[str, int],
    search_seed_count: int,
    unmatched_news_count: int,
    coolr_inventory_count: int,
    coolr_feature_count: int,
) -> None:
    lines = [
        "# External Inventory Match Report",
        "",
        f"Generated at: {generated_at}",
        f"Common comparison cutoff: {comparison_end.isoformat()}",
        "",
        "## Inputs",
        f"- Canonical news events: {news_count}",
        f"- BIPAD rows in the study window: {bipad_raw_count}",
        f"- Harmonized BIPAD incident clusters: {bipad_cluster_count}",
        f"- BIPAD collapse ratio: {collapse_summary.get('collapse_ratio')}",
        "",
        "## Candidate overlap",
        f"- Tier A candidates: {overlap_summary['by_tier']['A']}",
        f"- Tier B candidates: {overlap_summary['by_tier']['B']}",
        f"- Tier C candidates: {overlap_summary['by_tier']['C']}",
        f"- BIPAD clusters with a strong A/B match: {status_counts['strong_match']}",
        f"- BIPAD clusters with only a weak Tier-C candidate: {status_counts['weak_candidate']}",
        f"- BIPAD clusters with no candidate: {status_counts['unmatched']}",
        f"- Targeted search seeds: {search_seed_count}",
        f"- Canonical news events without an A/B match: {unmatched_news_count}",
        "",
        "## COOLR",
        f"- Scientific inventory groups: {coolr_inventory_count}",
        f"- Mapped polygon features: {coolr_feature_count}",
        "- COOLR polygons are spatial evidence, not independent incident counts.",
        "",
        "## Interpretation",
        "BIPAD is an incomplete administrative observation system, not ground truth. "
        "The outputs report overlap and candidate links—not precision or recall. Tier C "
        "is intentionally treated as a weak lead because district-level ±7-day overlap "
        "is common during the monsoon.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def run_external_match_stage(config: AppConfig) -> None:
    """Run the external comparison and write auditable gap-analysis outputs."""

    initialize_sqlite(config.sqlite_path)
    output_dir = config.resolve_path("outputs_dir")
    ensure_directory(output_dir)
    start_year, end_year = config.study_period
    study_start = date(start_year, 1, 1)
    study_end = date(end_year, 12, 31)
    bipad, bipad_details = load_external_bipad(config.sqlite_path, study_start, study_end)
    if not bipad:
        raise RuntimeError("No in-window BIPAD external records found; run external_collect first.")
    comparison_end = min(study_end, max(event.event_date for event in bipad))
    news, news_details = load_canonical_news(config.sqlite_path, study_start, comparison_end)
    collapsed_bipad, collapse_summary = collapse_to_incidents(bipad)
    matches, overlap_summary = match_inventories(news, collapsed_bipad)
    settings = config.raw.get("external_sources", {}).get("matching", {})
    permutations = int(settings.get("permutations", 100))
    agreement = full_agreement_report(news, bipad, permutations=permutations)
    generated_at = utc_now_iso()
    agreement_payload = {
        "generated_at": generated_at,
        "comparison_start": study_start.isoformat(),
        "comparison_end": comparison_end.isoformat(),
        "external_sources": ["bipad", "nasa-coolr"],
        **agreement,
    }
    (output_dir / "external_agreement.json").write_text(
        json.dumps(agreement_payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    news_by_id = {event.event_id: event for event in news}
    bipad_by_id = {event.event_id: event for event in collapsed_bipad}
    match_count = write_match_candidates(
        output_dir / "external_bipad_match_candidates.csv",
        matches,
        news_by_id,
        bipad_by_id,
        news_details,
        bipad_details,
    )
    search_seed_count, status_counts = write_search_seeds(
        output_dir / "external_search_seeds.csv", collapsed_bipad, matches, bipad_details
    )
    unmatched_news_count = write_unmatched_news(
        output_dir / "external_unmatched_news.csv", news, matches, news_details
    )
    coolr_inventory_count, coolr_feature_count = write_coolr_inventory_summary(
        config.sqlite_path, output_dir / "external_coolr_inventories.csv"
    )
    write_summary_report(
        output_dir / "external_match_report.md",
        generated_at=generated_at,
        comparison_end=comparison_end,
        news_count=len(news),
        bipad_raw_count=len(bipad),
        bipad_cluster_count=len(collapsed_bipad),
        collapse_summary=collapse_summary,
        overlap_summary=overlap_summary,
        status_counts=status_counts,
        search_seed_count=search_seed_count,
        unmatched_news_count=unmatched_news_count,
        coolr_inventory_count=coolr_inventory_count,
        coolr_feature_count=coolr_feature_count,
    )
    LOGGER.info(
        "External match complete: news=%s bipad_rows=%s bipad_clusters=%s "
        "candidate_pairs=%s search_seeds=%s coolr_inventories=%s coolr_features=%s",
        len(news),
        len(bipad),
        len(collapsed_bipad),
        match_count,
        search_seed_count,
        coolr_inventory_count,
        coolr_feature_count,
    )
