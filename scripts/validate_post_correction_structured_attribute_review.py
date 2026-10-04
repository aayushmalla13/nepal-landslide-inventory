#!/usr/bin/env python3
"""Validate the completed post-correction structured-attribute review."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "outputs"
TEMPLATE = OUTPUT / "post_correction_structured_attribute_REVIEW.csv"
MANIFEST = OUTPUT / "post_correction_structured_attribute_review_manifest.json"
DEFAULT_COMPLETED = OUTPUT / "post_correction_structured_attribute_REVIEW_COMPLETED.csv"
VALIDATION_OUTPUT = OUTPUT / "post_correction_structured_attribute_review_validation.json"
FINAL_COLUMNS = {
    "final_record_action",
    "final_event_type",
    "final_hazard_type",
    "final_deaths",
    "reviewed_by",
    "review_notes",
}
FIELDS = {
    "final_event_type": ({"correct_event_type"}, "claimed_event_type"),
    "final_hazard_type": ({"correct_hazard_type"}, "claimed_hazard_type"),
    "final_deaths": ({"correct_deaths", "clear_deaths"}, "claimed_deaths"),
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


def validate_value(field: str, value: str, queue_id: str) -> None:
    if field == "final_event_type" and value not in EVENT_TYPES:
        raise ValueError(f"{queue_id}: invalid final_event_type.")
    if field == "final_hazard_type" and value not in HAZARD_TYPES:
        raise ValueError(f"{queue_id}: invalid final_hazard_type.")
    if field == "final_deaths":
        if value == "not_reported":
            return
        try:
            if int(value) < 0:
                raise ValueError
        except ValueError as exc:
            raise ValueError(
                f"{queue_id}: final_deaths must be a count or not_reported."
            ) from exc


def validate(
    completed: list[dict[str, str]], template: list[dict[str, str]]
) -> dict[str, object]:
    if len(completed) != len(template):
        raise ValueError(f"Expected {len(template)} review rows, found {len(completed)}.")
    if list(completed[0]) != list(template[0]):
        raise ValueError("Completed review columns differ from the template.")
    if [row["queue_id"] for row in completed] != [row["queue_id"] for row in template]:
        raise ValueError("Queue IDs or row order differ from the template.")

    action_counts: Counter[str] = Counter()
    changed_fields: Counter[str] = Counter()
    unresolved_rows: list[str] = []
    for row, blank in zip(completed, template, strict=True):
        queue_id = row["queue_id"]
        for column in blank:
            if column not in FINAL_COLUMNS and row.get(column, "") != blank.get(column, ""):
                raise ValueError(f"{queue_id}: frozen column {column} changed.")

        record_action = row["final_record_action"].strip()
        if record_action not in {"retain", "exclude_candidate", "unclear"}:
            raise ValueError(f"{queue_id}: invalid or blank final_record_action.")
        if not row["reviewed_by"].strip() or not row["review_notes"].strip():
            raise ValueError(f"{queue_id}: reviewed_by and review_notes are required.")
        action_counts[record_action] += 1

        if record_action != "retain":
            if any(row[field].strip() for field in FIELDS):
                raise ValueError(f"{queue_id}: non-retained rows must leave final values blank.")
            if record_action == "unclear":
                unresolved_rows.append(queue_id)
            continue

        actions = set(row["recommended_actions"].split(";"))
        for field, (required_actions, claimed_field) in FIELDS.items():
            value = row[field].strip()
            if actions.isdisjoint(required_actions):
                if value:
                    raise ValueError(f"{queue_id}: {field} has no matching action.")
                continue
            if not value or value == "unclear":
                unresolved_rows.append(queue_id)
                continue
            validate_value(field, value, queue_id)
            claimed = row[claimed_field].strip()
            left = normalized_deaths(value) if field == "final_deaths" else value.casefold()
            right = (
                normalized_deaths(claimed)
                if field == "final_deaths"
                else claimed.casefold()
            )
            if left == right:
                raise ValueError(
                    f"{queue_id}: confirmed correction {field} did not change the claim."
                )
            changed_fields[field.removeprefix("final_")] += 1

    unresolved_rows = sorted(set(unresolved_rows))
    return {
        "review_rows": len(completed),
        "record_action_counts": dict(action_counts),
        "changed_field_counts": dict(changed_fields),
        "unresolved_rows": unresolved_rows,
        "unresolved_count": len(unresolved_rows),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("completed", nargs="?", type=Path, default=DEFAULT_COMPLETED)
    args = parser.parse_args()

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if sha256(TEMPLATE) != manifest["output_sha256"][TEMPLATE.name]:
        raise ValueError("Structured-attribute template differs from its manifest.")
    result = validate(read_csv(args.completed), read_csv(TEMPLATE))
    result["input_sha256"] = {
        args.completed.name: sha256(args.completed),
        TEMPLATE.name: sha256(TEMPLATE),
        MANIFEST.name: sha256(MANIFEST),
    }
    result["status"] = (
        "blocked_unresolved_structured_attributes"
        if result["unresolved_count"]
        else "validated_structured_attributes_not_yet_applied"
    )
    VALIDATION_OUTPUT.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"Validated {result['review_rows']} structured-attribute decisions.")
    print(f"Status: {result['status']}")
    print(f"Wrote {VALIDATION_OUTPUT}")


if __name__ == "__main__":
    main()
