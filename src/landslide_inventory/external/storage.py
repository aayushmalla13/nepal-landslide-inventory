"""Persistence and export helpers for external records."""

from __future__ import annotations

import csv
from collections.abc import Iterable
from pathlib import Path

from ..db import connect_sqlite, initialize_sqlite
from .models import ExternalRecord, records_to_rows, utc_now_iso

EXTERNAL_COLUMNS = (
    "record_id",
    "source",
    "source_family",
    "record_type",
    "source_record_id",
    "source_url",
    "title",
    "text",
    "published_at",
    "incident_date_raw",
    "incident_date_ad",
    "hazard_type",
    "country",
    "province",
    "district",
    "municipality",
    "ward",
    "latitude",
    "longitude",
    "deaths",
    "missing",
    "injured",
    "retrieval_medium",
    "retrieved_at",
    "content_hash",
    "raw_json",
)


UPSERT_SQL = f"""
INSERT INTO external_records ({", ".join(EXTERNAL_COLUMNS)})
VALUES ({", ".join(":" + column for column in EXTERNAL_COLUMNS)})
ON CONFLICT(record_id) DO UPDATE SET
    source_family=excluded.source_family,
    record_type=excluded.record_type,
    source_record_id=excluded.source_record_id,
    source_url=excluded.source_url,
    title=excluded.title,
    text=excluded.text,
    published_at=excluded.published_at,
    incident_date_raw=excluded.incident_date_raw,
    incident_date_ad=excluded.incident_date_ad,
    hazard_type=excluded.hazard_type,
    country=excluded.country,
    province=excluded.province,
    district=excluded.district,
    municipality=excluded.municipality,
    ward=excluded.ward,
    latitude=excluded.latitude,
    longitude=excluded.longitude,
    deaths=excluded.deaths,
    missing=excluded.missing,
    injured=excluded.injured,
    retrieval_medium=excluded.retrieval_medium,
    retrieved_at=excluded.retrieved_at,
    content_hash=excluded.content_hash,
    raw_json=excluded.raw_json,
    updated_at=CURRENT_TIMESTAMP
"""


def upsert_external_records(database_path: Path, records: Iterable[ExternalRecord]) -> int:
    """Insert or update normalized records and return the number handled."""

    rows = records_to_rows(records)
    if not rows:
        return 0
    initialize_sqlite(database_path)
    with connect_sqlite(database_path) as connection:
        connection.executemany(UPSERT_SQL, rows)
        connection.commit()
    return len(rows)


def start_source_run(database_path: Path, run_id: str, source: str, adapter: str) -> None:
    initialize_sqlite(database_path)
    with connect_sqlite(database_path) as connection:
        connection.execute(
            """INSERT INTO external_source_runs
               (run_id, source, adapter, status, started_at)
               VALUES (?, ?, ?, 'running', ?)""",
            (run_id, source, adapter, utc_now_iso()),
        )
        connection.commit()


def finish_source_run(
    database_path: Path,
    run_id: str,
    *,
    status: str,
    fetched_count: int = 0,
    stored_count: int = 0,
    error: str | None = None,
) -> None:
    with connect_sqlite(database_path) as connection:
        connection.execute(
            """UPDATE external_source_runs
               SET status=?, completed_at=?, fetched_count=?, stored_count=?, error=?
               WHERE run_id=?""",
            (status, utc_now_iso(), fetched_count, stored_count, error, run_id),
        )
        connection.commit()


def export_external_records(
    database_path: Path,
    output_path: Path,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
) -> int:
    """Export external records, optionally bounded to a study period.

    Incident dates take precedence. For document/archive records with no
    incident date, an ISO publication/capture date is used. Undated records are
    retained so lack of a parseable date does not silently destroy evidence.
    """

    initialize_sqlite(database_path)
    with connect_sqlite(database_path) as connection:
        where = ""
        parameters: tuple[str, ...] = ()
        if start_date and end_date:
            effective_date = "date(COALESCE(incident_date_ad, published_at))"
            where = f"WHERE {effective_date} IS NULL OR {effective_date} BETWEEN ? AND ? "
            parameters = (start_date, end_date)
        rows = connection.execute(
            f"SELECT {', '.join(EXTERNAL_COLUMNS)} FROM external_records "
            f"{where}ORDER BY source, incident_date_ad, record_id",
            parameters,
        ).fetchall()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=EXTERNAL_COLUMNS)
        writer.writeheader()
        writer.writerows(dict(row) for row in rows)
    return len(rows)


def source_counts(database_path: Path) -> dict[str, int]:
    initialize_sqlite(database_path)
    with connect_sqlite(database_path) as connection:
        rows = connection.execute(
            "SELECT source, COUNT(*) AS count FROM external_records GROUP BY source ORDER BY source"
        ).fetchall()
    return {str(row["source"]): int(row["count"]) for row in rows}
