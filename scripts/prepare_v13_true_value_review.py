#!/usr/bin/env python3
"""Prepare v1.3 true-value review using only verified date-remediation outcomes."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/outputs"
TEMPLATE = OUTPUT / "v13_remediation_BATCH_TRUE_VALUE_REVIEW.csv"
REMEDIATION_MANIFEST = OUTPUT / "v13_remediation_manifest.json"
DATE_REPLAY = OUTPUT / "v13_date_remediation_replay.csv"
DATE_SUMMARY = OUTPUT / "v13_date_remediation_summary.json"
REVIEW = OUTPUT / "v13_remediation_BATCH_TRUE_VALUE_REVIEW_PREFILLED.csv"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def prepare(
    rows: list[dict[str, str]], replay_rows: list[dict[str, str]]
) -> tuple[list[dict[str, str]], int, int]:
    replay = {row["row_id"]: row for row in replay_rows}
    prepared: list[dict[str, str]] = []
    fully_prefilled = 0
    partial_dates = 0
    for source in rows:
        row = dict(source)
        prior = replay.get(row["row_id"])
        actions = {value for value in row["recommended_actions"].split(";") if value}
        if prior and prior["outcome"] == "excluded_exact_date_or_identity_unresolved":
            row["reviewed_action"] = "exclude_candidate"
            row["reviewed_by"] = "date_remediation_v1"
            row["review_notes"] = (
                "Prior reviewed date remediation could not establish an exact event date "
                "or stable event identity; candidate excluded."
            )
            fully_prefilled += 1
        elif prior and prior["outcome"] == "corrected_exact_date":
            row["proposed_event_date"] = prior["v13_event_date"]
            if actions == {"correct_date"}:
                row["reviewed_action"] = "retain"
                row["reviewed_by"] = "date_remediation_v1"
                row["review_notes"] = (
                    "Exact event date previously verified and replayed in the v1.3 diagnostic."
                )
                fully_prefilled += 1
            else:
                partial_dates += 1
        prepared.append(row)
    return prepared, fully_prefilled, partial_dates


def main() -> int:
    remediation = json.loads(REMEDIATION_MANIFEST.read_text(encoding="utf-8"))
    if sha256(TEMPLATE) != remediation["output_sha256"][TEMPLATE.name]:
        raise ValueError("Locked v1.3 true-value template changed")
    date_summary = json.loads(DATE_SUMMARY.read_text(encoding="utf-8"))
    if date_summary["status"] != "diagnostic_spent_sample_only":
        raise ValueError("Date-remediation replay does not have the expected status")

    rows = read_csv(TEMPLATE)
    prepared, fully_prefilled, partial_dates = prepare(rows, read_csv(DATE_REPLAY))
    columns = list(rows[0])
    with REVIEW.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(prepared)
    print(f"Wrote {len(prepared)} rows to {REVIEW}")
    print(f"Fully pre-filled {fully_prefilled} rows")
    print(f"Pre-filled verified dates in {partial_dates} additional rows")
    print(f"Rows requiring human completion: {len(prepared) - fully_prefilled}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
