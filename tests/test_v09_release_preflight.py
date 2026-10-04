"""Tests for v0.9 release preflight location handling."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load():
    path = ROOT / "scripts" / "resolve_v09_release_preflight.py"
    spec = importlib.util.spec_from_file_location("v09_preflight", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cross_district_candidate_becomes_documented_exclusion() -> None:
    module = load()
    candidate = {
        "candidate_event_id": module.TARGET,
        "district": "Dailekh/Kalikot",
        "reviewed_by_final": "reviewer",
        "final_collision_notes": "Distinct physical event.",
    }
    columns = [
        "candidate_event_id", "district", "exclusion_stage",
        "duplicate_of_candidate_event_id", "reviewed_by", "review_notes",
        "production_status",
    ]
    row = module.exclusion_row(candidate, columns)
    assert row["exclusion_stage"] == "release_preflight_location"
    assert "single canonical district" in row["review_notes"]
