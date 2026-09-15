"""Review-gated ingestion of externally assisted news discoveries."""

from __future__ import annotations

import logging
import os
import re
import csv
from collections import defaultdict
from dataclasses import replace
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from ..config import AppConfig
from ..db import connect_sqlite, initialize_sqlite
from ..scrape.fetcher import HTTPFetcher
from ..scrape.models import DiscoveredUrl
from ..scrape.parser import parse_article_html
from ..scrape.storage import upsert_discovered_url, upsert_raw_article
from ..sources import SourceDefinition, load_sources
from ..utils import ensure_directory, utc_now_iso

LOGGER = logging.getLogger(__name__)
ASSISTED_METHOD = "external_seed_bipad"
EPAPER_METHOD = "external_epaper_review"


def _domain_key(url: str) -> str:
    hostname = (urlparse(url).hostname or "").casefold().strip(".")
    parts = hostname.split(".")
    if len(parts) >= 3 and ".".join(parts[-2:]) in {"com.np", "org.np", "gov.np"}:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:]) if len(parts) >= 2 else hostname


def _slug_from_url(url: str) -> str:
    key = _domain_key(url).split(".")[0]
    return key.replace("_", "-") or "external-assisted"


def source_for_candidate(
    config: AppConfig,
    *,
    resolved_url: str,
    source_name: str | None,
) -> SourceDefinition:
    """Reuse configured source metadata when domains match, otherwise use a safe generic."""

    candidate_domain = _domain_key(resolved_url)
    for source in load_sources(config):
        if _domain_key(source.base_url) == candidate_domain:
            return source
    parsed_url = urlparse(resolved_url)
    return SourceDefinition(
        name=source_name or candidate_domain,
        slug=_slug_from_url(resolved_url),
        language="en",
        base_url=f"{parsed_url.scheme}://{parsed_url.netloc}",
        discovery={"primary": ASSISTED_METHOD},
        entry_points=[
            {"kind": ASSISTED_METHOD, "url": resolved_url, "pagination": "none"}
        ],
    )


def _candidate_rows(config: AppConfig, limit: int) -> list[Any]:
    if limit <= 0:
        return []
    with connect_sqlite(config.sqlite_path) as connection:
        return connection.execute(
            """
            SELECT candidate_id, seed_id, seed_event_date, source_name, resolved_url,
                   published_at
            FROM external_news_candidates
            WHERE review_status = 'relevant_event'
              AND resolved_url IS NOT NULL
              AND COALESCE(ingest_status, 'not_ingested') != 'ingested'
            ORDER BY COALESCE(seed_deaths, 0) DESC, seed_event_date, candidate_id
            LIMIT ?
            """,
            (limit,),
        ).fetchall()


def _prefer_candidate_publication_date(parsed: Any, published_at: str | None) -> Any:
    """Use index metadata when a publisher page exposes an unrelated current date."""

    if not published_at:
        return parsed
    candidate_year = re.search(r"\b(20\d{2})\b", published_at)
    parsed_year = re.search(r"\b(20\d{2})\b", parsed.published_date_raw or "")
    if parsed_year and candidate_year and parsed_year.group(1) == candidate_year.group(1):
        return parsed
    return replace(parsed, published_date_raw=published_at)


def _mark_candidates(
    database_path: Path,
    candidate_ids: list[str],
    *,
    status: str,
    ingested_url: str | None = None,
    error: str | None = None,
) -> None:
    if not candidate_ids:
        return
    placeholders = ",".join("?" for _value in candidate_ids)
    with connect_sqlite(database_path) as connection:
        connection.execute(
            f"""
            UPDATE external_news_candidates
            SET ingest_status=?, ingested_url=?, ingested_at=?, ingest_error=?
            WHERE candidate_id IN ({placeholders})
            """,
            (
                status,
                ingested_url,
                utc_now_iso() if status == "ingested" else None,
                error,
                *candidate_ids,
            ),
        )
        connection.commit()


def ingest_reviewed_candidates(
    config: AppConfig,
    fetcher: HTTPFetcher | None = None,
) -> dict[str, int]:
    """Fetch only event-specific, publisher-resolved candidates into raw articles."""

    initialize_sqlite(config.sqlite_path)
    settings = dict(
        config.raw.get("external_sources", {})
        .get("matching", {})
        .get("candidate_ingest", {})
    )
    configured_limit = int(settings.get("max_candidates", 25))
    limit = int(os.getenv("LS_EXTERNAL_INGEST_LIMIT", str(configured_limit)))
    min_text_chars = int(settings.get("min_text_chars", 200))
    rows = _candidate_rows(config, limit)
    grouped: dict[str, list[Any]] = defaultdict(list)
    for row in rows:
        grouped[str(row["resolved_url"])].append(row)
    http_fetcher = fetcher or HTTPFetcher.from_config(config)
    summary = {
        "candidate_rows_selected": len(rows),
        "publisher_urls_selected": len(grouped),
        "publisher_urls_ingested": 0,
        "publisher_urls_failed": 0,
    }
    failures: list[str] = []
    for url, url_rows in grouped.items():
        candidate_ids = [str(row["candidate_id"]) for row in url_rows]
        try:
            source = source_for_candidate(
                config,
                resolved_url=url,
                source_name=url_rows[0]["source_name"],
            )
            fetch_result = http_fetcher.fetch(url)
            parsed = parse_article_html(source, fetch_result.text, url)
            parsed = _prefer_candidate_publication_date(
                parsed,
                url_rows[0]["published_at"],
            )
            if not 200 <= fetch_result.status_code < 300:
                raise RuntimeError(f"HTTP {fetch_result.status_code}")
            if not parsed.parse_success or len(parsed.text) < min_text_chars:
                raise RuntimeError(
                    f"article parse failed or text too short ({len(parsed.text)} characters)"
                )
            seed_ids = sorted({str(row["seed_id"]) for row in url_rows})
            year_hint = int(str(url_rows[0]["seed_event_date"])[:4])
            discovery = DiscoveredUrl(
                url=url,
                source=source.slug,
                method=ASSISTED_METHOD,
                entry_point="external_news_candidates",
                query_term="bipad:" + ",".join(seed_ids),
                year_hint=year_hint,
            )
            upsert_discovered_url(config.sqlite_path, discovery)
            upsert_raw_article(
                config.sqlite_path,
                source=source.slug,
                url=url,
                fetch_result=fetch_result,
                parsed=parsed,
                method=ASSISTED_METHOD,
                entry_point="external_news_candidates",
            )
            _mark_candidates(
                config.sqlite_path,
                candidate_ids,
                status="ingested",
                ingested_url=url,
            )
            summary["publisher_urls_ingested"] += 1
        except Exception as exc:  # noqa: BLE001 - report each reviewed URL independently
            message = f"{type(exc).__name__}: {exc}"
            _mark_candidates(
                config.sqlite_path,
                candidate_ids,
                status="failed",
                error=message,
            )
            failures.append(f"{url}: {message}")
            summary["publisher_urls_failed"] += 1
            LOGGER.error("Assisted candidate ingestion failed for %s: %s", url, message)
    _write_report(
        config.resolve_path("outputs_dir") / "external_ingest_report.md",
        summary,
        failures,
    )
    return summary


def _write_report(path: Path, summary: dict[str, int], failures: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# External Candidate Ingest Report",
        "",
        f"Generated at: {utc_now_iso()}",
        "",
        f"- Candidate rows selected: {summary['candidate_rows_selected']}",
        f"- Publisher URLs selected: {summary['publisher_urls_selected']}",
        f"- Publisher URLs ingested: {summary['publisher_urls_ingested']}",
        f"- Publisher URLs failed: {summary['publisher_urls_failed']}",
        "",
        f"Every inserted article carries method `{ASSISTED_METHOD}` and is excluded from "
        "BIPAD agreement and locked-test sampling.",
    ]
    if failures:
        lines.extend(["", "## Failures", *[f"- {failure}" for failure in failures]])
    path.write_text("\n".join([*lines, ""]), encoding="utf-8")


def run_external_ingest_stage(config: AppConfig) -> None:
    """CLI stage wrapper."""

    for directory in config.data_directories():
        ensure_directory(directory)
    summary = ingest_reviewed_candidates(config)
    LOGGER.info("External candidate ingestion complete: %s", summary)


def _epaper_queue_path(config: AppConfig) -> Path:
    """Return the generated e-paper review queue path."""

    configured = config.raw.get("external_sources", {}).get("epaper_review_queue", {})
    value = configured.get("output_csv", "epaper_review_queue.csv")
    path = Path(str(value))
    return path if path.is_absolute() else config.resolve_path("outputs_dir") / path


def ingest_reviewed_epaper(config: AppConfig, fetcher: HTTPFetcher | None = None) -> dict[str, int]:
    """Ingest event-specific article URLs from the e-paper review queue.

    The queue is deliberately kept as a CSV (rather than a database table) so
    that the human review remains auditable.  Ingest status columns are added
    on first run and updated per row; duplicate article URLs are fetched once.
    """

    initialize_sqlite(config.sqlite_path)
    path = _epaper_queue_path(config)
    if not path.exists():
        raise FileNotFoundError(f"E-paper review queue not found: {path}")
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    required = {"review_id", "review_status", "article_url", "issue_date"}
    missing = required - set(fieldnames)
    if missing:
        raise ValueError(f"E-paper queue missing columns: {', '.join(sorted(missing))}")
    for name in ("ingest_status", "ingest_error", "ingested_at"):
        if name not in fieldnames:
            fieldnames.append(name)

    settings = dict(config.raw.get("external_sources", {}).get("matching", {}).get("candidate_ingest", {}))
    configured_limit = int(config.raw.get("external_sources", {}).get("epaper_review_queue", {}).get("max_articles", 100))
    limit = int(os.getenv("LS_EXTERNAL_EPAPER_INGEST_LIMIT", str(configured_limit)))
    min_text_chars = int(settings.get("min_text_chars", 200))
    selected = [
        row for row in rows
        if row.get("review_status", "").strip() == "relevant_event"
        and row.get("article_url", "").strip()
        and row.get("ingest_status", "").strip() != "ingested"
    ][:max(0, limit)]
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in selected:
        grouped[row["article_url"].strip()].append(row)
    http_fetcher = fetcher or HTTPFetcher.from_config(config)
    summary = {
        "queue_rows_selected": len(selected),
        "article_urls_selected": len(grouped),
        "article_urls_ingested": 0,
        "article_urls_failed": 0,
    }
    failures: list[str] = []
    for url, url_rows in grouped.items():
        try:
            source = source_for_candidate(config, resolved_url=url, source_name="epaper-review")
            result = http_fetcher.fetch(url)
            if not 200 <= result.status_code < 300:
                raise RuntimeError(f"HTTP {result.status_code}")
            parsed = parse_article_html(source, result.text, url)
            if not parsed.parse_success or len(parsed.text) < min_text_chars:
                raise RuntimeError(f"article parse failed or text too short ({len(parsed.text)} characters)")
            issue_date = (url_rows[0].get("issue_date") or "")[:4]
            article_date = (url_rows[0].get("article_date") or "")[:4]
            year_hint = int(article_date or issue_date) if (article_date or issue_date).isdigit() else None
            discovery = DiscoveredUrl(
                url=url,
                source=source.slug,
                method=EPAPER_METHOD,
                entry_point="epaper_review_queue",
                query_term="epaper:" + ",".join(row.get("review_id", "") for row in url_rows),
                year_hint=year_hint,
            )
            upsert_discovered_url(config.sqlite_path, discovery)
            upsert_raw_article(
                config.sqlite_path,
                source=source.slug,
                url=url,
                fetch_result=result,
                parsed=parsed,
                method=EPAPER_METHOD,
                entry_point="epaper_review_queue",
            )
            for row in url_rows:
                row["ingest_status"] = "ingested"
                row["ingest_error"] = ""
                row["ingested_at"] = utc_now_iso()
            summary["article_urls_ingested"] += 1
        except Exception as exc:  # noqa: BLE001 - continue independent reviewed URLs
            message = f"{type(exc).__name__}: {exc}"
            for row in url_rows:
                row["ingest_status"] = "failed"
                row["ingest_error"] = message
                row["ingested_at"] = ""
            failures.append(f"{url}: {message}")
            summary["article_urls_failed"] += 1
            LOGGER.error("E-paper article ingestion failed for %s: %s", url, message)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    _write_epaper_report(config.resolve_path("outputs_dir") / "epaper_ingest_report.md", summary, failures)
    return summary


def _write_epaper_report(path: Path, summary: dict[str, int], failures: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# E-paper Review Ingest Report", "", f"Generated at: {utc_now_iso()}", ""]
    lines.extend(f"- {key.replace('_', ' ').title()}: {value}" for key, value in summary.items())
    if failures:
        lines.extend(["", "## Failures", *[f"- {item}" for item in failures]])
    path.write_text("\n".join([*lines, ""]), encoding="utf-8")


def run_external_epaper_ingest_stage(config: AppConfig) -> None:
    """CLI wrapper for e-paper review queue ingestion."""

    for directory in config.data_directories():
        ensure_directory(directory)
    summary = ingest_reviewed_epaper(config)
    LOGGER.info("E-paper review ingestion complete: %s", summary)
