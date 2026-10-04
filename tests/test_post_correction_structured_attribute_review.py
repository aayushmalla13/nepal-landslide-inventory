"""Tests for post-correction structured-attribute review validation."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load():
    path = ROOT / "scripts" / "validate_post_correction_structured_attribute_review.py"
    spec = importlib.util.spec_from_file_location("post_structured_validate", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def blank(actions: str = "correct_event_type") -> dict[str, str]:
    return {
        "queue_id": "PCR-001",
        "recommended_actions": actions,
        "claimed_event_type": "landslide",
        "claimed_hazard_type": "landslide",
        "claimed_deaths": "",
        "final_record_action": "",
        "final_event_type": "",
        "final_hazard_type": "",
        "final_deaths": "",
        "reviewed_by": "",
        "review_notes": "",
    }


def test_validates_changed_event_type() -> None:
    module = load()
    row = {
        **blank(),
        "final_record_action": "retain",
        "final_event_type": "road_obstruction",
        "reviewed_by": "reviewer",
        "review_notes": "road blocked",
    }
    result = module.validate([row], [blank()])
    assert result["changed_field_counts"] == {"event_type": 1}


def test_rejects_unchanged_confirmed_value() -> None:
    module = load()
    row = {
        **blank(),
        "final_record_action": "retain",
        "final_event_type": "landslide",
        "reviewed_by": "reviewer",
        "review_notes": "unchanged",
    }
    with pytest.raises(ValueError, match="did not change"):
        module.validate([row], [blank()])


def test_non_retained_row_must_leave_values_blank() -> None:
    module = load()
    row = {
        **blank(),
        "final_record_action": "exclude_candidate",
        "final_event_type": "other",
        "reviewed_by": "reviewer",
        "review_notes": "not usable",
    }
    with pytest.raises(ValueError, match="leave final values blank"):
        module.validate([row], [blank()])
