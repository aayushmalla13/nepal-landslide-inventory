"""Tests for post-correction true-value review validation."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load():
    path = ROOT / "scripts" / "validate_post_correction_true_value_review.py"
    spec = importlib.util.spec_from_file_location("post_true_value", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def blank(actions: str = "correct_date") -> dict[str, str]:
    return {
        "queue_id": "PCR-001",
        "event_id": "event_1",
        "recommended_actions": actions,
        "claimed_event_date": "2020-01-02",
        "claimed_district": "Chitwan",
        "claimed_municipality": "Bharatpur Metropolitan City",
        "claimed_event_type": "landslide",
        "claimed_hazard_type": "landslide",
        "claimed_deaths": "",
        "proposed_event_date": "",
        "proposed_district": "",
        "proposed_municipality": "",
        "proposed_event_type": "",
        "proposed_hazard_type": "",
        "proposed_deaths": "",
        "reviewed_action": "",
        "reviewed_by": "",
        "review_notes": "",
    }


def release() -> list[dict[str, str]]:
    return [
        {"event_id": "event_1", "event_date_ad": "2015-01-01"},
        {"event_id": "event_2", "event_date_ad": "2026-08-09"},
    ]


def test_confirmed_date_correction_requires_changed_value() -> None:
    module = load()
    row = {
        **blank(),
        "proposed_event_date": "2020-01-01",
        "reviewed_action": "retain",
        "reviewed_by": "reviewer",
        "review_notes": "previous day",
    }
    result = module.validate([row], [blank()], release())
    assert result["unresolved_count"] == 0
    row["proposed_event_date"] = "2020-01-02"
    with pytest.raises(ValueError, match="did not change"):
        module.validate([row], [blank()], release())


def test_not_established_clears_a_wrong_municipality() -> None:
    module = load()
    template = blank("correct_municipality")
    row = {
        **template,
        "proposed_municipality": "not_established",
        "reviewed_action": "retain",
        "reviewed_by": "reviewer",
        "review_notes": "residence only",
    }
    result = module.validate([row], [template], release())
    assert result["changed_field_counts"] == {"municipality": 1}


def test_keep_original_records_a_reviewed_false_positive() -> None:
    module = load()
    template = blank("correct_municipality")
    row = {
        **template,
        "proposed_municipality": "keep_original",
        "reviewed_action": "retain",
        "reviewed_by": "reviewer",
        "review_notes": "source name is a canonical alias",
    }
    result = module.validate([row], [template], release())
    assert result["retained_no_change_rows"] == ["PCR-001"]


def test_review_can_repeat_claimed_value_to_record_no_change() -> None:
    module = load()
    template = blank("review_hazard_type")
    row = {
        **template,
        "proposed_hazard_type": "landslide",
        "reviewed_action": "retain",
        "reviewed_by": "reviewer",
        "review_notes": "Corroborating source confirms the original classification.",
    }
    result = module.validate([row], [template], release())
    assert result["retained_no_change_rows"] == ["PCR-001"]


def test_unclear_record_blocks_without_proposed_values() -> None:
    module = load()
    template = blank("review_event_existence")
    row = {
        **template,
        "reviewed_action": "unclear",
        "reviewed_by": "reviewer",
        "review_notes": "source body missing",
    }
    result = module.validate([row], [template], release())
    assert result["unresolved_rows"] == ["PCR-001"]


def test_non_retained_row_rejects_proposed_values() -> None:
    module = load()
    row = {
        **blank(),
        "proposed_event_date": "2020-01-01",
        "reviewed_action": "exclude_candidate",
        "reviewed_by": "reviewer",
        "review_notes": "no exact date",
    }
    with pytest.raises(ValueError, match="leave proposed values blank"):
        module.validate([row], [blank()], release())


def test_confirmed_event_existence_can_be_retained_without_attribute_change() -> None:
    module = load()
    template = blank("review_event_existence")
    row = {
        **template,
        "reviewed_action": "retain",
        "reviewed_by": "reviewer",
        "review_notes": "Article confirms a dated landslide in the claimed district.",
    }
    result = module.validate([row], [template], release())
    assert result["retained_no_change_rows"] == ["PCR-001"]
