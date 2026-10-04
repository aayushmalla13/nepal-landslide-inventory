"""Tests for v1.4 structured-attribute wrappers."""

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


def test_builder_targets_v14_inputs_and_outputs() -> None:
    module = load("build_v14_structured_attribute_review.py")
    assert module.core.SOURCE.name == "v14_remediation_BATCH_STRUCTURED_ATTRIBUTES.csv"
    assert module.core.REVIEW_OUTPUT.name == "v14_structured_attribute_REVIEW.csv"
    assert module.core.REVIEW_STATUS == "blank_v14_structured_attribute_review"


def test_validator_targets_v14_review() -> None:
    module = load("validate_v14_structured_attribute_review.py")
    assert module.core.TEMPLATE.name == "v14_structured_attribute_REVIEW.csv"
    assert module.core.DEFAULT_COMPLETED.name == "v14_structured_attribute_REVIEW_COMPLETED.csv"


def test_materializer_targets_frozen_v13_and_v14_outputs() -> None:
    module = load("materialize_v14_structured_attribute_plan.py")
    assert module.RELEASE.name == "nepal_landslide_inventory_v1.3.0_candidate_20260930"
    assert module.core.CORRECTIONS_OUTPUT.name == "v14_structured_attribute_plan_CORRECTIONS.csv"
    assert module.core.FINAL_STATUS == "all_v14_manual_gates_complete_candidate_assembly_pending"


def test_validator_accepts_clear_deaths_action() -> None:
    module = load("validate_v14_structured_attribute_review.py")
    row = {
        "queue_id": "V14R-004",
        "recommended_actions": "clear_deaths",
        "claimed_event_type": "landslide",
        "claimed_hazard_type": "landslide",
        "claimed_deaths": "2",
        "final_record_action": "retain",
        "final_event_type": "",
        "final_hazard_type": "",
        "final_deaths": "not_reported",
        "reviewed_by": "aayush",
        "review_notes": "Article does not report deaths for this event.",
    }
    template = {**row, "final_record_action": "", "final_deaths": "", "reviewed_by": "", "review_notes": ""}
    result = module.validate([row], [template])
    assert result["changed_field_counts"] == {"deaths": 1}
    assert result["unresolved_count"] == 0
