"""Tests for the post-correction structured-attribute review builder."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load():
    path = ROOT / "scripts" / "build_post_correction_structured_attribute_review.py"
    spec = importlib.util.spec_from_file_location("post_structured_review", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_builder_copies_suggestions_without_prefilling_final_values() -> None:
    module = load()
    source = {
        "queue_id": "PCR-001",
        "row_id": "PCF-001",
        "event_id": "event_1",
        "recommended_actions": "correct_event_type;correct_deaths",
        "claimed_event_date": "2020-01-01",
        "claimed_district": "Chitwan",
        "claimed_event_type": "landslide",
        "claimed_hazard_type": "landslide",
        "claimed_deaths": "",
        "proposed_event_type": "road_obstruction",
        "proposed_hazard_type": "",
        "proposed_deaths": "1",
        "audit_notes": "evidence reviewed",
        "representative_title": "Road blocked",
        "representative_url": "https://example.test",
        "article_evidence": "Specific road-blocking failure.",
    }
    row = module.build([source])[0]
    assert row["suggested_event_type"] == "road_obstruction"
    assert row["suggested_deaths"] == "1"
    assert row["final_record_action"] == ""
    assert row["final_event_type"] == ""
    assert row["final_deaths"] == ""
