#!/usr/bin/env python3
"""Normalize incompatible proposed values without changing reviewed decisions."""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/outputs"
COMPLETED = OUTPUT / "v13_remediation_BATCH_TRUE_VALUE_REVIEW_COMPLETED.csv"
SUBMITTED = OUTPUT / "v13_remediation_BATCH_TRUE_VALUE_REVIEW_SUBMITTED.csv"
LOG = OUTPUT / "v13_true_value_normalization_log.csv"
MANIFEST = OUTPUT / "v13_true_value_normalization_manifest.json"
VALUE_ALIASES = {
    ("proposed_municipality", "Besisahar Municipality"): "Besishahar Municipality",
}
INVENTORY_START = date(2015, 1, 1)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize(rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    normalized: list[dict[str, str]] = []
    changes: list[dict[str, str]] = []
    proposed = [column for column in rows[0] if column.startswith("proposed_")]
    for source in rows:
        row = dict(source)
        proposed_date = row.get("proposed_event_date", "")
        if (
            row["reviewed_action"] == "retain"
            and proposed_date
            and date.fromisoformat(proposed_date) < INVENTORY_START
        ):
            old_note = row["review_notes"]
            row["reviewed_action"] = "exclude_candidate"
            row["proposed_event_date"] = ""
            row["review_notes"] = (
                f"{old_note} Event predates the inventory's 2015 start boundary; "
                "excluded from the release."
            ).strip()
            changes.extend(
                [
                    {
                        "queue_id": row["queue_id"],
                        "column": "reviewed_action",
                        "old_value": "retain",
                        "new_value": "exclude_candidate",
                        "reason": "verified event date predates inventory scope",
                    },
                    {
                        "queue_id": row["queue_id"],
                        "column": "proposed_event_date",
                        "old_value": proposed_date,
                        "new_value": "",
                        "reason": "verified event date predates inventory scope",
                    },
                    {
                        "queue_id": row["queue_id"],
                        "column": "review_notes",
                        "old_value": old_note,
                        "new_value": row["review_notes"],
                        "reason": "document inventory-scope exclusion",
                    },
                ]
            )
        if row["reviewed_action"] != "retain":
            for column in proposed:
                if row[column]:
                    changes.append(
                        {
                            "queue_id": row["queue_id"],
                            "column": column,
                            "old_value": row[column],
                            "new_value": "",
                            "reason": "non-retained rows must not carry proposed values",
                        }
                    )
                    row[column] = ""
        else:
            for column in proposed:
                replacement = VALUE_ALIASES.get((column, row[column]))
                if replacement:
                    changes.append(
                        {
                            "queue_id": row["queue_id"],
                            "column": column,
                            "old_value": row[column],
                            "new_value": replacement,
                            "reason": "canonical gazetteer alias normalization",
                        }
                    )
                    row[column] = replacement
        normalized.append(row)
    return normalized, changes


def main() -> int:
    if not SUBMITTED.exists():
        shutil.copy2(COMPLETED, SUBMITTED)
    submitted_sha = sha256(SUBMITTED)
    with COMPLETED.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        columns = list(reader.fieldnames or [])
    normalized, changes = normalize(rows)
    prior_changes: list[dict[str, str]] = []
    if LOG.exists():
        with LOG.open(encoding="utf-8-sig", newline="") as handle:
            prior_changes = list(csv.DictReader(handle))
    all_changes = prior_changes + changes
    with COMPLETED.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(normalized)
    with LOG.open("w", encoding="utf-8", newline="") as handle:
        columns_log = ["queue_id", "column", "old_value", "new_value", "reason"]
        writer = csv.DictWriter(handle, fieldnames=columns_log)
        writer.writeheader()
        writer.writerows(all_changes)
    manifest = {
        "audit": "v13_true_value_submission_normalization_v1",
        "change_count": len(all_changes),
        "submitted_sha256": submitted_sha,
        "normalized_sha256": sha256(COMPLETED),
        "log_sha256": sha256(LOG),
        "status": "normalized_editable_fields_only_pending_validation",
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Archived submitted review at {SUBMITTED}")
    print(f"Normalized {len(changes)} additional proposed value(s)")
    print(f"Wrote {LOG}")
    print(f"Wrote {MANIFEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
