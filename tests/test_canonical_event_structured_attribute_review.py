"""Tests for canonical-event structured-attribute review tooling."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load(name: str):
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def blank(actions: str = "correct_event_type") -> dict[str, str]:
    return {
        "candidate_id": "CEC-010", "recommended_actions": actions,
        "claimed_event_type": "landslide", "claimed_hazard_type": "landslide",
        "claimed_deaths": "", "final_record_action": "", "final_event_type": "",
        "final_hazard_type": "", "final_deaths": "", "reviewed_by": "", "review_notes": "",
    }


def test_builder_does_not_prefill_final_values() -> None:
    module = load("build_canonical_event_structured_attribute_review")
    source = {
        "candidate_id": "C", "row_id": "R", "event_id": "E",
        "recommended_actions": "correct_event_type", "claimed_event_date": "2020-01-01",
        "claimed_district": "Chitwan", "claimed_event_type": "landslide",
        "claimed_hazard_type": "landslide", "claimed_deaths": "",
        "proposed_event_type": "road_obstruction", "proposed_hazard_type": "",
        "proposed_deaths": "", "adjudication_notes": "n", "representative_title": "t",
        "representative_url": "u", "article_evidence": "e",
    }
    row = module.build([source])[0]
    assert row["suggested_event_type"] == "road_obstruction"
    assert row["final_event_type"] == ""


def test_valid_correction_must_change_claim() -> None:
    module = load("validate_canonical_event_structured_attribute_review")
    row = {
        **blank(), "final_record_action": "retain", "final_event_type": "road_obstruction",
        "reviewed_by": "D", "review_notes": "road blockage only",
    }
    assert module.validate([row], [blank()])["unresolved_values"] == 0
    row["final_event_type"] = "landslide"
    with pytest.raises(ValueError, match="did not change"):
        module.validate([row], [blank()])


def test_missing_required_value_blocks_release() -> None:
    module = load("validate_canonical_event_structured_attribute_review")
    row = {
        **blank(), "final_record_action": "retain", "reviewed_by": "D",
        "review_notes": "unknown",
    }
    assert module.validate([row], [blank()])["unresolved_values"] == 1


def test_excluded_record_must_leave_final_values_blank() -> None:
    module = load("validate_canonical_event_structured_attribute_review")
    row = {
        **blank(), "final_record_action": "exclude_candidate", "final_event_type": "other",
        "reviewed_by": "D", "review_notes": "not usable",
    }
    with pytest.raises(ValueError, match="leave final values blank"):
        module.validate([row], [blank()])
