#!/usr/bin/env python3
"""Create a reordered, answer-free second review of the canonical event audit."""

from __future__ import annotations

import csv
import hashlib
import json
import random
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "outputs"
FIRST_TEMPLATE = OUTPUT / "canonical_event_audit_LABEL_HERE.csv"
FIRST_COMPLETED = OUTPUT / "canonical_event_audit_COMPLETED.csv"
FIRST_READING = OUTPUT / "canonical_event_audit_reading_pack.csv"

LABEL_OUTPUT = OUTPUT / "canonical_event_audit_second_LABEL_HERE.csv"
READING_OUTPUT = OUTPUT / "canonical_event_audit_second_reading_pack.csv"
MAPPING_OUTPUT = OUTPUT / "canonical_event_audit_second_mapping.csv"
MANIFEST_OUTPUT = OUTPUT / "canonical_event_audit_second_manifest.json"

SEED = 20260916
CLAIM_COLUMNS = (
    "row_id", "event_id", "claimed_event_date", "claimed_district",
    "claimed_municipality", "claimed_event_type", "claimed_hazard_type",
    "claimed_deaths", "claimed_missing", "claimed_injured",
    "cluster_article_count", "representative_title", "representative_url",
)
LABEL_COLUMNS = (
    "event_really_happened", "one_physical_event", "district_correct",
    "date_correct", "municipality_correct", "event_type_true",
    "hazard_type_true", "deaths_true", "duplicate_merge_correct",
    "annotator", "notes",
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def shuffled_ids(row_ids: list[str], seed: int = SEED) -> list[str]:
    result = sorted(row_ids)
    random.Random(seed).shuffle(result)
    return result


def blank_row(source: dict[str, str], second_row_id: str) -> dict[str, str]:
    claims = {column: source[column] for column in CLAIM_COLUMNS if column != "row_id"}
    return {"row_id": second_row_id, **claims, **{column: "" for column in LABEL_COLUMNS}}


def main() -> None:
    template = read_csv(FIRST_TEMPLATE)
    completed = read_csv(FIRST_COMPLETED)
    reading_by_id = {row["row_id"]: row for row in read_csv(FIRST_READING)}
    if len(template) != 150 or len(completed) != 150 or len(reading_by_id) != 150:
        raise ValueError("The first canonical audit artifacts must each contain 150 rows.")
    if [row["row_id"] for row in template] != [row["row_id"] for row in completed]:
        raise ValueError("The completed first review no longer matches its blank template.")
    template_by_id = {row["row_id"]: row for row in template}
    original_ids = shuffled_ids(list(template_by_id))

    labels: list[dict[str, str]] = []
    readings: list[dict[str, str]] = []
    mappings: list[dict[str, str]] = []
    for number, first_row_id in enumerate(original_ids, start=1):
        second_row_id = f"CEA2-{number:03d}"
        source = template_by_id[first_row_id]
        labels.append(blank_row(source, second_row_id))
        reading = reading_by_id[first_row_id]
        readings.append(
            {
                **{column: labels[-1][column] for column in CLAIM_COLUMNS},
                "article_evidence": reading["article_evidence"],
            }
        )
        mappings.append(
            {
                "second_row_id": second_row_id,
                "first_row_id": first_row_id,
                "event_id": source["event_id"],
            }
        )

    write_csv(LABEL_OUTPUT, labels, [*CLAIM_COLUMNS, *LABEL_COLUMNS])
    write_csv(READING_OUTPUT, readings, [*CLAIM_COLUMNS, "article_evidence"])
    write_csv(MAPPING_OUTPUT, mappings, ["second_row_id", "first_row_id", "event_id"])
    manifest = {
        "audit": "canonical_event_level_second_review_v1",
        "purpose": "independent second human review and inter-rater agreement",
        "rows": len(labels),
        "seed": SEED,
        "ordering": "deterministically shuffled with new second-review row IDs",
        "blinding": "first-review labels and notes are absent from both reviewer-facing files",
        "source_sha256": {
            FIRST_TEMPLATE.name: sha256(FIRST_TEMPLATE),
            FIRST_COMPLETED.name: sha256(FIRST_COMPLETED),
            FIRST_READING.name: sha256(FIRST_READING),
        },
        "outputs": {
            LABEL_OUTPUT.name: sha256(LABEL_OUTPUT),
            READING_OUTPUT.name: sha256(READING_OUTPUT),
            MAPPING_OUTPUT.name: sha256(MAPPING_OUTPUT),
        },
    }
    MANIFEST_OUTPUT.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {len(labels)} blind rows to {LABEL_OUTPUT}")
    print(f"Wrote reordered evidence to {READING_OUTPUT}")
    print(f"Wrote private mapping to {MAPPING_OUTPUT}")
    print(f"Wrote manifest to {MANIFEST_OUTPUT}")


if __name__ == "__main__":
    main()
