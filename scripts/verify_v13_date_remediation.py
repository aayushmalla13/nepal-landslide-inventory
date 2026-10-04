#!/usr/bin/env python3
"""Verify closure of confirmed v1.2 date failures in the v1.3 diagnostic."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_COMPLETED = ROOT / "data/outputs/v12_final_validation_COMPLETED.csv"
DEFAULT_CORRECTIONS = ROOT / "corrections/article_corrections.csv"
DEFAULT_DATABASE = ROOT / "data/outputs/v13_pipeline_diagnostic/landslide_inventory.sqlite"
DEFAULT_REPLAY = ROOT / "data/outputs/v13_date_remediation_replay.csv"
DEFAULT_SUMMARY = ROOT / "data/outputs/v13_date_remediation_summary.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def verify(
    completed_path: Path,
    corrections_path: Path,
    database_path: Path,
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    failures = [
        row for row in read_csv(completed_path) if row["date_correct"].strip() == "no"
    ]
    corrections = {row["url"]: row for row in read_csv(corrections_path)}
    replay: list[dict[str, str]] = []
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        for row in failures:
            url = row["representative_url"]
            correction = corrections.get(url)
            if correction is None:
                raise ValueError(f"Date failure lacks a reviewed correction: {row['row_id']}")
            article = connection.execute(
                """
                SELECT event_date_ad, district, municipality, dedup_cluster_id
                FROM article_events WHERE url = ?
                """,
                (url,),
            ).fetchone()
            if article is None:
                raise ValueError(f"Date failure URL is absent from diagnostic: {url}")
            excluded = correction["exclude_from_canonical"].strip() == "1"
            canonical = None
            if article["dedup_cluster_id"]:
                canonical = connection.execute(
                    """
                    SELECT event_id, event_date_ad, district, municipality
                    FROM canonical_events WHERE dedup_cluster_id = ?
                    """,
                    (article["dedup_cluster_id"],),
                ).fetchone()
            if excluded:
                if article["dedup_cluster_id"] is not None or canonical is not None:
                    raise ValueError(f"Excluded date failure remains canonical: {row['row_id']}")
                outcome = "excluded_exact_date_or_identity_unresolved"
            else:
                expected = correction["event_date_ad"].strip()
                if not expected:
                    raise ValueError(f"Non-excluded date failure lacks corrected date: {row['row_id']}")
                if article["event_date_ad"] != expected:
                    raise ValueError(f"Article date correction was not applied: {row['row_id']}")
                if canonical is None or canonical["event_date_ad"] != expected:
                    raise ValueError(f"Canonical date correction was not applied: {row['row_id']}")
                outcome = "corrected_exact_date"
            replay.append(
                {
                    "row_id": row["row_id"],
                    "v12_event_id": row["event_id"],
                    "representative_url": url,
                    "claimed_event_date": row["claimed_event_date"],
                    "outcome": outcome,
                    "v13_event_id": canonical["event_id"] if canonical else "",
                    "v13_event_date": canonical["event_date_ad"] if canonical else "",
                    "v13_district": canonical["district"] if canonical else "",
                    "correction_action": correction["correction_action"],
                    "scope_reason": correction["scope_reason"],
                }
            )
    counts: dict[str, int] = {}
    for row in replay:
        counts[row["outcome"]] = counts.get(row["outcome"], 0) + 1
    summary = {
        "audit": "v13_date_remediation_replay_v1",
        "status": "diagnostic_spent_sample_only",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "confirmed_v12_date_failures": len(failures),
        "resolved_rows": len(replay),
        "outcome_counts": counts,
        "unresolved_rows": len(failures) - len(replay),
        "interpretation": (
            "This replay verifies repair application on the spent v1.2 validation "
            "sample. It is not an unbiased estimate of v1.3 performance."
        ),
    }
    return replay, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--completed", type=Path, default=DEFAULT_COMPLETED)
    parser.add_argument("--corrections", type=Path, default=DEFAULT_CORRECTIONS)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--replay", type=Path, default=DEFAULT_REPLAY)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    args = parser.parse_args()
    replay, summary = verify(args.completed, args.corrections, args.database)
    args.replay.parent.mkdir(parents=True, exist_ok=True)
    with args.replay.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(replay[0]))
        writer.writeheader()
        writer.writerows(replay)
    summary["input_sha256"] = {
        str(path.resolve().relative_to(ROOT)): sha256(path)
        for path in (args.completed, args.corrections, args.database, Path(__file__))
    }
    summary["replay_sha256"] = sha256(args.replay)
    args.summary.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"verified {len(replay)} date failures")
    print(f"wrote {args.replay}")
    print(f"wrote {args.summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
