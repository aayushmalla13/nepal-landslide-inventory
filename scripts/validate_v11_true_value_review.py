#!/usr/bin/env python3
"""Validate completed v1.1 true-value decisions against frozen provenance."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_core():
    path = Path(__file__).with_name("validate_v09_true_value_review.py")
    spec = importlib.util.spec_from_file_location("v11_true_value_validation_core", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load true-value validator core: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


core = _load_core()
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/outputs"
RELEASE = ROOT / "data/releases/nepal_landslide_inventory_v1.0.0_candidate_20260927"


def configure_core() -> None:
    core.RELEASE = RELEASE / "canonical_events_final.csv"
    core.TEMPLATE = OUTPUT / "v11_remediation_BATCH_TRUE_VALUE_REVIEW.csv"
    core.REMEDIATION_MANIFEST = OUTPUT / "v11_remediation_manifest.json"
    core.DEFAULT_COMPLETED = (
        OUTPUT / "v11_remediation_BATCH_TRUE_VALUE_REVIEW_COMPLETED.csv"
    )
    core.IDENTITY_MANIFEST = OUTPUT / "v11_identity_plan_manifest.json"
    core.IDENTITY_REMOVE = OUTPUT / "v11_identity_plan_REMOVE_OLD_EVENTS.csv"
    core.IDENTITY_MERGES = OUTPUT / "v11_identity_plan_MERGES_EXISTING.csv"
    core.VALIDATION_OUTPUT = OUTPUT / "v11_true_value_review_validation.json"
    core.IDENTITY_STATUS = (
        "v11_identity_plan_unapplied_true_value_and_structured_attribute_gates_pending"
    )
    core.PLAN_LABEL = "v1.1"
    core.ALLOW_MERGE_TARGETS = True


configure_core()
validate = core.validate
overlapping_event_ids = core.overlapping_event_ids


def main() -> int:
    configure_core()
    return core.main()


if __name__ == "__main__":
    raise SystemExit(main())
