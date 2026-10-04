"""Tests for v0.9 structured-attribute review wiring."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name: str):
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_builder_preserves_suggestions_but_blanks_final_values() -> None:
    module = load("build_v09_structured_attribute_review")
    source = {
        "queue_id": "V9R-001", "row_id": "V8F-001", "event_id": "event_1",
        "recommended_actions": "correct_event_type", "claimed_event_date": "2020-01-01",
        "claimed_district": "Chitwan", "claimed_event_type": "landslide",
        "claimed_hazard_type": "landslide", "claimed_deaths": "",
        "proposed_event_type": "road_obstruction", "proposed_hazard_type": "",
        "proposed_deaths": "", "audit_notes": "", "representative_title": "Road blocked",
        "representative_url": "https://example.test", "article_evidence": "Road blocked.",
    }
    row = module.build([source])[0]
    assert row["suggested_event_type"] == "road_obstruction"
    assert row["final_event_type"] == ""
    assert row["final_record_action"] == ""


def test_validator_uses_v09_review_names() -> None:
    module = load("validate_v09_structured_attribute_review")
    assert module.TEMPLATE.name == "v09_structured_attribute_REVIEW.csv"
    assert module.DEFAULT_COMPLETED.name == "v09_structured_attribute_REVIEW_COMPLETED.csv"
