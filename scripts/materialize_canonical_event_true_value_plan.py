#!/usr/bin/env python3
"""Materialize validated true-value decisions as an unapplied release plan."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from landslide_inventory.gazetteer import district_to_province

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "outputs"
RELEASE_DIR = ROOT / "data" / "releases" / "nepal_landslide_inventory_v0.6.0_v7_20260915"
COMPLETED = OUTPUT / "canonical_event_true_value_REVIEW_COMPLETED.csv"
VALIDATION = OUTPUT / "canonical_event_true_value_review_validation.json"
FROZEN_CANONICAL = RELEASE_DIR / "canonical_events_final.csv"
IDENTITY_REMOVE = OUTPUT / "canonical_event_identity_plan_REMOVE_OLD_EVENTS.csv"
IDENTITY_MERGES = OUTPUT / "canonical_event_identity_plan_MERGES.csv"
IDENTITY_MANIFEST = OUTPUT / "canonical_event_identity_plan_manifest.json"
CORRECTIONS_OUTPUT = OUTPUT / "canonical_event_true_value_plan_CORRECTIONS.csv"
EXCLUSIONS_OUTPUT = OUTPUT / "canonical_event_true_value_plan_EXCLUSIONS.csv"
MANIFEST_OUTPUT = OUTPUT / "canonical_event_true_value_plan_manifest.json"
REPORT_OUTPUT = OUTPUT / "canonical_event_true_value_plan_report.md"

FIELDS = {
    "event_date": ("event_date_ad", "final_event_date"),
    "district": ("district", "final_district"),
    "municipality": ("municipality", "final_municipality"),
    "event_type": ("event_type", "final_event_type"),
    "hazard_type": ("hazard_type", "final_hazard_type"),
    "deaths": ("deaths", "final_deaths"),
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


def plan_value(value: str, original: str, *, deaths: bool = False) -> str:
    if value == "keep_original":
        return original or ("not_reported" if deaths else "")
    return value


def materialize(
    completed: list[dict[str, str]], frozen: list[dict[str, str]]
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    frozen_by_id = {row["event_id"]: row for row in frozen}
    corrections: list[dict[str, object]] = []
    exclusions: list[dict[str, object]] = []
    for row in completed:
        event_id = row["event_id"]
        if event_id not in frozen_by_id:
            raise ValueError(f"Reviewed event is absent from frozen inventory: {event_id}")
        original = frozen_by_id[event_id]
        common = {
            "candidate_id": row["candidate_id"],
            "event_id": event_id,
            "representative_url": original["representative_url"],
            "reviewed_by": row["reviewed_by"],
            "review_notes": row["review_notes"],
        }
        if row["final_record_action"] == "exclude_candidate":
            exclusions.append(
                {
                    **common,
                    "event_date": original["event_date_ad"],
                    "district": original["district"],
                    "recommended_actions": row["recommended_actions"],
                    "production_status": "planned_exclude_existing_event",
                }
            )
            continue
        if row["final_record_action"] != "retain":
            raise ValueError(f"Unresolved record action for {row['candidate_id']}")

        before: dict[str, str] = {}
        after: dict[str, str] = {}
        changed_fields: list[str] = []
        for name, (source_field, final_field) in FIELDS.items():
            source_value = original[source_field]
            before[name] = source_value or ("not_reported" if name == "deaths" else "")
            entered = row[final_field].strip()
            final_value = (
                plan_value(entered, source_value, deaths=name == "deaths")
                if entered
                else before[name]
            )
            after[name] = final_value
            if final_value != before[name]:
                changed_fields.append(name)
        if not changed_fields:
            raise ValueError(f"Retained decision makes no material change: {row['candidate_id']}")
        corrections.append(
            {
                **common,
                "recommended_actions": row["recommended_actions"],
                "changed_fields_json": json.dumps(changed_fields, ensure_ascii=False),
                **{f"original_{key}": value for key, value in before.items()},
                "original_province": original["province"],
                **{f"final_{key}": value for key, value in after.items()},
                "final_province": district_to_province(after["district"]),
                "production_status": "planned_true_value_correction",
            }
        )
    return corrections, exclusions


def main() -> None:
    validation = json.loads(VALIDATION.read_text(encoding="utf-8"))
    if validation["status"] != "validated_true_values_not_yet_applied":
        raise ValueError("True-value review is not release-safe.")
    if sha256(COMPLETED) != validation["inputs"][COMPLETED.name]:
        raise ValueError("Completed true-value review differs from validation provenance.")
    identity = json.loads(IDENTITY_MANIFEST.read_text(encoding="utf-8"))
    reviewed = read_csv(COMPLETED)
    reviewed_ids = {row["event_id"] for row in reviewed}
    removed_ids = {row["old_event_id"] for row in read_csv(IDENTITY_REMOVE)}
    merge_targets = {row["merge_target_event_id"] for row in read_csv(IDENTITY_MERGES)}
    overlap = reviewed_ids & (removed_ids | merge_targets)
    if overlap:
        raise ValueError(f"True-value rows overlap the identity plan: {sorted(overlap)}")

    corrections, exclusions = materialize(reviewed, read_csv(FROZEN_CANONICAL))
    write_csv(CORRECTIONS_OUTPUT, corrections, list(corrections[0]))
    write_csv(EXCLUSIONS_OUTPUT, exclusions, list(exclusions[0]))
    planned_rows = identity["planned_identity_layer_rows"] - len(exclusions)
    manifest = {
        "review_rows": len(reviewed),
        "planned_corrections": len(corrections),
        "planned_exclusions": len(exclusions),
        "identity_plan_rows_before_true_value_exclusions": identity["planned_identity_layer_rows"],
        "provisional_rows_after_true_value_plan": planned_rows,
        "net_delta_from_frozen_inventory": planned_rows - identity["frozen_inventory_rows"],
        "identity_overlap_count": 0,
        "inputs": {
            COMPLETED.name: sha256(COMPLETED),
            VALIDATION.name: sha256(VALIDATION),
            str(FROZEN_CANONICAL.relative_to(ROOT)): sha256(FROZEN_CANONICAL),
            IDENTITY_MANIFEST.name: sha256(IDENTITY_MANIFEST),
            IDENTITY_REMOVE.name: sha256(IDENTITY_REMOVE),
            IDENTITY_MERGES.name: sha256(IDENTITY_MERGES),
        },
        "outputs": {
            CORRECTIONS_OUTPUT.name: sha256(CORRECTIONS_OUTPUT),
            EXCLUSIONS_OUTPUT.name: sha256(EXCLUSIONS_OUTPUT),
        },
        "status": "true_value_plan_unapplied_structured_attribute_gate_pending",
    }
    MANIFEST_OUTPUT.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    REPORT_OUTPUT.write_text(
        "\n".join(
            [
                "# Canonical event true-value release plan",
                "",
                f"Reviewed rows: {len(reviewed)}",
                f"Planned corrections: {len(corrections)}",
                f"Planned exclusions: {len(exclusions)}",
                "Identity-plan overlap: 0",
                f"Provisional inventory rows: {planned_rows}",
                "Net change from the frozen inventory: "
                f"{planned_rows - identity['frozen_inventory_rows']:+d}",
                "",
                "This plan is not applied. The structured-attribute gate must be completed",
                "before a corrected release is built.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"Wrote {len(corrections)} rows to {CORRECTIONS_OUTPUT}")
    print(f"Wrote {len(exclusions)} rows to {EXCLUSIONS_OUTPUT}")
    print(f"Wrote {MANIFEST_OUTPUT}")
    print(f"Wrote {REPORT_OUTPUT}")


if __name__ == "__main__":
    main()
