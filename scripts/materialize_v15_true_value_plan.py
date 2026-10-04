#!/usr/bin/env python3
"""Materialize validated v1.5 true-value decisions as an unapplied plan."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_core():
    path = Path(__file__).with_name("materialize_v09_true_value_plan.py")
    spec = importlib.util.spec_from_file_location("v15_true_value_core", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load true-value materializer core: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


core = _load_core()
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/outputs"
RELEASE = ROOT / "data/releases/nepal_landslide_inventory_v1.4.0_candidate_20261002/canonical_events_final.csv"


def configure_core() -> None:
    core.RELEASE = RELEASE
    core.COMPLETED = OUTPUT / "v15_remediation_BATCH_TRUE_VALUE_REVIEW_COMPLETED.csv"
    core.VALIDATION = OUTPUT / "v15_true_value_review_validation.json"
    core.IDENTITY_MANIFEST = OUTPUT / "v15_identity_plan_manifest.json"
    core.IDENTITY_REMOVE = OUTPUT / "v15_identity_plan_REMOVE_OLD_EVENTS.csv"
    core.IDENTITY_MERGES = OUTPUT / "v15_identity_plan_MERGES_EXISTING.csv"
    core.CORRECTIONS_OUTPUT = OUTPUT / "v15_true_value_plan_CORRECTIONS.csv"
    core.EXCLUSIONS_OUTPUT = OUTPUT / "v15_true_value_plan_EXCLUSIONS.csv"
    core.NO_CHANGE_OUTPUT = OUTPUT / "v15_true_value_plan_NO_CHANGE.csv"
    core.MANIFEST_OUTPUT = OUTPUT / "v15_true_value_plan_manifest.json"
    core.REPORT_OUTPUT = OUTPUT / "v15_true_value_plan_report.md"
    core.IDENTITY_STATUS = (
        "v15_identity_plan_unapplied_true_value_and_structured_attribute_gates_pending"
    )
    core.TRUE_VALUE_STATUS = "v15_true_value_plan_unapplied_structured_attribute_gate_pending"
    core.PLAN_LABEL = "v1.5"
    core.SOURCE_LABEL = "v1.4"


configure_core()
materialize = core.materialize


def main() -> int:
    configure_core()
    return core.main()


if __name__ == "__main__":
    raise SystemExit(main())
