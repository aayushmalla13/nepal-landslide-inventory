#!/usr/bin/env python3
"""Normalize one documented death-value encoding in the v0.9 submission."""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "outputs"
COMPLETED = OUTPUT / "v09_structured_attribute_REVIEW_COMPLETED.csv"
SUBMITTED = OUTPUT / "v09_structured_attribute_REVIEW_SUBMITTED.csv"
VALIDATION = OUTPUT / "v09_structured_attribute_review_validation.json"
MANIFEST = OUTPUT / "v09_structured_attribute_normalization_manifest.json"
TARGET_QUEUE_ID = "V9R-097"
NORMALIZATION_NOTE = (
    " [Normalization: the blank claimed death value means not_reported; explicit "
    "source confirmation of no human casualties is encoded as final_deaths=0.]"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    matches = [row for row in rows if row["queue_id"] == TARGET_QUEUE_ID]
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one {TARGET_QUEUE_ID} row")
    row = matches[0]
    if row["final_record_action"] != "retain":
        raise ValueError(f"{TARGET_QUEUE_ID}: expected retain decision")
    if "correct_deaths" not in row["recommended_actions"].split(";"):
        raise ValueError(f"{TARGET_QUEUE_ID}: death correction is not requested")
    if row["claimed_deaths"].strip() or row["final_deaths"].strip():
        raise ValueError(f"{TARGET_QUEUE_ID}: expected blank claimed and final deaths")
    if "no human casualties" not in row["review_notes"].lower():
        raise ValueError(f"{TARGET_QUEUE_ID}: reviewer did not explicitly establish zero deaths")
    row["final_deaths"] = "0"
    row["review_notes"] = row["review_notes"].rstrip() + NORMALIZATION_NOTE
    return rows


def main() -> int:
    validation = json.loads(VALIDATION.read_text(encoding="utf-8"))
    if validation["status"] != "blocked_unresolved_structured_attributes":
        raise ValueError("Expected a blocked structured-attribute validation")
    if validation["unresolved_rows"] != [TARGET_QUEUE_ID]:
        raise ValueError("Normalization is allowed only for the single documented target row")
    if sha256(COMPLETED) != validation["input_sha256"][COMPLETED.name]:
        raise ValueError("Completed submission differs from blocked validation provenance")

    shutil.copyfile(COMPLETED, SUBMITTED)
    with COMPLETED.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = list(reader.fieldnames or [])
        rows = normalize(list(reader))
    with COMPLETED.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)

    manifest = {
        "normalized_rows": [TARGET_QUEUE_ID],
        "change": "final_deaths blank/not_reported -> 0",
        "submitted_sha256": sha256(SUBMITTED),
        "normalized_sha256": sha256(COMPLETED),
        "blocked_validation_sha256": sha256(VALIDATION),
        "status": "one_documented_encoding_normalization_revalidation_required",
    }
    MANIFEST.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"Preserved original submission at {SUBMITTED}")
    print(f"Normalized {TARGET_QUEUE_ID}: final_deaths=0")
    print(f"Wrote {MANIFEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
