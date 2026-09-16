#!/usr/bin/env python3
"""Validate the completed canonical-event structured-attribute review."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "outputs"
TEMPLATE = OUTPUT / "canonical_event_structured_attribute_REVIEW.csv"
MANIFEST = OUTPUT / "canonical_event_structured_attribute_review_manifest.json"
DEFAULT_COMPLETED = OUTPUT / "canonical_event_structured_attribute_REVIEW_COMPLETED.csv"
VALIDATION_OUTPUT = OUTPUT / "canonical_event_structured_attribute_review_validation.json"
FINAL_COLUMNS = {
    "final_record_action", "final_event_type", "final_hazard_type", "final_deaths",
    "reviewed_by", "review_notes",
}
FIELDS = {
    "final_event_type": ("correct_event_type", "claimed_event_type"),
    "final_hazard_type": ("correct_hazard_type", "claimed_hazard_type"),
    "final_deaths": ("correct_deaths", "claimed_deaths"),
}
EVENT_TYPES = {"landslide", "road_obstruction", "other"}
HAZARD_TYPES = {"landslide", "debris_flow", "rockfall", "other"}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalized_deaths(value: str) -> str:
    value = value.strip().lower()
    return "not_reported" if not value else value


def validate_value(field: str, value: str, row_id: str) -> None:
    if field == "final_event_type" and value not in EVENT_TYPES:
        raise ValueError(f"{row_id}: invalid final_event_type.")
    if field == "final_hazard_type" and value not in HAZARD_TYPES:
        raise ValueError(f"{row_id}: invalid final_hazard_type.")
    if field == "final_deaths":
        if value == "not_reported":
            return
        try:
            if int(value) < 0:
                raise ValueError
        except ValueError as exc:
            raise ValueError(f"{row_id}: final_deaths must be a count or not_reported.") from exc


def validate(completed: list[dict[str, str]], template: list[dict[str, str]]) -> dict[str, object]:
    if len(completed) != len(template):
        raise ValueError(f"Expected {len(template)} review rows, found {len(completed)}.")
    if [row["candidate_id"] for row in completed] != [row["candidate_id"] for row in template]:
        raise ValueError("Candidate IDs or order differ from the blank structured-attribute sheet.")
    action_counts: Counter[str] = Counter()
    unresolved = 0
    for row, blank in zip(completed, template, strict=True):
        row_id = row["candidate_id"]
        for column in blank:
            if column not in FINAL_COLUMNS and row.get(column, "") != blank.get(column, ""):
                raise ValueError(f"{row_id}: frozen column {column} changed.")
        record_action = row["final_record_action"].strip()
        if record_action not in {"retain", "exclude_candidate", "unclear"}:
            raise ValueError(f"{row_id}: invalid or blank final_record_action.")
        if not row["reviewed_by"].strip() or not row["review_notes"].strip():
            raise ValueError(f"{row_id}: reviewer and review_notes are required.")
        action_counts[record_action] += 1
        if record_action != "retain":
            if any(row[field].strip() for field in FIELDS):
                raise ValueError(f"{row_id}: non-retained record must leave final values blank.")
            unresolved += int(record_action == "unclear")
            continue
        actions = set(row["recommended_actions"].split(";"))
        for field, (required_action, claimed_field) in FIELDS.items():
            value = row[field].strip()
            if required_action not in actions:
                if value:
                    raise ValueError(f"{row_id}: {field} was filled without a matching action.")
                continue
            if not value or value == "unclear":
                unresolved += 1
                continue
            validate_value(field, value, row_id)
            claimed = row[claimed_field].strip()
            left = normalized_deaths(value) if field == "final_deaths" else value.casefold()
            right = normalized_deaths(claimed) if field == "final_deaths" else claimed.casefold()
            if left == right:
                raise ValueError(
                    f"{row_id}: confirmed correction {field} did not change the claim."
                )
    return {
        "review_rows": len(completed),
        "record_action_counts": dict(action_counts),
        "unresolved_values": unresolved,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("completed", nargs="?", type=Path, default=DEFAULT_COMPLETED)
    args = parser.parse_args()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if sha256(TEMPLATE) != manifest["outputs"][TEMPLATE.name]:
        raise ValueError("Structured-attribute review template differs from its manifest.")
    result = validate(read_csv(args.completed), read_csv(TEMPLATE))
    result["inputs"] = {
        args.completed.name: sha256(args.completed),
        TEMPLATE.name: sha256(TEMPLATE),
        MANIFEST.name: sha256(MANIFEST),
    }
    result["status"] = (
        "blocked_unresolved_structured_attributes"
        if result["unresolved_values"] else "validated_structured_attributes_not_yet_applied"
    )
    VALIDATION_OUTPUT.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"Validated {result['review_rows']} structured-attribute decisions.")
    print(f"Wrote {VALIDATION_OUTPUT}")


if __name__ == "__main__":
    main()
