"""Tests for v1.5 structured-attribute wrappers."""

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


def test_builder_targets_v15_inputs_and_outputs() -> None:
    module = load("build_v15_structured_attribute_review.py")
    assert module.core.SOURCE.name == "v15_remediation_BATCH_STRUCTURED_ATTRIBUTES.csv"
    assert module.core.REVIEW_OUTPUT.name == "v15_structured_attribute_REVIEW.csv"
    assert module.core.REVIEW_STATUS == "blank_v15_structured_attribute_review"


def test_validator_targets_v15_review() -> None:
    module = load("validate_v15_structured_attribute_review.py")
    assert module.core.TEMPLATE.name == "v15_structured_attribute_REVIEW.csv"
    assert module.core.DEFAULT_COMPLETED.name == "v15_structured_attribute_REVIEW_COMPLETED.csv"


def test_materializer_targets_frozen_v14_and_v15_outputs() -> None:
    module = load("materialize_v15_structured_attribute_plan.py")
    assert module.RELEASE.name == "nepal_landslide_inventory_v1.4.0_candidate_20261002"
    assert module.core.CORRECTIONS_OUTPUT.name == "v15_structured_attribute_plan_CORRECTIONS.csv"
    assert module.core.FINAL_STATUS == "all_v15_manual_gates_complete_candidate_assembly_pending"
