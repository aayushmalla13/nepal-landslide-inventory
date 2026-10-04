"""Tests for the v1.4 exact-date release preflight."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load():
    path = ROOT / "scripts/resolve_v14_release_preflight.py"
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_exact_date_gate() -> None:
    module = load()
    assert module.has_exact_date({"event_date": "2024-07-01"})
    assert not module.has_exact_date({"event_date": "unclear"})
    assert not module.has_exact_date({"event_date": ""})


def test_unresolved_date_candidate_becomes_documented_exclusion() -> None:
    module = load()
    candidate = {
        "candidate_event_id": "v14_candidate_example",
        "event_date": "unclear",
        "reviewed_by_final": "aayush",
        "final_collision_notes": "Distinct physical event.",
    }
    columns = [
        "candidate_event_id",
        "event_date",
        "exclusion_stage",
        "duplicate_of_candidate_event_id",
        "reviewed_by",
        "review_notes",
        "production_status",
    ]
    row = module.exclusion_row(candidate, columns)
    assert row["exclusion_stage"] == "release_preflight_exact_date"
    assert "exact YYYY-MM-DD" in row["review_notes"]
