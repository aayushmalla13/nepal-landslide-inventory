#!/usr/bin/env python3
"""Validate completed v1.4 true-value decisions against frozen provenance."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_core():
    path = Path(__file__).with_name("validate_v09_true_value_review.py")
    spec = importlib.util.spec_from_file_location("v14_true_value_validation_core", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load true-value validator core: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


core = _load_core()
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/outputs"
RELEASE = ROOT / "data/releases/nepal_landslide_inventory_v1.3.0_candidate_20260930/canonical_events_final.csv"


def configure_core() -> None:
    core.RELEASE = RELEASE
    core.TEMPLATE = OUTPUT / "v14_remediation_BATCH_TRUE_VALUE_REVIEW.csv"
    core.REMEDIATION_MANIFEST = OUTPUT / "v14_remediation_manifest.json"
    core.DEFAULT_COMPLETED = OUTPUT / "v14_remediation_BATCH_TRUE_VALUE_REVIEW_COMPLETED.csv"
    core.IDENTITY_MANIFEST = OUTPUT / "v14_identity_plan_manifest.json"
    core.IDENTITY_REMOVE = OUTPUT / "v14_identity_plan_REMOVE_OLD_EVENTS.csv"
    core.IDENTITY_MERGES = OUTPUT / "v14_identity_plan_MERGES_EXISTING.csv"
    core.VALIDATION_OUTPUT = OUTPUT / "v14_true_value_review_validation.json"
    core.IDENTITY_STATUS = (
        "v14_identity_plan_unapplied_true_value_and_structured_attribute_gates_pending"
    )
    core.PLAN_LABEL = "v1.4"


configure_core()
validate = core.validate


def main() -> int:
    configure_core()
    return core.main()


if __name__ == "__main__":
    raise SystemExit(main())
