#!/usr/bin/env python3
"""Materialize validated v1.1 true-value decisions as an unapplied plan."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_core():
    path = Path(__file__).with_name("materialize_v09_true_value_plan.py")
    spec = importlib.util.spec_from_file_location("v11_true_value_plan_core", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load true-value plan core: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


core = _load_core()
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/outputs"
RELEASE = ROOT / "data/releases/nepal_landslide_inventory_v1.0.0_candidate_20260927"


def configure_core() -> None:
    core.RELEASE = RELEASE / "canonical_events_final.csv"
    core.COMPLETED = OUTPUT / "v11_remediation_BATCH_TRUE_VALUE_REVIEW_COMPLETED.csv"
    core.VALIDATION = OUTPUT / "v11_true_value_review_validation.json"
    core.IDENTITY_MANIFEST = OUTPUT / "v11_identity_plan_manifest.json"
    core.IDENTITY_REMOVE = OUTPUT / "v11_identity_plan_REMOVE_OLD_EVENTS.csv"
    core.IDENTITY_MERGES = OUTPUT / "v11_identity_plan_MERGES_EXISTING.csv"
    core.CORRECTIONS_OUTPUT = OUTPUT / "v11_true_value_plan_CORRECTIONS.csv"
    core.EXCLUSIONS_OUTPUT = OUTPUT / "v11_true_value_plan_EXCLUSIONS.csv"
    core.NO_CHANGE_OUTPUT = OUTPUT / "v11_true_value_plan_NO_CHANGE.csv"
    core.MANIFEST_OUTPUT = OUTPUT / "v11_true_value_plan_manifest.json"
    core.REPORT_OUTPUT = OUTPUT / "v11_true_value_plan_report.md"
    core.IDENTITY_STATUS = (
        "v11_identity_plan_unapplied_true_value_and_structured_attribute_gates_pending"
    )
    core.TRUE_VALUE_STATUS = (
        "v11_true_value_plan_unapplied_structured_attribute_gate_pending"
    )
    core.PLAN_LABEL = "v1.1"
    core.SOURCE_LABEL = "v1.0"
    core.ALLOW_MERGE_TARGETS = True


configure_core()
materialize = core.materialize


def main() -> int:
    configure_core()
    return core.main()


if __name__ == "__main__":
    raise SystemExit(main())
