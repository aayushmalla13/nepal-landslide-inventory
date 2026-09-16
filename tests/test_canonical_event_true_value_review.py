"""Tests for canonical-event true-value review generation and validation."""

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


def blank(actions: str = "correct_date") -> dict[str, str]:
    return {
        "candidate_id": "CEC-001", "recommended_actions": actions,
        "claimed_event_date": "2020-01-02", "claimed_district": "Chitwan",
        "claimed_municipality": "", "claimed_event_type": "landslide",
        "claimed_hazard_type": "landslide", "claimed_deaths": "",
        "final_record_action": "", "final_event_date": "",
        "final_district": "", "final_municipality": "",
        "final_event_type": "", "final_hazard_type": "", "final_deaths": "",
        "reviewed_by": "", "review_notes": "",
    }


def test_confirmed_date_correction_requires_changed_date() -> None:
    module = load("validate_canonical_event_true_value_review")
    row = {
        **blank(), "final_record_action": "retain", "final_event_date": "2020-01-01",
        "reviewed_by": "D", "review_notes": "previous night",
    }
    result = module.validate([row], [blank()])
    assert result["unresolved_values"] == 0
    row["final_event_date"] = "2020-01-02"
    with pytest.raises(ValueError, match="did not change"):
        module.validate([row], [blank()])


def test_review_field_can_keep_original_or_remain_unclear() -> None:
    module = load("validate_canonical_event_true_value_review")
    row = {
        **blank("review_date"), "final_record_action": "retain",
        "final_event_date": "keep_original", "reviewed_by": "D", "review_notes": "supported",
    }
    assert module.validate([row], [blank("review_date")])["unresolved_values"] == 0
    row["final_event_date"] = "unclear"
    assert module.validate([row], [blank("review_date")])["unresolved_values"] == 1


def test_excluded_record_must_leave_values_blank() -> None:
    module = load("validate_canonical_event_true_value_review")
    row = {
        **blank(), "final_record_action": "exclude_candidate",
        "final_event_date": "2020-01-01", "reviewed_by": "D", "review_notes": "no date",
    }
    with pytest.raises(ValueError, match="leave final values blank"):
        module.validate([row], [blank()])


def test_builder_copies_suggestions_without_prefilling_final_values() -> None:
    module = load("build_canonical_event_true_value_review")
    source = {
        "candidate_id": "C", "row_id": "R", "event_id": "E",
        "recommended_actions": "correct_event_type", "claimed_event_date": "2020-01-01",
        "claimed_district": "D", "claimed_municipality": "",
        "claimed_event_type": "landslide", "claimed_hazard_type": "landslide",
        "claimed_deaths": "", "proposed_event_type": "road_obstruction",
        "proposed_hazard_type": "", "proposed_deaths": "",
        "adjudication_notes": "n", "representative_title": "t",
        "representative_url": "u", "article_evidence": "e",
    }
    row = module.build([source])[0]
    assert row["suggested_event_type"] == "road_obstruction"
    assert row["final_event_type"] == ""
