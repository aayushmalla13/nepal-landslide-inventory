"""Tests for v1.1 structured-attribute wrappers."""

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


def test_builder_targets_v11_artifacts() -> None:
    module = load("build_v11_structured_attribute_review.py")
    assert module.core.SOURCE.name == "v11_remediation_BATCH_STRUCTURED_ATTRIBUTES.csv"
    assert module.core.REVIEW_OUTPUT.name == "v11_structured_attribute_REVIEW.csv"
    assert module.core.REVIEW_STATUS == "blank_v11_structured_attribute_review"


def test_validator_targets_v11_review() -> None:
    module = load("validate_v11_structured_attribute_review.py")
    assert module.core.DEFAULT_COMPLETED.name == (
        "v11_structured_attribute_REVIEW_COMPLETED.csv"
    )


def test_materializer_targets_v10_release_and_v11_outputs() -> None:
    module = load("materialize_v11_structured_attribute_plan.py")
    assert module.core.RELEASE.parent.name == (
        "nepal_landslide_inventory_v1.0.0_candidate_20260927"
    )
    assert module.core.CORRECTIONS_OUTPUT.name == (
        "v11_structured_attribute_plan_CORRECTIONS.csv"
    )
