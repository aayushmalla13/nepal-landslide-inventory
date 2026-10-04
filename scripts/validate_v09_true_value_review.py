#!/usr/bin/env python3
"""Validate the completed v0.9 true-value review against frozen provenance."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path


def _load_shared_validator():
    path = Path(__file__).with_name("validate_post_correction_true_value_review.py")
    spec = importlib.util.spec_from_file_location("post_correction_true_value_shared", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load shared true-value validator: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_shared = _load_shared_validator()
read_csv = _shared.read_csv
sha256 = _shared.sha256
validate = _shared.validate

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "outputs"
RELEASE = (
    ROOT / "data" / "releases" / "nepal_landslide_inventory_v0.8.0_candidate_20260923"
    / "canonical_events_final.csv"
)
TEMPLATE = OUTPUT / "v09_remediation_BATCH_TRUE_VALUE_REVIEW.csv"
REMEDIATION_MANIFEST = OUTPUT / "v09_remediation_manifest.json"
DEFAULT_COMPLETED = OUTPUT / "v09_remediation_BATCH_TRUE_VALUE_REVIEW_COMPLETED.csv"
IDENTITY_MANIFEST = OUTPUT / "v09_identity_plan_manifest.json"
IDENTITY_REMOVE = OUTPUT / "v09_identity_plan_REMOVE_OLD_EVENTS.csv"
IDENTITY_MERGES = OUTPUT / "v09_identity_plan_MERGES_EXISTING.csv"
VALIDATION_OUTPUT = OUTPUT / "v09_true_value_review_validation.json"
IDENTITY_STATUS = "v09_identity_plan_unapplied_true_value_and_structured_attribute_gates_pending"
PLAN_LABEL = "v0.9"
ALLOW_MERGE_TARGETS = False


def overlapping_event_ids(
    reviewed: list[dict[str, str]],
    removed: list[dict[str, str]],
    merges: list[dict[str, str]],
) -> set[str]:
    reviewed_ids = {row["event_id"] for row in reviewed}
    unavailable_ids = {row["old_event_id"] for row in removed}
    if not ALLOW_MERGE_TARGETS:
        unavailable_ids.update(row["merge_existing_event_id"] for row in merges)
    return reviewed_ids & unavailable_ids


def verify_frozen_inputs() -> tuple[dict, dict]:
    remediation = json.loads(REMEDIATION_MANIFEST.read_text(encoding="utf-8"))
    if sha256(TEMPLATE) != remediation["output_sha256"][TEMPLATE.name]:
        raise ValueError("True-value template differs from the remediation manifest")

    identity = json.loads(IDENTITY_MANIFEST.read_text(encoding="utf-8"))
    if identity["status"] != IDENTITY_STATUS:
        raise ValueError(f"{PLAN_LABEL} identity plan is not ready for true-value review")
    for path in (IDENTITY_REMOVE, IDENTITY_MERGES):
        if sha256(path) != identity["output_sha256"][path.name]:
            raise ValueError(f"Identity-plan artifact changed: {path.name}")
    return remediation, identity


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("completed", nargs="?", type=Path, default=DEFAULT_COMPLETED)
    args = parser.parse_args()

    verify_frozen_inputs()
    completed = read_csv(args.completed)
    overlap = overlapping_event_ids(
        completed, read_csv(IDENTITY_REMOVE), read_csv(IDENTITY_MERGES)
    )
    if overlap:
        raise ValueError(f"True-value rows overlap the identity plan: {sorted(overlap)}")

    result = validate(completed, read_csv(TEMPLATE), read_csv(RELEASE))
    result["identity_overlap_count"] = 0
    result["input_sha256"] = {
        args.completed.name: sha256(args.completed),
        TEMPLATE.name: sha256(TEMPLATE),
        REMEDIATION_MANIFEST.name: sha256(REMEDIATION_MANIFEST),
        IDENTITY_MANIFEST.name: sha256(IDENTITY_MANIFEST),
        IDENTITY_REMOVE.name: sha256(IDENTITY_REMOVE),
        IDENTITY_MERGES.name: sha256(IDENTITY_MERGES),
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
    print(f"Validated {result['review_rows']} {PLAN_LABEL} true-value decisions.")
    print(f"Status: {result['status']}")
    print(f"Wrote {VALIDATION_OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
