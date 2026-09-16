#!/usr/bin/env python3
"""Materialize validated structured-attribute decisions as an unapplied plan."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "outputs"
RELEASE_DIR = ROOT / "data" / "releases" / "nepal_landslide_inventory_v0.6.0_v7_20260915"
COMPLETED = OUTPUT / "canonical_event_structured_attribute_REVIEW_COMPLETED.csv"
VALIDATION = OUTPUT / "canonical_event_structured_attribute_review_validation.json"
FROZEN_CANONICAL = RELEASE_DIR / "canonical_events_final.csv"
IDENTITY_REMOVE = OUTPUT / "canonical_event_identity_plan_REMOVE_OLD_EVENTS.csv"
IDENTITY_MERGES = OUTPUT / "canonical_event_identity_plan_MERGES.csv"
TRUE_VALUE_COMPLETED = OUTPUT / "canonical_event_true_value_REVIEW_COMPLETED.csv"
TRUE_VALUE_MANIFEST = OUTPUT / "canonical_event_true_value_plan_manifest.json"
CORRECTIONS_OUTPUT = OUTPUT / "canonical_event_structured_attribute_plan_CORRECTIONS.csv"
EXCLUSIONS_OUTPUT = OUTPUT / "canonical_event_structured_attribute_plan_EXCLUSIONS.csv"
MANIFEST_OUTPUT = OUTPUT / "canonical_event_structured_attribute_plan_manifest.json"
REPORT_OUTPUT = OUTPUT / "canonical_event_structured_attribute_plan_report.md"

FIELDS = {
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
            "event_date": original["event_date_ad"],
            "district": original["district"],
            "representative_url": original["representative_url"],
            "reviewed_by": row["reviewed_by"],
            "review_notes": row["review_notes"],
        }
        if row["final_record_action"] == "exclude_candidate":
            exclusions.append(
                {
                    **common,
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
            after[name] = row[final_field].strip() or before[name]
            if after[name] != before[name]:
                changed_fields.append(name)
        if not changed_fields:
            raise ValueError(f"Retained decision makes no material change: {row['candidate_id']}")
        corrections.append(
            {
                **common,
                "recommended_actions": row["recommended_actions"],
                "changed_fields_json": json.dumps(changed_fields, ensure_ascii=False),
                **{f"original_{key}": value for key, value in before.items()},
                **{f"final_{key}": value for key, value in after.items()},
                "production_status": "planned_structured_attribute_correction",
            }
        )
    return corrections, exclusions


def main() -> None:
    validation = json.loads(VALIDATION.read_text(encoding="utf-8"))
    if validation["status"] != "validated_structured_attributes_not_yet_applied":
        raise ValueError("Structured-attribute review is not release-safe.")
    if sha256(COMPLETED) != validation["inputs"][COMPLETED.name]:
        raise ValueError(
            "Completed structured-attribute review differs from validation provenance."
        )
    true_value = json.loads(TRUE_VALUE_MANIFEST.read_text(encoding="utf-8"))
    reviewed = read_csv(COMPLETED)
    reviewed_ids = {row["event_id"] for row in reviewed}
    prior_ids = {row["old_event_id"] for row in read_csv(IDENTITY_REMOVE)}
    prior_ids |= {row["merge_target_event_id"] for row in read_csv(IDENTITY_MERGES)}
    prior_ids |= {row["event_id"] for row in read_csv(TRUE_VALUE_COMPLETED)}
    overlap = reviewed_ids & prior_ids
    if overlap:
        raise ValueError(f"Structured-attribute rows overlap earlier plans: {sorted(overlap)}")

    frozen = read_csv(FROZEN_CANONICAL)
    corrections, exclusions = materialize(reviewed, frozen)
    correction_columns = list(corrections[0]) if corrections else ["event_id"]
    exclusion_columns = list(exclusions[0]) if exclusions else [
        "candidate_id", "event_id", "event_date", "district", "representative_url",
        "reviewed_by", "review_notes", "recommended_actions", "production_status",
    ]
    write_csv(CORRECTIONS_OUTPUT, corrections, correction_columns)
    write_csv(EXCLUSIONS_OUTPUT, exclusions, exclusion_columns)
    planned_rows = true_value["provisional_rows_after_true_value_plan"] - len(exclusions)
    manifest = {
        "review_rows": len(reviewed),
        "planned_corrections": len(corrections),
        "planned_exclusions": len(exclusions),
        "prior_gate_overlap_count": 0,
        "provisional_rows_after_all_manual_correction_plans": planned_rows,
        "frozen_inventory_rows": len(frozen),
        "net_delta_from_frozen_inventory": planned_rows - len(frozen),
        "inputs": {
            COMPLETED.name: sha256(COMPLETED),
            VALIDATION.name: sha256(VALIDATION),
            str(FROZEN_CANONICAL.relative_to(ROOT)): sha256(FROZEN_CANONICAL),
            IDENTITY_REMOVE.name: sha256(IDENTITY_REMOVE),
            IDENTITY_MERGES.name: sha256(IDENTITY_MERGES),
            TRUE_VALUE_COMPLETED.name: sha256(TRUE_VALUE_COMPLETED),
            TRUE_VALUE_MANIFEST.name: sha256(TRUE_VALUE_MANIFEST),
        },
        "outputs": {
            CORRECTIONS_OUTPUT.name: sha256(CORRECTIONS_OUTPUT),
            EXCLUSIONS_OUTPUT.name: sha256(EXCLUSIONS_OUTPUT),
        },
        "status": "all_manual_correction_gates_complete_unapplied_pipeline_fixes_pending",
    }
    MANIFEST_OUTPUT.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    REPORT_OUTPUT.write_text(
        "\n".join(
            [
                "# Canonical event structured-attribute release plan",
                "",
                f"Reviewed rows: {len(reviewed)}",
                f"Planned corrections: {len(corrections)}",
                f"Planned exclusions: {len(exclusions)}",
                "Prior-gate overlap: 0",
                f"Provisional inventory rows: {planned_rows}",
                f"Net change from the frozen inventory: {planned_rows - len(frozen):+d}",
                "",
                "All manual correction gates are complete. This plan remains unapplied",
                "until pipeline fixes and corrected-release assembly are complete.",
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
