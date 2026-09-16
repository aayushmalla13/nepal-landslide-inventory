#!/usr/bin/env python3
"""Validate adjudication and merge it into the canonical event audit."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "outputs"
FIRST_COMPLETED = OUTPUT / "canonical_event_audit_COMPLETED.csv"
ADJUDICATION_TEMPLATE = OUTPUT / "canonical_event_audit_ADJUDICATE.csv"
AGREEMENT = OUTPUT / "canonical_event_audit_interannotator_agreement.json"
DEFAULT_COMPLETED = OUTPUT / "canonical_event_audit_ADJUDICATE_COMPLETED.csv"
MERGED_OUTPUT = OUTPUT / "canonical_event_audit_ADJUDICATED.csv"
MANIFEST_OUTPUT = OUTPUT / "canonical_event_audit_adjudication_manifest.json"

FROZEN_COLUMNS = (
    "adjudication_id", "event_id", "claimed_event_date", "claimed_district",
    "claimed_municipality", "claimed_event_type", "claimed_hazard_type",
    "claimed_deaths", "claimed_missing", "claimed_injured",
    "cluster_article_count", "representative_title", "representative_url",
    "disagreement_fields", "first_event_really_happened",
    "first_one_physical_event", "first_district_correct", "first_date_correct",
    "first_municipality_correct", "first_event_type_true",
    "first_hazard_type_true", "first_deaths_true",
    "first_duplicate_merge_correct", "first_annotator", "first_notes",
    "second_event_really_happened", "second_one_physical_event",
    "second_district_correct", "second_date_correct",
    "second_municipality_correct", "second_event_type_true",
    "second_hazard_type_true", "second_deaths_true",
    "second_duplicate_merge_correct", "second_annotator", "second_notes",
    "article_evidence",
)
REVIEW_FIELDS = (
    "event_really_happened", "one_physical_event", "district_correct",
    "date_correct", "municipality_correct", "event_type_true",
    "hazard_type_true", "deaths_true", "duplicate_merge_correct",
)
YES_NO_UNCLEAR = {"yes", "no", "unclear"}
EVENT_TYPES = {"landslide", "road_obstruction", "other", "unclear"}
HAZARD_TYPES = {"landslide", "debris_flow", "rockfall", "other", "unclear"}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
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


def normalized(row: dict[str, str], field: str) -> str:
    return row.get(f"final_{field}", "").strip().lower()


def validate(
    completed: list[dict[str, str]],
    template: list[dict[str, str]],
    expected_template_hash: str,
) -> None:
    if sha256(ADJUDICATION_TEMPLATE) != expected_template_hash:
        raise ValueError("Blank adjudication sheet differs from the agreement manifest.")
    if len(completed) != len(template):
        raise ValueError(f"Expected {len(template)} adjudication rows, found {len(completed)}.")
    if [row["adjudication_id"] for row in completed] != [row["adjudication_id"] for row in template]:
        raise ValueError("Adjudication row IDs or order differ from the blank sheet.")

    for row, blank in zip(completed, template, strict=True):
        row_id = row["adjudication_id"]
        for column in FROZEN_COLUMNS:
            if row.get(column, "") != blank.get(column, ""):
                raise ValueError(f"{row_id}: frozen column {column} changed.")
        if not row.get("adjudicator", "").strip():
            raise ValueError(f"{row_id}: adjudicator is blank.")
        event = normalized(row, "event_really_happened")
        if event not in YES_NO_UNCLEAR:
            raise ValueError(f"{row_id}: invalid final_event_really_happened.")
        downstream = REVIEW_FIELDS[1:]
        if event != "yes":
            if any(normalized(row, field) for field in downstream):
                raise ValueError(f"{row_id}: downstream final fields must be blank unless the event is yes.")
            continue
        for field in ("one_physical_event", "district_correct", "date_correct"):
            if normalized(row, field) not in YES_NO_UNCLEAR:
                raise ValueError(f"{row_id}: invalid or blank final_{field}.")
        municipality = normalized(row, "municipality_correct")
        if row["claimed_municipality"].strip() and municipality not in YES_NO_UNCLEAR:
            raise ValueError(f"{row_id}: final_municipality_correct is required.")
        if not row["claimed_municipality"].strip() and municipality:
            raise ValueError(f"{row_id}: final_municipality_correct must be blank without a claim.")
        if normalized(row, "event_type_true") not in EVENT_TYPES:
            raise ValueError(f"{row_id}: invalid final_event_type_true.")
        if normalized(row, "hazard_type_true") not in HAZARD_TYPES:
            raise ValueError(f"{row_id}: invalid final_hazard_type_true.")
        deaths = normalized(row, "deaths_true")
        if deaths not in {"unclear", "not_reported"}:
            try:
                if int(deaths) < 0:
                    raise ValueError
            except ValueError as exc:
                raise ValueError(f"{row_id}: invalid final_deaths_true.") from exc
        duplicate = normalized(row, "duplicate_merge_correct")
        if int(row["cluster_article_count"]) > 1 and duplicate not in YES_NO_UNCLEAR:
            raise ValueError(f"{row_id}: final_duplicate_merge_correct is required.")
        if int(row["cluster_article_count"]) == 1 and duplicate != "not_applicable":
            raise ValueError(f"{row_id}: use not_applicable for a one-article cluster.")


def merge(
    first: list[dict[str, str]], completed: list[dict[str, str]]
) -> list[dict[str, str]]:
    adjudicated_by_event = {row["event_id"]: row for row in completed}
    if len(adjudicated_by_event) != len(completed):
        raise ValueError("Adjudication contains duplicate event IDs.")
    first_event_ids = {row["event_id"] for row in first}
    unknown = set(adjudicated_by_event) - first_event_ids
    if unknown:
        raise ValueError(f"Adjudication contains unknown event IDs: {sorted(unknown)}")

    merged = []
    for source in first:
        row = dict(source)
        adjudicated = adjudicated_by_event.get(source["event_id"])
        if adjudicated:
            for field in REVIEW_FIELDS:
                row[field] = adjudicated[f"final_{field}"].strip()
            row["annotator"] = adjudicated["adjudicator"].strip()
            row["notes"] = adjudicated["adjudication_notes"].strip()
        merged.append(row)
    return merged


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("completed", nargs="?", type=Path, default=DEFAULT_COMPLETED)
    args = parser.parse_args()

    agreement = json.loads(AGREEMENT.read_text(encoding="utf-8"))
    template = read_csv(ADJUDICATION_TEMPLATE)
    completed = read_csv(args.completed)
    first = read_csv(FIRST_COMPLETED)
    validate(completed, template, agreement["outputs"][ADJUDICATION_TEMPLATE.name])
    merged = merge(first, completed)
    write_csv(MERGED_OUTPUT, merged, list(first[0]))

    manifest = {
        "audit": agreement["audit"],
        "sample_rows": len(merged),
        "adjudicated_rows": len(completed),
        "unchanged_agreement_rows": len(merged) - len(completed),
        "adjudicators": sorted({row["adjudicator"].strip() for row in completed}),
        "inputs": {
            FIRST_COMPLETED.name: sha256(FIRST_COMPLETED),
            AGREEMENT.name: sha256(AGREEMENT),
            ADJUDICATION_TEMPLATE.name: sha256(ADJUDICATION_TEMPLATE),
            args.completed.name: sha256(args.completed),
        },
        "outputs": {MERGED_OUTPUT.name: sha256(MERGED_OUTPUT)},
    }
    MANIFEST_OUTPUT.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Validated {len(completed)} adjudicated rows.")
    print(f"Wrote {MERGED_OUTPUT}")
    print(f"Wrote {MANIFEST_OUTPUT}")


if __name__ == "__main__":
    main()
