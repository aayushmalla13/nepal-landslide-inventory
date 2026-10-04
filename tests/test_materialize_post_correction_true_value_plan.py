"""Tests for post-correction true-value plan materialization."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load():
    path = ROOT / "scripts" / "materialize_post_correction_true_value_plan.py"
    spec = importlib.util.spec_from_file_location("post_true_plan", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def source() -> dict[str, str]:
    return {
        "event_id": "event_1",
        "event_date_ad": "2020-01-02",
        "district": "Kathmandu",
        "province": "Bagmati",
        "municipality": "Kathmandu Metropolitan City",
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
        "recommended_actions": "correct_district;correct_municipality",
        "reviewed_action": action,
        "proposed_event_date": "",
        "proposed_district": "Lalitpur",
        "proposed_municipality": "not_established",
        "proposed_event_type": "",
        "proposed_hazard_type": "",
        "proposed_deaths": "",
        "reviewed_by": "reviewer",
        "review_notes": "dateline corrected",
    }


def test_materializes_correction_and_clears_municipality() -> None:
    module = load()
    corrections, exclusions, no_change = module.materialize(
        [completed()], [source()]
    )
    assert not exclusions and not no_change
    assert corrections[0]["final_district"] == "Lalitpur"
    assert corrections[0]["final_municipality"] == ""
    assert corrections[0]["changed_fields_json"] == '["district", "municipality"]'


def test_materializes_exclusion() -> None:
    module = load()
    row = completed("exclude_candidate")
    row["proposed_district"] = ""
    row["proposed_municipality"] = ""
    corrections, exclusions, no_change = module.materialize([row], [source()])
    assert not corrections and not no_change
    assert exclusions[0]["production_status"] == "planned_exclude_existing_event"


def test_keep_original_is_preserved_as_reviewed_no_change() -> None:
    module = load()
    row = completed()
    row["proposed_district"] = "keep_original"
    row["proposed_municipality"] = "keep_original"
    corrections, exclusions, no_change = module.materialize([row], [source()])
    assert not corrections and not exclusions
    assert no_change[0]["production_status"] == "reviewed_retain_no_change"


def test_rejects_unresolved_action() -> None:
    module = load()
    row = completed("unclear")
    with pytest.raises(ValueError, match="unresolved"):
        module.materialize([row], [source()])
