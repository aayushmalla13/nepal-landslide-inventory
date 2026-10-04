#!/usr/bin/env python3
"""Build the final v1.3 structured-attribute review sheet."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_core():
    path = Path(__file__).with_name("build_v09_structured_attribute_review.py")
    spec = importlib.util.spec_from_file_location("v13_structured_review_core", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load structured-review core: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


core = _load_core()
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/outputs"


def configure_core() -> None:
    core.SOURCE = OUTPUT / "v13_remediation_BATCH_STRUCTURED_ATTRIBUTES.csv"
    core.REMEDIATION_MANIFEST = OUTPUT / "v13_remediation_manifest.json"
    core.IDENTITY_REMOVE = OUTPUT / "v13_identity_plan_REMOVE_OLD_EVENTS.csv"
    core.IDENTITY_MERGES = OUTPUT / "v13_identity_plan_MERGES_EXISTING.csv"
    core.IDENTITY_MANIFEST = OUTPUT / "v13_identity_plan_manifest.json"
    core.TRUE_VALUE_COMPLETED = OUTPUT / "v13_remediation_BATCH_TRUE_VALUE_REVIEW_COMPLETED.csv"
    core.TRUE_VALUE_CORRECTIONS = OUTPUT / "v13_true_value_plan_CORRECTIONS.csv"
    core.TRUE_VALUE_EXCLUSIONS = OUTPUT / "v13_true_value_plan_EXCLUSIONS.csv"
    core.TRUE_VALUE_NO_CHANGE = OUTPUT / "v13_true_value_plan_NO_CHANGE.csv"
    core.TRUE_VALUE_MANIFEST = OUTPUT / "v13_true_value_plan_manifest.json"
    core.REVIEW_OUTPUT = OUTPUT / "v13_structured_attribute_REVIEW.csv"
    core.MANIFEST_OUTPUT = OUTPUT / "v13_structured_attribute_review_manifest.json"
    core.REPORT_OUTPUT = OUTPUT / "v13_structured_attribute_review_report.md"
    core.IDENTITY_STATUS = (
        "v13_identity_plan_unapplied_true_value_and_structured_attribute_gates_pending"
    )
    core.TRUE_VALUE_STATUS = "v13_true_value_plan_unapplied_structured_attribute_gate_pending"
    core.REVIEW_STATUS = "blank_v13_structured_attribute_review"
    core.PLAN_LABEL = "v1.3"


configure_core()
build = core.build


def main() -> int:
    configure_core()
    return core.main()


if __name__ == "__main__":
    raise SystemExit(main())
