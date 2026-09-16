"""Tests for canonical-event true-value plan materialization."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load():
    path = ROOT / "scripts" / "materialize_canonical_event_true_value_plan.py"
    spec = importlib.util.spec_from_file_location("true_value_plan", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def frozen() -> dict[str, str]:
    return {
        "event_id": "event_1", "event_date_ad": "2020-01-02", "district": "Kathmandu",
        "province": "Bagmati", "municipality": "", "event_type": "landslide",
        "hazard_type": "landslide", "deaths": "", "representative_url": "https://example.test",
    }


def completed(action: str = "retain") -> dict[str, str]:
    return {
        "candidate_id": "CEC-001", "event_id": "event_1", "recommended_actions": "correct_district",
        "final_record_action": action, "final_event_date": "", "final_district": "Lalitpur",
        "final_municipality": "", "final_event_type": "", "final_hazard_type": "",
        "final_deaths": "", "reviewed_by": "reviewer_D", "review_notes": "dateline corrected",
    }


def test_materializes_correction_and_derived_province() -> None:
    module = load()
    corrections, exclusions = module.materialize([completed()], [frozen()])
    assert not exclusions
    assert corrections[0]["final_district"] == "Lalitpur"
    assert corrections[0]["final_province"] == "Bagmati"
    assert corrections[0]["changed_fields_json"] == '["district"]'


def test_materializes_exclusion_without_correction_values() -> None:
    module = load()
    row = completed("exclude_candidate")
    row["final_district"] = ""
    corrections, exclusions = module.materialize([row], [frozen()])
    assert not corrections
    assert exclusions[0]["production_status"] == "planned_exclude_existing_event"


def test_rejects_retained_row_without_material_change() -> None:
    module = load()
    row = completed()
    row["final_district"] = "Kathmandu"
    with pytest.raises(ValueError, match="no material change"):
        module.materialize([row], [frozen()])


def test_keep_original_only_maps_blank_deaths_to_not_reported() -> None:
    module = load()
    assert module.plan_value("keep_original", "", deaths=True) == "not_reported"
    assert module.plan_value("keep_original", "") == ""
