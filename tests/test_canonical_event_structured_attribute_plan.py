"""Tests for canonical-event structured-attribute plan materialization."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load():
    path = ROOT / "scripts" / "materialize_canonical_event_structured_attribute_plan.py"
    spec = importlib.util.spec_from_file_location("structured_attribute_plan", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def frozen() -> dict[str, str]:
    return {
        "event_id": "event_1", "event_date_ad": "2020-01-02", "district": "Kathmandu",
        "event_type": "landslide", "hazard_type": "landslide", "deaths": "",
        "representative_url": "https://example.test",
    }


def completed(action: str = "retain") -> dict[str, str]:
    return {
        "candidate_id": "CEC-010", "event_id": "event_1",
        "recommended_actions": "correct_event_type", "final_record_action": action,
        "final_event_type": "road_obstruction", "final_hazard_type": "",
        "final_deaths": "", "reviewed_by": "reviewer_D",
        "review_notes": "road blockage only",
    }


def test_materializes_structured_attribute_correction() -> None:
    module = load()
    corrections, exclusions = module.materialize([completed()], [frozen()])
    assert not exclusions
    assert corrections[0]["final_event_type"] == "road_obstruction"
    assert corrections[0]["changed_fields_json"] == '["event_type"]'
    assert corrections[0]["final_deaths"] == "not_reported"


def test_materializes_exclusion() -> None:
    module = load()
    row = completed("exclude_candidate")
    row["final_event_type"] = ""
    corrections, exclusions = module.materialize([row], [frozen()])
    assert not corrections
    assert exclusions[0]["production_status"] == "planned_exclude_existing_event"


def test_rejects_retained_row_without_material_change() -> None:
    module = load()
    row = completed()
    row["final_event_type"] = "landslide"
    with pytest.raises(ValueError, match="no material change"):
        module.materialize([row], [frozen()])
