#!/usr/bin/env python3
"""Materialize the validated v1.1 structured-attribute plan."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_core():
    path = Path(__file__).with_name("materialize_v09_structured_attribute_plan.py")
    spec = importlib.util.spec_from_file_location("v11_structured_plan_core", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load structured plan core: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


core = _load_core()
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/outputs"
RELEASE = ROOT / "data/releases/nepal_landslide_inventory_v1.0.0_candidate_20260927"


def configure_core() -> None:
    core.RELEASE = RELEASE / "canonical_events_final.csv"
    core.COMPLETED = OUTPUT / "v11_structured_attribute_REVIEW_COMPLETED.csv"
    core.VALIDATION = OUTPUT / "v11_structured_attribute_review_validation.json"
    core.IDENTITY_REMOVE = OUTPUT / "v11_identity_plan_REMOVE_OLD_EVENTS.csv"
    core.IDENTITY_MERGES = OUTPUT / "v11_identity_plan_MERGES_EXISTING.csv"
    core.IDENTITY_MANIFEST = OUTPUT / "v11_identity_plan_manifest.json"
    core.TRUE_VALUE_CORRECTIONS = OUTPUT / "v11_true_value_plan_CORRECTIONS.csv"
    core.TRUE_VALUE_EXCLUSIONS = OUTPUT / "v11_true_value_plan_EXCLUSIONS.csv"
    core.TRUE_VALUE_NO_CHANGE = OUTPUT / "v11_true_value_plan_NO_CHANGE.csv"
    core.TRUE_VALUE_MANIFEST = OUTPUT / "v11_true_value_plan_manifest.json"
    core.CORRECTIONS_OUTPUT = OUTPUT / "v11_structured_attribute_plan_CORRECTIONS.csv"
    core.EXCLUSIONS_OUTPUT = OUTPUT / "v11_structured_attribute_plan_EXCLUSIONS.csv"
    core.MANIFEST_OUTPUT = OUTPUT / "v11_structured_attribute_plan_manifest.json"
    core.REPORT_OUTPUT = OUTPUT / "v11_structured_attribute_plan_report.md"
    core.TRUE_VALUE_STATUS = (
        "v11_true_value_plan_unapplied_structured_attribute_gate_pending"
    )
    core.FINAL_STATUS = "all_v11_manual_gates_complete_candidate_assembly_pending"
    core.PLAN_LABEL = "v1.1"
    core.SOURCE_LABEL = "v1.0"


configure_core()
materialize = core.materialize


def main() -> int:
    configure_core()
    return core.main()


if __name__ == "__main__":
    raise SystemExit(main())
