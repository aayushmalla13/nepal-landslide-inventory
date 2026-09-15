"""Bounded news-candidate discovery from unmatched external incident seeds.

The stage deliberately stops at candidate metadata. BIPAD can guide discovery,
but a Google News index hit is not article evidence and must not enter
``raw_articles`` until its publisher URL and content have been reviewed.
"""

from __future__ import annotations

import csv
import logging
import os
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from ..config import AppConfig
from ..db import connect_sqlite, initialize_sqlite
from ..utils import ensure_directory, stable_hash, utc_now_iso
from .http import ExternalHttpClient

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SearchSeed:
    """One harmonized BIPAD incident selected for targeted discovery."""

    seed_id: str
    match_status: str
    priority: str
    event_date: str
    search_date_from: str
    search_date_to: str
    district: str
    municipality: str | None
    deaths: int | None
    title: str | None


@dataclass(frozen=True, slots=True)
class NewsCandidate:
    """One provider result linked to the seed and query that found it."""

    candidate_id: str
    seed_id: str
    seed_match_status: str
    seed_event_date: str
    seed_district: str
    seed_municipality: str | None
    seed_deaths: int | None
    provider: str
    query_scope: str
    query: str
    result_id: str
    result_url: str
    source_name: str | None
    source_home_url: str | None
    title: str | None
    published_at: str | None
    retrieved_at: str


CANDIDATE_COLUMNS = tuple(NewsCandidate.__dataclass_fields__)


def _optional_int(value: Any) -> int | None:
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def load_search_seeds(
    path: Path,
    *,
    statuses: set[str],
    priorities: set[str],
    limit: int,
) -> list[SearchSeed]:
    """Load the already severity-ordered match output without reinterpreting it."""

    if limit <= 0:
        return []
    if not path.exists():
        raise RuntimeError(f"Search seed file not found: {path}; run external_match first.")
    seeds: list[SearchSeed] = []
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("match_status") not in statuses or row.get("priority") not in priorities:
                continue
            seeds.append(
                SearchSeed(
                    seed_id=str(row["bipad_cluster_id"]),
                    match_status=str(row["match_status"]),
                    priority=str(row["priority"]),
                    event_date=str(row["event_date"]),
                    search_date_from=str(row["search_date_from"]),
                    search_date_to=str(row["search_date_to"]),
                    district=str(row["district"]),
                    municipality=str(row.get("municipality") or "").strip() or None,
                    deaths=_optional_int(row.get("deaths")),
                    title=str(row.get("title") or "").strip() or None,
                )
            )
            if len(seeds) >= limit:
                break
    return seeds


def build_seed_queries(seed: SearchSeed) -> list[tuple[str, str]]:
    """Return narrow and fallback queries in deterministic order."""

    # Google treats after/before as exclusive. Expand by one day so the search
    # includes both boundaries written in the auditable seed CSV.
    after = date.fromisoformat(seed.search_date_from) - timedelta(days=1)
    before = date.fromisoformat(seed.search_date_to) + timedelta(days=1)
    date_filter = f"after:{after.isoformat()} before:{before.isoformat()}"
    queries: list[tuple[str, str]] = []
    if seed.municipality and seed.municipality.casefold() != seed.district.casefold():
        queries.append(
            ("municipality_en", f'landslide "{seed.municipality}" {date_filter}')
        )
    queries.extend(
        [
            ("district_en", f'landslide "{seed.district}" Nepal {date_filter}'),
            ("district_np", f'पहिरो "{seed.district}" {date_filter}'),
        ]
    )
    return queries


def google_news_rss_url(endpoint: str, query: str) -> str:
    """Build a stable RSS URL; dates stay in the query rather than metadata."""

    return f"{endpoint}?{urlencode({'q': query, 'hl': 'en-US', 'gl': 'US', 'ceid': 'US:en'})}"


def _published_iso(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
        return parsed.isoformat()
    except (TypeError, ValueError, OverflowError):
        return value.strip() or None


def parse_google_news_rss(
    xml_text: str,
    *,
    seed: SearchSeed,
    query_scope: str,
    query: str,
    retrieved_at: str,
) -> list[NewsCandidate]:
    """Parse RSS item metadata without pretending Google wrappers are article URLs."""

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise RuntimeError(f"Invalid Google News RSS for seed {seed.seed_id}: {exc}") from exc
    candidates: list[NewsCandidate] = []
    for item in root.findall("./channel/item"):
        result_url = (item.findtext("link") or "").strip()
        result_id = (item.findtext("guid") or result_url).strip()
        if not result_url or not result_id:
            continue
        source_element = item.find("source")
        source_name = (
            (source_element.text or "").strip() if source_element is not None else None
        )
        source_home_url = (
            str(source_element.attrib.get("url") or "").strip() or None
            if source_element is not None
            else None
        )
        candidate_id = stable_hash(seed.seed_id, "google-news-rss", result_id)
        candidates.append(
            NewsCandidate(
                candidate_id=candidate_id,
                seed_id=seed.seed_id,
                seed_match_status=seed.match_status,
                seed_event_date=seed.event_date,
                seed_district=seed.district,
                seed_municipality=seed.municipality,
                seed_deaths=seed.deaths,
                provider="google-news-rss",
                query_scope=query_scope,
                query=query,
                result_id=result_id,
                result_url=result_url,
                source_name=source_name,
                source_home_url=source_home_url,
                title=(item.findtext("title") or "").strip() or None,
                published_at=_published_iso(item.findtext("pubDate")),
                retrieved_at=retrieved_at,
            )
        )
    return candidates


def upsert_news_candidates(database_path: Path, candidates: list[NewsCandidate]) -> int:
    """Upsert candidate metadata while preserving any later review decision."""

    if not candidates:
        return 0
    initialize_sqlite(database_path)
    columns = ", ".join(CANDIDATE_COLUMNS)
    placeholders = ", ".join(f":{column}" for column in CANDIDATE_COLUMNS)
    updates = ", ".join(
        f"{column}=excluded.{column}"
        for column in CANDIDATE_COLUMNS
        if column not in {"candidate_id"}
    )
    with connect_sqlite(database_path) as connection:
        connection.executemany(
            f"""
            INSERT INTO external_news_candidates ({columns})
            VALUES ({placeholders})
            ON CONFLICT(candidate_id) DO UPDATE SET {updates}
            """,
            [asdict(candidate) for candidate in candidates],
        )
        connection.commit()
    return len(candidates)


def export_news_candidates(database_path: Path, path: Path) -> int:
    """Export the review queue, keeping fatal/unmatched seeds at the top."""

    with connect_sqlite(database_path) as connection:
        rows = connection.execute(
            f"""
            SELECT {', '.join(CANDIDATE_COLUMNS)}, review_status, resolved_url, review_notes,
                   ingest_status, ingested_url, ingested_at, ingest_error
            FROM external_news_candidates
            ORDER BY
                CASE seed_match_status WHEN 'unmatched' THEN 0 ELSE 1 END,
                COALESCE(seed_deaths, 0) DESC,
                seed_event_date,
                seed_district,
                published_at,
                candidate_id
            """
        ).fetchall()
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        *CANDIDATE_COLUMNS,
        "review_status",
        "resolved_url",
        "review_notes",
        "ingest_status",
        "ingested_url",
        "ingested_at",
        "ingest_error",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(dict(row) for row in rows)
    return len(rows)


def _settings(config: AppConfig) -> dict[str, Any]:
    matching = config.raw.get("external_sources", {}).get("matching", {})
    return dict(matching.get("seed_discovery", {}))


def discover_seed_candidates(
    config: AppConfig,
    client: ExternalHttpClient | None = None,
) -> dict[str, int]:
    """Query a bounded seed batch and persist index candidates for review."""

    settings = _settings(config)
    output_dir = config.resolve_path("outputs_dir")
    seed_path = output_dir / str(settings.get("seed_file", "external_search_seeds.csv"))
    configured_limit = int(settings.get("max_seeds", 50))
    limit = int(os.getenv("LS_EXTERNAL_SEED_LIMIT", str(configured_limit)))
    seeds = load_search_seeds(
        seed_path,
        statuses={str(value) for value in settings.get("statuses", ["unmatched"])},
        priorities={str(value) for value in settings.get("priorities", ["high"])},
        limit=max(0, limit),
    )
    endpoint = str(
        settings.get("endpoint", "https://news.google.com/rss/search")
    )
    http_client = client or ExternalHttpClient(
        user_agent=str(config.raw["runtime"]["user_agent"]),
        timeout_seconds=float(settings.get("timeout_seconds", 30)),
        retries=int(settings.get("retries", 3)),
        rate_limit_seconds=float(settings.get("rate_limit_seconds", 1.0)),
    )
    max_results = int(settings.get("max_results_per_query", 20))
    all_candidates: list[NewsCandidate] = []
    query_count = 0
    seeds_with_results: set[str] = set()
    for seed in seeds:
        for query_scope, query in build_seed_queries(seed):
            response = http_client.request(
                google_news_rss_url(endpoint, query),
                headers={"Accept": "application/rss+xml,application/xml;q=0.9,*/*;q=0.8"},
            )
            query_count += 1
            if not 200 <= response.status < 300:
                LOGGER.warning(
                    "Seed query failed: seed=%s scope=%s status=%s",
                    seed.seed_id,
                    query_scope,
                    response.status,
                )
                continue
            candidates = parse_google_news_rss(
                response.text,
                seed=seed,
                query_scope=query_scope,
                query=query,
                retrieved_at=response.retrieved_at,
            )[:max_results]
            if candidates:
                seeds_with_results.add(seed.seed_id)
            all_candidates.extend(candidates)
    # The same article may be returned by the narrow and fallback queries. Its
    # deterministic candidate ID keeps one row per seed/article relationship.
    deduplicated: dict[str, NewsCandidate] = {}
    for candidate in all_candidates:
        deduplicated.setdefault(candidate.candidate_id, candidate)
    stored = upsert_news_candidates(config.sqlite_path, list(deduplicated.values()))
    export_count = export_news_candidates(
        config.sqlite_path,
        output_dir / str(settings.get("output_csv", "external_news_candidates.csv")),
    )
    summary = {
        "seeds_selected": len(seeds),
        "queries_run": query_count,
        "seeds_with_results": len(seeds_with_results),
        "seeds_without_results": len(seeds) - len(seeds_with_results),
        "candidates_this_run": len(deduplicated),
        "candidates_stored_this_run": stored,
        "candidates_exported_total": export_count,
    }
    _write_report(output_dir / "external_seed_discovery_report.md", summary)
    return summary


def _write_report(path: Path, summary: dict[str, int]) -> None:
    lines = [
        "# External Seed Discovery Report",
        "",
        f"Generated at: {utc_now_iso()}",
        "",
        f"- Seeds selected: {summary['seeds_selected']}",
        f"- Queries run: {summary['queries_run']}",
        f"- Seeds with at least one result: {summary['seeds_with_results']}",
        f"- Seeds without results: {summary['seeds_without_results']}",
        f"- Unique candidates found this run: {summary['candidates_this_run']}",
        f"- Candidate rows exported in total: {summary['candidates_exported_total']}",
        "",
        "Candidate rows are discovery leads, not verified events. Google News wrapper URLs "
        "must be resolved and the publisher article reviewed before ingestion. BIPAD-assisted "
        "articles must remain identifiable so they are excluded from BIPAD agreement analysis.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def run_external_discover_stage(config: AppConfig) -> None:
    """CLI stage wrapper."""

    for directory in config.data_directories():
        ensure_directory(directory)
    initialize_sqlite(config.sqlite_path)
    summary = discover_seed_candidates(config)
    LOGGER.info("External seed discovery complete: %s", summary)
