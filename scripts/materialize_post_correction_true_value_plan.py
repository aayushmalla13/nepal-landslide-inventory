#!/usr/bin/env python3
"""Materialize validated post-correction true-value decisions as an unapplied plan."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from landslide_inventory.gazetteer import district_to_province
from landslide_inventory.gazetteer_municipality import municipality_districts

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "outputs"
RELEASE = (
    ROOT
    / "data"
    / "releases"
    / "nepal_landslide_inventory_v0.7.0_candidate_20260916"
    / "canonical_events_final.csv"
)
COMPLETED = OUTPUT / "post_correction_remediation_BATCH_TRUE_VALUE_REVIEW_COMPLETED.csv"
VALIDATION = OUTPUT / "post_correction_true_value_review_validation.json"
IDENTITY_MANIFEST = OUTPUT / "post_correction_identity_plan_manifest.json"
IDENTITY_REMOVE = OUTPUT / "post_correction_identity_plan_REMOVE_OLD_EVENTS.csv"
IDENTITY_MERGES = OUTPUT / "post_correction_identity_plan_MERGES_EXISTING.csv"
CORRECTIONS_OUTPUT = OUTPUT / "post_correction_true_value_plan_CORRECTIONS.csv"
EXCLUSIONS_OUTPUT = OUTPUT / "post_correction_true_value_plan_EXCLUSIONS.csv"
NO_CHANGE_OUTPUT = OUTPUT / "post_correction_true_value_plan_NO_CHANGE.csv"
MANIFEST_OUTPUT = OUTPUT / "post_correction_true_value_plan_manifest.json"
REPORT_OUTPUT = OUTPUT / "post_correction_true_value_plan_report.md"

FIELDS = {
    "event_date": ("event_date_ad", "proposed_event_date"),
    "district": ("district", "proposed_district"),
    "municipality": ("municipality", "proposed_municipality"),
    "event_type": ("event_type", "proposed_event_type"),
    "hazard_type": ("hazard_type", "proposed_hazard_type"),
    "deaths": ("deaths", "proposed_deaths"),
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]], columns: list[str]) -> None:
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


def semantic_source_value(name: str, value: str) -> str:
    if name == "deaths" and not value:
        return "not_reported"
    return value


def plan_value(name: str, entered: str, original: str) -> str:
    if not entered or entered == "keep_original":
        return semantic_source_value(name, original)
    if name == "municipality" and entered == "not_established":
        return ""
    return entered


def materialize(
    completed: list[dict[str, str]], source: list[dict[str, str]]
) -> tuple[
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
]:
    source_by_id = {row["event_id"]: row for row in source}
    corrections: list[dict[str, object]] = []
    exclusions: list[dict[str, object]] = []
    no_change: list[dict[str, object]] = []

    for row in completed:
        queue_id = row["queue_id"]
        event_id = row["event_id"]
        if event_id not in source_by_id:
            raise ValueError(f"{queue_id}: reviewed event is absent from source release.")
        original = source_by_id[event_id]
        common = {
            "queue_id": queue_id,
            "row_id": row["row_id"],
            "event_id": event_id,
            "representative_url": original["representative_url"],
            "recommended_actions": row["recommended_actions"],
            "reviewed_by": row["reviewed_by"],
            "review_notes": row["review_notes"],
        }
        action = row["reviewed_action"]
        if action == "exclude_candidate":
            exclusions.append(
                {
                    **common,
                    "event_date": original["event_date_ad"],
                    "district": original["district"],
                    "production_status": "planned_exclude_existing_event",
                }
            )
            continue
        if action != "retain":
            raise ValueError(f"{queue_id}: unresolved reviewed_action.")

        before: dict[str, str] = {}
        after: dict[str, str] = {}
        changed_fields: list[str] = []
        for name, (source_field, proposed_field) in FIELDS.items():
            source_value = original[source_field]
            before[name] = semantic_source_value(name, source_value)
            after[name] = plan_value(name, row[proposed_field].strip(), source_value)
            if after[name] != before[name]:
                changed_fields.append(name)

        municipality = after["municipality"]
        if municipality and municipality_districts(municipality):
            if after["district"] not in municipality_districts(municipality):
                raise ValueError(f"{queue_id}: final municipality and district conflict.")

        result = {
            **common,
            "changed_fields_json": json.dumps(changed_fields, ensure_ascii=False),
            **{f"original_{key}": value for key, value in before.items()},
            "original_province": original["province"],
            **{f"final_{key}": value for key, value in after.items()},
            "final_province": district_to_province(after["district"]),
        }
        if changed_fields:
            corrections.append(
                {**result, "production_status": "planned_true_value_correction"}
            )
        else:
            no_change.append(
                {**result, "production_status": "reviewed_retain_no_change"}
            )
    return corrections, exclusions, no_change


def main() -> None:
    validation = json.loads(VALIDATION.read_text(encoding="utf-8"))
    if validation["status"] != "validated_true_values_not_yet_applied":
        raise ValueError("Post-correction true-value review is not release-safe.")
    if sha256(COMPLETED) != validation["input_sha256"][COMPLETED.name]:
        raise ValueError("Completed review differs from its validation provenance.")

    identity = json.loads(IDENTITY_MANIFEST.read_text(encoding="utf-8"))
    reviewed = read_csv(COMPLETED)
    reviewed_ids = {row["event_id"] for row in reviewed}
    removed_ids = {row["old_event_id"] for row in read_csv(IDENTITY_REMOVE)}
    merge_targets = {
        row["merge_existing_event_id"] for row in read_csv(IDENTITY_MERGES)
    }
    overlap = reviewed_ids & (removed_ids | merge_targets)
    if overlap:
        raise ValueError(f"True-value rows overlap the identity plan: {sorted(overlap)}")

    corrections, exclusions, no_change = materialize(reviewed, read_csv(RELEASE))
    correction_columns = list(corrections[0])
    exclusion_columns = list(exclusions[0])
    no_change_columns = list(no_change[0])
    write_csv(CORRECTIONS_OUTPUT, corrections, correction_columns)
    write_csv(EXCLUSIONS_OUTPUT, exclusions, exclusion_columns)
    write_csv(NO_CHANGE_OUTPUT, no_change, no_change_columns)

    planned_rows = identity["planned_identity_layer_rows"] - len(exclusions)
    manifest = {
        "review_rows": len(reviewed),
        "planned_corrections": len(corrections),
        "planned_exclusions": len(exclusions),
        "reviewed_no_change": len(no_change),
        "identity_overlap_count": 0,
        "identity_plan_rows_before_true_value_exclusions": identity[
            "planned_identity_layer_rows"
        ],
        "provisional_rows_after_true_value_plan": planned_rows,
        "net_delta_from_source_inventory": planned_rows - identity["source_inventory_rows"],
        "input_sha256": {
            COMPLETED.name: sha256(COMPLETED),
            VALIDATION.name: sha256(VALIDATION),
            IDENTITY_MANIFEST.name: sha256(IDENTITY_MANIFEST),
            IDENTITY_REMOVE.name: sha256(IDENTITY_REMOVE),
            IDENTITY_MERGES.name: sha256(IDENTITY_MERGES),
            str(RELEASE.relative_to(ROOT)): sha256(RELEASE),
        },
        "output_sha256": {
            CORRECTIONS_OUTPUT.name: sha256(CORRECTIONS_OUTPUT),
            EXCLUSIONS_OUTPUT.name: sha256(EXCLUSIONS_OUTPUT),
            NO_CHANGE_OUTPUT.name: sha256(NO_CHANGE_OUTPUT),
        },
        "status": "post_correction_true_value_plan_unapplied_attributes_pending",
    }
    MANIFEST_OUTPUT.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    REPORT_OUTPUT.write_text(
        "\n".join(
            [
                "# Post-correction true-value plan",
                "",
                f"Reviewed rows: {len(reviewed)}",
                f"Planned corrections: {len(corrections)}",
                f"Planned exclusions: {len(exclusions)}",
                f"Reviewed no-change rows: {len(no_change)}",
                "Identity-plan overlap: 0",
                f"Provisional inventory rows: {planned_rows}",
                "Net change from the 2,904-row source candidate: "
                f"{planned_rows - identity['source_inventory_rows']:+d}",
                "",
                "This plan remains unapplied. Complete the structured-attribute gate",
                "before assembling a new corrected candidate.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"Wrote {len(corrections)} corrections to {CORRECTIONS_OUTPUT}")
    print(f"Wrote {len(exclusions)} exclusions to {EXCLUSIONS_OUTPUT}")
    print(f"Wrote {len(no_change)} no-change decisions to {NO_CHANGE_OUTPUT}")
    print(f"Wrote {MANIFEST_OUTPUT}")


if __name__ == "__main__":
    main()
