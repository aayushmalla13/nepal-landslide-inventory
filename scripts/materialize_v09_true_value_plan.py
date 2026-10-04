#!/usr/bin/env python3
"""Materialize validated v0.9 true-value decisions as an unapplied plan."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_shared_materializer():
    path = Path(__file__).with_name("materialize_post_correction_true_value_plan.py")
    spec = importlib.util.spec_from_file_location("post_correction_true_value_shared", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load shared true-value materializer: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_shared = _load_shared_materializer()
read_csv = _shared.read_csv
write_csv = _shared.write_csv
sha256 = _shared.sha256
materialize = _shared.materialize

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "outputs"
RELEASE = (
    ROOT / "data" / "releases" / "nepal_landslide_inventory_v0.8.0_candidate_20260923"
    / "canonical_events_final.csv"
)
COMPLETED = OUTPUT / "v09_remediation_BATCH_TRUE_VALUE_REVIEW_COMPLETED.csv"
VALIDATION = OUTPUT / "v09_true_value_review_validation.json"
IDENTITY_MANIFEST = OUTPUT / "v09_identity_plan_manifest.json"
IDENTITY_REMOVE = OUTPUT / "v09_identity_plan_REMOVE_OLD_EVENTS.csv"
IDENTITY_MERGES = OUTPUT / "v09_identity_plan_MERGES_EXISTING.csv"
CORRECTIONS_OUTPUT = OUTPUT / "v09_true_value_plan_CORRECTIONS.csv"
EXCLUSIONS_OUTPUT = OUTPUT / "v09_true_value_plan_EXCLUSIONS.csv"
NO_CHANGE_OUTPUT = OUTPUT / "v09_true_value_plan_NO_CHANGE.csv"
MANIFEST_OUTPUT = OUTPUT / "v09_true_value_plan_manifest.json"
REPORT_OUTPUT = OUTPUT / "v09_true_value_plan_report.md"
IDENTITY_STATUS = "v09_identity_plan_unapplied_true_value_and_structured_attribute_gates_pending"
TRUE_VALUE_STATUS = "v09_true_value_plan_unapplied_structured_attribute_gate_pending"
PLAN_LABEL = "v0.9"
SOURCE_LABEL = "v0.8"
ALLOW_MERGE_TARGETS = False

CORRECTION_COLUMNS = [
    "queue_id", "row_id", "event_id", "representative_url",
    "recommended_actions", "reviewed_by", "review_notes", "changed_fields_json",
    "original_event_date", "original_district", "original_municipality",
    "original_event_type", "original_hazard_type", "original_deaths",
    "original_province", "final_event_date", "final_district",
    "final_municipality", "final_event_type", "final_hazard_type",
    "final_deaths", "final_province", "production_status",
]
EXCLUSION_COLUMNS = [
    "queue_id", "row_id", "event_id", "representative_url",
    "recommended_actions", "reviewed_by", "review_notes", "event_date",
    "district", "production_status",
]


def verify_inputs() -> tuple[dict, dict]:
    validation = json.loads(VALIDATION.read_text(encoding="utf-8"))
    if validation["status"] != "validated_true_values_not_yet_applied":
        raise ValueError(f"{PLAN_LABEL} true-value review is not release-safe")
    if sha256(COMPLETED) != validation["input_sha256"][COMPLETED.name]:
        raise ValueError("Completed review differs from its validation provenance")

    identity = json.loads(IDENTITY_MANIFEST.read_text(encoding="utf-8"))
    if identity["status"] != IDENTITY_STATUS:
        raise ValueError(
            f"{PLAN_LABEL} identity plan is not ready for true-value materialization"
        )
    for path in (IDENTITY_REMOVE, IDENTITY_MERGES):
        if sha256(path) != identity["output_sha256"][path.name]:
            raise ValueError(f"Identity-plan artifact changed: {path.name}")
    return identity, validation


def main() -> int:
    identity, validation = verify_inputs()
    reviewed = read_csv(COMPLETED)
    reviewed_ids = {row["event_id"] for row in reviewed}
    removed_ids = {row["old_event_id"] for row in read_csv(IDENTITY_REMOVE)}
    merge_targets = {
        row["merge_existing_event_id"] for row in read_csv(IDENTITY_MERGES)
    }
    unavailable_ids = removed_ids if ALLOW_MERGE_TARGETS else removed_ids | merge_targets
    overlap = reviewed_ids & unavailable_ids
    if overlap:
        raise ValueError(f"True-value rows overlap the identity plan: {sorted(overlap)}")

    corrections, exclusions, no_change = materialize(reviewed, read_csv(RELEASE))
    expected = {
        "corrections": validation_count("retain", reviewed) - len(no_change),
        "exclusions": validation_count("exclude_candidate", reviewed),
        "no_change": validation["retained_no_change_count"],
    }
    actual = {
        "corrections": len(corrections),
        "exclusions": len(exclusions),
        "no_change": len(no_change),
    }
    if actual != expected:
        raise ValueError(
            f"Unexpected {PLAN_LABEL} true-value counts: {actual}; expected {expected}"
        )

    outputs = {
        CORRECTIONS_OUTPUT: corrections,
        EXCLUSIONS_OUTPUT: exclusions,
        NO_CHANGE_OUTPUT: no_change,
    }
    output_columns = {
        CORRECTIONS_OUTPUT: CORRECTION_COLUMNS,
        EXCLUSIONS_OUTPUT: EXCLUSION_COLUMNS,
        NO_CHANGE_OUTPUT: CORRECTION_COLUMNS,
    }
    for path, rows in outputs.items():
        columns = list(rows[0]) if rows else output_columns[path]
        write_csv(path, rows, columns)

    planned_rows = identity["planned_identity_layer_rows"] - len(exclusions)
    inputs = (
        COMPLETED, VALIDATION, IDENTITY_MANIFEST, IDENTITY_REMOVE,
        IDENTITY_MERGES, RELEASE,
    )
    manifest = {
        "review_rows": len(reviewed),
        "planned_corrections": len(corrections),
        "planned_exclusions": len(exclusions),
        "reviewed_no_change": len(no_change),
        "identity_overlap_count": 0,
        "identity_plan_rows_before_true_value_exclusions": identity["planned_identity_layer_rows"],
        "provisional_rows_after_true_value_plan": planned_rows,
        "net_delta_from_source_inventory": planned_rows - identity["source_inventory_rows"],
        "input_sha256": {str(path.relative_to(ROOT)): sha256(path) for path in inputs},
        "output_sha256": {path.name: sha256(path) for path in outputs},
        "status": TRUE_VALUE_STATUS,
    }
    MANIFEST_OUTPUT.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    REPORT_OUTPUT.write_text(
        "\n".join(
            [
                f"# {PLAN_LABEL} true-value plan", "",
                f"Reviewed rows: {len(reviewed)}",
                f"Planned corrections: {len(corrections)}",
                f"Planned exclusions: {len(exclusions)}",
                f"Reviewed no-change rows: {len(no_change)}",
                "Identity-plan overlap: 0",
                f"Provisional inventory rows: {planned_rows}",
                f"Net change from the {identity['source_inventory_rows']}-row {SOURCE_LABEL} source: "
                f"{planned_rows - identity['source_inventory_rows']:+d}", "",
                "This plan remains unapplied. Complete the structured-attribute gate",
                f"before assembling the {PLAN_LABEL} candidate.", "",
            ]
        ),
        encoding="utf-8",
    )
    for path, rows in outputs.items():
        print(f"Wrote {len(rows)} rows to {path}")
    print(f"Wrote {MANIFEST_OUTPUT}")
    print(f"Wrote {REPORT_OUTPUT}")
    return 0


def validation_count(action: str, rows: list[dict[str, str]]) -> int:
    return sum(row["reviewed_action"] == action for row in rows)


if __name__ == "__main__":
    raise SystemExit(main())
