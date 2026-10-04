#!/usr/bin/env python3
"""Validate the completed post-correction true-value review gate."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import date
from pathlib import Path

from landslide_inventory.gazetteer import all_districts
from landslide_inventory.gazetteer_municipality import (
    load_municipality_gazetteers,
    municipality_districts,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "outputs"
RELEASE = (
    ROOT
    / "data"
    / "releases"
    / "nepal_landslide_inventory_v0.7.0_candidate_20260916"
    / "canonical_events_final.csv"
)
TEMPLATE = OUTPUT / "post_correction_remediation_BATCH_TRUE_VALUE_REVIEW.csv"
REMEDIATION_MANIFEST = OUTPUT / "post_correction_remediation_manifest.json"
DEFAULT_COMPLETED = (
    OUTPUT / "post_correction_remediation_BATCH_TRUE_VALUE_REVIEW_COMPLETED.csv"
)
VALIDATION_OUTPUT = OUTPUT / "post_correction_true_value_review_validation.json"

EDITABLE_COLUMNS = {
    "proposed_event_date",
    "proposed_district",
    "proposed_municipality",
    "proposed_event_type",
    "proposed_hazard_type",
    "proposed_deaths",
    "reviewed_action",
    "reviewed_by",
    "review_notes",
}
FIELD_ACTIONS = {
    "proposed_event_date": ("correct_date", "review_date"),
    "proposed_district": ("correct_district", "review_district"),
    "proposed_municipality": ("correct_municipality", "review_municipality"),
    "proposed_event_type": ("correct_event_type", "review_event_type"),
    "proposed_hazard_type": ("correct_hazard_type", "review_hazard_type"),
    "proposed_deaths": ("correct_deaths", "review_deaths", "clear_deaths"),
}
CLAIMED_FIELDS = {
    "proposed_event_date": "claimed_event_date",
    "proposed_district": "claimed_district",
    "proposed_municipality": "claimed_municipality",
    "proposed_event_type": "claimed_event_type",
    "proposed_hazard_type": "claimed_hazard_type",
    "proposed_deaths": "claimed_deaths",
}
EVENT_TYPES = {"landslide", "road_obstruction", "other"}
HAZARD_TYPES = {"landslide", "debris_flow", "rockfall", "other"}
REVIEW_SENTINELS = {"keep_original", "unclear"}
NULL_SENTINELS = {"not_established"}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalized_value(field: str, value: str) -> str:
    value = value.strip()
    if field == "proposed_deaths":
        return (value or "not_reported").lower()
    if field == "proposed_municipality" and value == "not_established":
        return ""
    return value.casefold()


def validate_value(
    field: str,
    value: str,
    queue_id: str,
    *,
    district: str,
    min_date: date,
    max_date: date,
) -> None:
    if field == "proposed_event_date":
        try:
            parsed = date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(f"{queue_id}: proposed_event_date must use YYYY-MM-DD.") from exc
        if not min_date <= parsed <= max_date:
            raise ValueError(
                f"{queue_id}: proposed_event_date is outside the source release period."
            )
    elif field == "proposed_district":
        if value not in set(all_districts()):
            raise ValueError(f"{queue_id}: proposed_district is not canonical.")
    elif field == "proposed_municipality":
        if value == "not_established":
            return
        gazetteer = load_municipality_gazetteers()
        if value not in gazetteer.district_by_canonical:
            raise ValueError(f"{queue_id}: proposed_municipality is not canonical.")
        if district and district not in municipality_districts(value):
            raise ValueError(
                f"{queue_id}: proposed_municipality is inconsistent with district {district}."
            )
    elif field == "proposed_event_type" and value not in EVENT_TYPES:
        raise ValueError(f"{queue_id}: invalid proposed_event_type.")
    elif field == "proposed_hazard_type" and value not in HAZARD_TYPES:
        raise ValueError(f"{queue_id}: invalid proposed_hazard_type.")
    elif field == "proposed_deaths":
        if value == "not_reported":
            return
        try:
            if int(value) < 0:
                raise ValueError
        except ValueError as exc:
            raise ValueError(
                f"{queue_id}: proposed_deaths must be a count or not_reported."
            ) from exc


def validate(
    completed: list[dict[str, str]],
    template: list[dict[str, str]],
    release: list[dict[str, str]],
) -> dict[str, object]:
    if len(completed) != len(template):
        raise ValueError(f"Expected {len(template)} review rows, found {len(completed)}.")
    if list(completed[0]) != list(template[0]):
        raise ValueError("Completed review columns differ from the template.")
    if [row["queue_id"] for row in completed] != [row["queue_id"] for row in template]:
        raise ValueError("Queue IDs or row order differ from the template.")

    release_by_id = {row["event_id"]: row for row in release}
    release_dates = [date.fromisoformat(row["event_date_ad"]) for row in release]
    min_date, max_date = min(release_dates), max(release_dates)
    action_counts: Counter[str] = Counter()
    unresolved_rows: list[str] = []
    retained_no_change_rows: list[str] = []
    changed_fields: Counter[str] = Counter()

    for row, blank in zip(completed, template, strict=True):
        queue_id = row["queue_id"]
        for column in blank:
            if column not in EDITABLE_COLUMNS and row.get(column, "") != blank.get(column, ""):
                raise ValueError(f"{queue_id}: frozen column {column} changed.")
        if row["event_id"] not in release_by_id:
            raise ValueError(f"{queue_id}: event_id is absent from the source release.")

        record_action = row["reviewed_action"].strip()
        if record_action not in {"retain", "exclude_candidate", "unclear"}:
            raise ValueError(f"{queue_id}: invalid or blank reviewed_action.")
        if not row["reviewed_by"].strip() or not row["review_notes"].strip():
            raise ValueError(f"{queue_id}: reviewed_by and review_notes are required.")
        action_counts[record_action] += 1

        if record_action != "retain":
            if any(row[field].strip() for field in FIELD_ACTIONS):
                raise ValueError(f"{queue_id}: non-retained rows must leave proposed values blank.")
            if record_action == "unclear":
                unresolved_rows.append(queue_id)
            continue

        actions = set(row["recommended_actions"].split(";"))
        effective_district = row["proposed_district"].strip() or row["claimed_district"].strip()
        row_changed = False
        kept_original = False
        for field, matching_actions in FIELD_ACTIONS.items():
            value = row[field].strip()
            applicable_actions = actions.intersection(matching_actions)
            if not applicable_actions:
                if value:
                    raise ValueError(f"{queue_id}: {field} has no matching recommended action.")
                continue
            if not value:
                raise ValueError(f"{queue_id}: {field} is required for a retained row.")

            is_review = any(action.startswith("review_") for action in applicable_actions)
            if value in REVIEW_SENTINELS:
                if value == "unclear":
                    if not is_review:
                        raise ValueError(
                            f"{queue_id}: confirmed correction {field} cannot remain unclear."
                        )
                    unresolved_rows.append(queue_id)
                else:
                    kept_original = True
                continue
            if value in NULL_SENTINELS and field != "proposed_municipality":
                raise ValueError(f"{queue_id}: {value} is not valid for {field}.")

            validate_value(
                field,
                value,
                queue_id,
                district=effective_district,
                min_date=min_date,
                max_date=max_date,
            )
            claimed = row[CLAIMED_FIELDS[field]]
            if normalized_value(field, value) != normalized_value(field, claimed):
                row_changed = True
                changed_fields[field.removeprefix("proposed_")] += 1
            elif is_review:
                kept_original = True
            elif any(
                action.startswith("correct_") or action == "clear_deaths"
                for action in applicable_actions
            ):
                raise ValueError(
                    f"{queue_id}: confirmed correction {field} did not change the claim."
                )

        existence_confirmed = "review_event_existence" in actions
        if not row_changed and (kept_original or existence_confirmed):
            retained_no_change_rows.append(queue_id)
        elif not row_changed:
            raise ValueError(f"{queue_id}: retained decision makes no material change.")

    unresolved_rows = sorted(set(unresolved_rows))
    return {
        "review_rows": len(completed),
        "record_action_counts": dict(action_counts),
        "changed_field_counts": dict(changed_fields),
        "retained_no_change_rows": retained_no_change_rows,
        "retained_no_change_count": len(retained_no_change_rows),
        "unresolved_rows": unresolved_rows,
        "unresolved_count": len(unresolved_rows),
        "source_release_date_extent": [min_date.isoformat(), max_date.isoformat()],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("completed", nargs="?", type=Path, default=DEFAULT_COMPLETED)
    args = parser.parse_args()

    manifest = json.loads(REMEDIATION_MANIFEST.read_text(encoding="utf-8"))
    if sha256(TEMPLATE) != manifest["output_sha256"][TEMPLATE.name]:
        raise ValueError("True-value template differs from the remediation manifest.")
    result = validate(read_csv(args.completed), read_csv(TEMPLATE), read_csv(RELEASE))
    result["input_sha256"] = {
        args.completed.name: sha256(args.completed),
        TEMPLATE.name: sha256(TEMPLATE),
        REMEDIATION_MANIFEST.name: sha256(REMEDIATION_MANIFEST),
        str(RELEASE.relative_to(ROOT)): sha256(RELEASE),
    }
    result["status"] = (
        "blocked_unresolved_true_values"
        if result["unresolved_count"]
        else "validated_true_values_not_yet_applied"
    )
    VALIDATION_OUTPUT.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"Validated {result['review_rows']} post-correction true-value decisions.")
    print(f"Status: {result['status']}")
    print(f"Wrote {VALIDATION_OUTPUT}")


if __name__ == "__main__":
    main()
