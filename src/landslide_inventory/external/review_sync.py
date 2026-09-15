"""Synchronize human review decisions from the exported candidate CSV."""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from ..config import AppConfig
from ..db import connect_sqlite, initialize_sqlite

LOGGER = logging.getLogger(__name__)

ALLOWED_STATUSES = {
    "relevant_event",
    "relevant_district",
    "needs_resolution",
    "irrelevant",
}


def _candidate_csv(config: AppConfig) -> Path:
    settings = config.raw.get("external_sources", {}).get("matching", {})
    configured = Path(str(settings.get("seed_discovery", {}).get(
        "output_csv", "external_news_candidates.csv"
    )))
    return configured if configured.is_absolute() else config.resolve_path("outputs_dir") / configured


def sync_reviewed_candidates(config: AppConfig) -> dict[str, int]:
    """Import review fields from the exported CSV without touching ingest fields."""

    path = _candidate_csv(config)
    if not path.exists():
        raise FileNotFoundError(f"Candidate review CSV not found: {path}")
    initialize_sqlite(config.sqlite_path)
    rows = list(csv.DictReader(path.open(encoding="utf-8", newline="")))
    required = {"candidate_id", "review_status", "resolved_url", "review_notes"}
    missing = required - set(rows[0] if rows else required)
    if missing:
        raise ValueError(f"Candidate CSV missing columns: {', '.join(sorted(missing))}")
    seen: set[str] = set()
    updates: list[tuple[str, str | None, str | None, str]] = []
    for row in rows:
        candidate_id = str(row.get("candidate_id", "")).strip()
        status = str(row.get("review_status", "")).strip()
        if not candidate_id:
            raise ValueError("Candidate CSV contains a blank candidate_id")
        if candidate_id in seen:
            raise ValueError(f"Duplicate candidate_id in CSV: {candidate_id}")
        seen.add(candidate_id)
        if status in {"", "unreviewed"}:
            continue
        if status not in ALLOWED_STATUSES:
            raise ValueError(
                f"Invalid review_status '{status}' for {candidate_id}; "
                f"allowed: {', '.join(sorted(ALLOWED_STATUSES))}"
            )
        resolved_url = str(row.get("resolved_url", "")).strip() or None
        if status == "relevant_event" and not resolved_url:
            raise ValueError(f"relevant_event requires resolved_url: {candidate_id}")
        notes = str(row.get("review_notes", "")).strip() or None
        updates.append((status, resolved_url, notes, candidate_id))

    with connect_sqlite(config.sqlite_path) as connection:
        known = {
            str(item[0])
            for item in connection.execute("SELECT candidate_id FROM external_news_candidates")
        }
        unknown = [candidate_id for *_rest, candidate_id in updates if candidate_id not in known]
        if unknown:
            raise ValueError(f"CSV contains unknown candidate_id: {unknown[0]}")
        connection.executemany(
            """
            UPDATE external_news_candidates
            SET review_status=?, resolved_url=?, review_notes=?
            WHERE candidate_id=?
            """,
            updates,
        )
        connection.commit()
    summary = {"csv_rows": len(rows), "reviewed_rows_synced": len(updates)}
    LOGGER.info("Synchronized candidate reviews from %s: %s", path, summary)
    return summary


def run_external_review_sync_stage(config: AppConfig) -> None:
    sync_reviewed_candidates(config)
