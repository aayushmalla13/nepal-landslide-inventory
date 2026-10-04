#!/usr/bin/env python3
"""Materialize the validated post-correction structured-attribute plan."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "outputs"
RELEASE = (
    ROOT
    / "data"
    / "releases"
    / "nepal_landslide_inventory_v0.7.0_candidate_20260916"
    / "canonical_events_final.csv"
)
COMPLETED = OUTPUT / "post_correction_structured_attribute_REVIEW_COMPLETED.csv"
VALIDATION = OUTPUT / "post_correction_structured_attribute_review_validation.json"
IDENTITY_REMOVE = OUTPUT / "post_correction_identity_plan_REMOVE_OLD_EVENTS.csv"
IDENTITY_MERGES = OUTPUT / "post_correction_identity_plan_MERGES_EXISTING.csv"
IDENTITY_MANIFEST = OUTPUT / "post_correction_identity_plan_manifest.json"
TRUE_VALUE_COMPLETED = (
    OUTPUT / "post_correction_remediation_BATCH_TRUE_VALUE_REVIEW_COMPLETED.csv"
)
TRUE_VALUE_MANIFEST = OUTPUT / "post_correction_true_value_plan_manifest.json"
CORRECTIONS_OUTPUT = OUTPUT / "post_correction_structured_attribute_plan_CORRECTIONS.csv"
EXCLUSIONS_OUTPUT = OUTPUT / "post_correction_structured_attribute_plan_EXCLUSIONS.csv"
MANIFEST_OUTPUT = OUTPUT / "post_correction_structured_attribute_plan_manifest.json"
REPORT_OUTPUT = OUTPUT / "post_correction_structured_attribute_plan_report.md"

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
    completed: list[dict[str, str]], source: list[dict[str, str]]
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    source_by_id = {row["event_id"]: row for row in source}
    corrections: list[dict[str, object]] = []
    exclusions: list[dict[str, object]] = []
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
            "event_date": original["event_date_ad"],
            "district": original["district"],
            "representative_url": original["representative_url"],
            "recommended_actions": row["recommended_actions"],
            "reviewed_by": row["reviewed_by"],
            "review_notes": row["review_notes"],
        }
        action = row["final_record_action"]
        if action == "exclude_candidate":
            exclusions.append(
                {**common, "production_status": "planned_exclude_existing_event"}
            )
            continue
        if action != "retain":
            raise ValueError(f"{queue_id}: unresolved final_record_action.")

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
            raise ValueError(f"{queue_id}: retained decision makes no material change.")
        corrections.append(
            {
                **common,
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
    if sha256(COMPLETED) != validation["input_sha256"][COMPLETED.name]:
        raise ValueError("Completed review differs from validation provenance.")

    identity = json.loads(IDENTITY_MANIFEST.read_text(encoding="utf-8"))
    true_value = json.loads(TRUE_VALUE_MANIFEST.read_text(encoding="utf-8"))
    reviewed = read_csv(COMPLETED)
    reviewed_ids = {row["event_id"] for row in reviewed}
    prior_ids = {row["old_event_id"] for row in read_csv(IDENTITY_REMOVE)}
    prior_ids |= {
        row["merge_existing_event_id"] for row in read_csv(IDENTITY_MERGES)
    }
    prior_ids |= {row["event_id"] for row in read_csv(TRUE_VALUE_COMPLETED)}
    overlap = reviewed_ids & prior_ids
    if overlap:
        raise ValueError(f"Structured-attribute rows overlap prior plans: {sorted(overlap)}")

    corrections, exclusions = materialize(reviewed, read_csv(RELEASE))
    correction_columns = list(corrections[0]) if corrections else ["event_id"]
    exclusion_columns = list(exclusions[0]) if exclusions else [
        "queue_id",
        "row_id",
        "event_id",
        "event_date",
        "district",
        "representative_url",
        "recommended_actions",
        "reviewed_by",
        "review_notes",
        "production_status",
    ]
    write_csv(CORRECTIONS_OUTPUT, corrections, correction_columns)
    write_csv(EXCLUSIONS_OUTPUT, exclusions, exclusion_columns)

    planned_rows = true_value["provisional_rows_after_true_value_plan"] - len(exclusions)
    source_rows = identity["source_inventory_rows"]
    manifest = {
        "review_rows": len(reviewed),
        "planned_corrections": len(corrections),
        "planned_exclusions": len(exclusions),
        "prior_gate_overlap_count": 0,
        "provisional_rows_after_all_manual_plans": planned_rows,
        "source_inventory_rows": source_rows,
        "net_delta_from_source_inventory": planned_rows - source_rows,
        "input_sha256": {
            COMPLETED.name: sha256(COMPLETED),
            VALIDATION.name: sha256(VALIDATION),
            TRUE_VALUE_COMPLETED.name: sha256(TRUE_VALUE_COMPLETED),
            TRUE_VALUE_MANIFEST.name: sha256(TRUE_VALUE_MANIFEST),
            IDENTITY_MANIFEST.name: sha256(IDENTITY_MANIFEST),
            IDENTITY_REMOVE.name: sha256(IDENTITY_REMOVE),
            IDENTITY_MERGES.name: sha256(IDENTITY_MERGES),
            str(RELEASE.relative_to(ROOT)): sha256(RELEASE),
        },
        "output_sha256": {
            CORRECTIONS_OUTPUT.name: sha256(CORRECTIONS_OUTPUT),
            EXCLUSIONS_OUTPUT.name: sha256(EXCLUSIONS_OUTPUT),
        },
        "status": "all_post_correction_manual_gates_complete_candidate_assembly_pending",
    }
    MANIFEST_OUTPUT.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    REPORT_OUTPUT.write_text(
        "\n".join(
            [
                "# Post-correction structured-attribute plan",
                "",
                f"Reviewed rows: {len(reviewed)}",
                f"Planned corrections: {len(corrections)}",
                f"Planned exclusions: {len(exclusions)}",
                "Prior-gate overlap: 0",
                f"Provisional inventory rows: {planned_rows}",
                f"Net change from the source candidate: {planned_rows - source_rows:+d}",
                "",
                "All post-correction manual gates are complete. The plans remain",
                "unapplied until a new checksummed candidate is assembled.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"Wrote {len(corrections)} corrections to {CORRECTIONS_OUTPUT}")
    print(f"Wrote {len(exclusions)} exclusions to {EXCLUSIONS_OUTPUT}")
    print(f"Wrote {MANIFEST_OUTPUT}")


if __name__ == "__main__":
    main()
