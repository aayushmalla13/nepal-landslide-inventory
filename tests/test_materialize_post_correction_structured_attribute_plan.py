"""Tests for post-correction structured-attribute plan materialization."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load():
    path = ROOT / "scripts" / "materialize_post_correction_structured_attribute_plan.py"
    spec = importlib.util.spec_from_file_location("post_structured_plan", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def source() -> dict[str, str]:
    return {
        "event_id": "event_1",
        "event_date_ad": "2020-01-01",
        "district": "Chitwan",
        "event_type": "landslide",
        "hazard_type": "landslide",
        "deaths": "",
        "representative_url": "https://example.test",
    }


def completed(action: str = "retain") -> dict[str, str]:
    return {
        "queue_id": "PCR-001",
        "row_id": "PCF-001",
        "event_id": "event_1",
        "recommended_actions": "correct_event_type;correct_deaths",
        "final_record_action": action,
        "final_event_type": "road_obstruction",
        "final_hazard_type": "",
        "final_deaths": "1",
        "reviewed_by": "reviewer",
        "review_notes": "road blockage with one death",
    }


def test_materializes_structured_corrections() -> None:
    module = load()
    corrections, exclusions = module.materialize([completed()], [source()])
    assert not exclusions
    assert corrections[0]["changed_fields_json"] == '["event_type", "deaths"]'
    assert corrections[0]["final_deaths"] == "1"


def test_materializes_exclusion() -> None:
    module = load()
    row = completed("exclude_candidate")
    corrections, exclusions = module.materialize([row], [source()])
    assert not corrections
    assert exclusions[0]["production_status"] == "planned_exclude_existing_event"


def test_rejects_unresolved_action() -> None:
    module = load()
    with pytest.raises(ValueError, match="unresolved"):
        module.materialize([completed("unclear")], [source()])
