#!/usr/bin/env python3
"""Materialize the validated v0.9 structured-attribute plan."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_shared_materializer():
    path = Path(__file__).with_name("materialize_post_correction_structured_attribute_plan.py")
    spec = importlib.util.spec_from_file_location("post_correction_structured_plan_shared", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load shared structured materializer: {path}")
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
COMPLETED = OUTPUT / "v09_structured_attribute_REVIEW_COMPLETED.csv"
VALIDATION = OUTPUT / "v09_structured_attribute_review_validation.json"
IDENTITY_REMOVE = OUTPUT / "v09_identity_plan_REMOVE_OLD_EVENTS.csv"
IDENTITY_MERGES = OUTPUT / "v09_identity_plan_MERGES_EXISTING.csv"
IDENTITY_MANIFEST = OUTPUT / "v09_identity_plan_manifest.json"
TRUE_VALUE_CORRECTIONS = OUTPUT / "v09_true_value_plan_CORRECTIONS.csv"
TRUE_VALUE_EXCLUSIONS = OUTPUT / "v09_true_value_plan_EXCLUSIONS.csv"
TRUE_VALUE_NO_CHANGE = OUTPUT / "v09_true_value_plan_NO_CHANGE.csv"
TRUE_VALUE_MANIFEST = OUTPUT / "v09_true_value_plan_manifest.json"
CORRECTIONS_OUTPUT = OUTPUT / "v09_structured_attribute_plan_CORRECTIONS.csv"
EXCLUSIONS_OUTPUT = OUTPUT / "v09_structured_attribute_plan_EXCLUSIONS.csv"
MANIFEST_OUTPUT = OUTPUT / "v09_structured_attribute_plan_manifest.json"
REPORT_OUTPUT = OUTPUT / "v09_structured_attribute_plan_report.md"
TRUE_VALUE_STATUS = "v09_true_value_plan_unapplied_structured_attribute_gate_pending"
FINAL_STATUS = "all_v09_manual_gates_complete_candidate_assembly_pending"
PLAN_LABEL = "v0.9"
SOURCE_LABEL = "v0.8"


def prior_event_ids() -> set[str]:
    ids = {row["old_event_id"] for row in read_csv(IDENTITY_REMOVE)}
    ids.update(row["merge_existing_event_id"] for row in read_csv(IDENTITY_MERGES))
    for path in (TRUE_VALUE_CORRECTIONS, TRUE_VALUE_EXCLUSIONS, TRUE_VALUE_NO_CHANGE):
        ids.update(row["event_id"] for row in read_csv(path))
    return ids


def verify_inputs() -> tuple[dict, dict, dict]:
    validation = json.loads(VALIDATION.read_text(encoding="utf-8"))
    if validation["status"] != "validated_structured_attributes_not_yet_applied":
        raise ValueError(f"{PLAN_LABEL} structured-attribute review is not release-safe")
    if sha256(COMPLETED) != validation["input_sha256"][COMPLETED.name]:
        raise ValueError("Completed review differs from validation provenance")

    identity = json.loads(IDENTITY_MANIFEST.read_text(encoding="utf-8"))
    true_value = json.loads(TRUE_VALUE_MANIFEST.read_text(encoding="utf-8"))
    if true_value["status"] != TRUE_VALUE_STATUS:
        raise ValueError(f"{PLAN_LABEL} true-value plan is not ready")
    for path in (TRUE_VALUE_CORRECTIONS, TRUE_VALUE_EXCLUSIONS, TRUE_VALUE_NO_CHANGE):
        if sha256(path) != true_value["output_sha256"][path.name]:
            raise ValueError(f"True-value artifact changed: {path.name}")
    return validation, identity, true_value


def main() -> int:
    validation, identity, true_value = verify_inputs()
    reviewed = read_csv(COMPLETED)
    overlap = {row["event_id"] for row in reviewed} & prior_event_ids()
    if overlap:
        raise ValueError(f"Structured-attribute rows overlap prior plans: {sorted(overlap)}")

    corrections, exclusions = materialize(reviewed, read_csv(RELEASE))
    expected_corrections = validation["record_action_counts"].get("retain", 0)
    expected_exclusions = validation["record_action_counts"].get("exclude_candidate", 0)
    if (len(corrections), len(exclusions)) != (expected_corrections, expected_exclusions):
        raise ValueError("Materialized structured-attribute counts differ from validation")

    correction_columns = list(corrections[0]) if corrections else ["event_id"]
    exclusion_columns = list(exclusions[0]) if exclusions else [
        "queue_id", "row_id", "event_id", "event_date", "district",
        "representative_url", "recommended_actions", "reviewed_by",
        "review_notes", "production_status",
    ]
    write_csv(CORRECTIONS_OUTPUT, corrections, correction_columns)
    write_csv(EXCLUSIONS_OUTPUT, exclusions, exclusion_columns)

    planned_rows = true_value["provisional_rows_after_true_value_plan"] - len(exclusions)
    inputs = (
        COMPLETED, VALIDATION, IDENTITY_MANIFEST, IDENTITY_REMOVE, IDENTITY_MERGES,
        TRUE_VALUE_MANIFEST, TRUE_VALUE_CORRECTIONS, TRUE_VALUE_EXCLUSIONS,
        TRUE_VALUE_NO_CHANGE, RELEASE,
    )
    outputs = (CORRECTIONS_OUTPUT, EXCLUSIONS_OUTPUT)
    manifest = {
        "review_rows": len(reviewed),
        "planned_corrections": len(corrections),
        "planned_exclusions": len(exclusions),
        "prior_gate_overlap_count": 0,
        "provisional_rows_after_all_manual_plans": planned_rows,
        "source_inventory_rows": identity["source_inventory_rows"],
        "net_delta_from_source_inventory": planned_rows - identity["source_inventory_rows"],
        "input_sha256": {str(path.relative_to(ROOT)): sha256(path) for path in inputs},
        "output_sha256": {path.name: sha256(path) for path in outputs},
        "status": FINAL_STATUS,
    }
    MANIFEST_OUTPUT.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    REPORT_OUTPUT.write_text(
        "\n".join(
            [
                f"# {PLAN_LABEL} structured-attribute plan", "",
                f"Reviewed rows: {len(reviewed)}",
                f"Planned corrections: {len(corrections)}",
                f"Planned exclusions: {len(exclusions)}",
                "Prior-gate overlap: 0",
                f"Provisional inventory rows: {planned_rows}",
                f"Net change from {SOURCE_LABEL}: {planned_rows - identity['source_inventory_rows']:+d}", "",
                f"All {PLAN_LABEL} manual gates are complete. The plans remain unapplied",
                f"until the checksummed {PLAN_LABEL} candidate is assembled.", "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"Wrote {len(corrections)} corrections to {CORRECTIONS_OUTPUT}")
    print(f"Wrote {len(exclusions)} exclusions to {EXCLUSIONS_OUTPUT}")
    print(f"Wrote {MANIFEST_OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
