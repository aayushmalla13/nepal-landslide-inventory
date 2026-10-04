"""Tests for v1.5 true-value review wrappers."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load(name: str):
    path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_wrappers_target_v15_and_frozen_v14() -> None:
    validator = load("validate_v15_true_value_review.py")
    materializer = load("materialize_v15_true_value_plan.py")
    assert validator.core.TEMPLATE.name == "v15_remediation_BATCH_TRUE_VALUE_REVIEW.csv"
    assert validator.core.RELEASE == materializer.core.RELEASE
    assert validator.core.RELEASE.parent.name == (
        "nepal_landslide_inventory_v1.4.0_candidate_20261002"
    )
    assert materializer.core.COMPLETED.name == (
        "v15_remediation_BATCH_TRUE_VALUE_REVIEW_COMPLETED.csv"
    )
    assert materializer.core.TRUE_VALUE_STATUS == (
        "v15_true_value_plan_unapplied_structured_attribute_gate_pending"
    )
