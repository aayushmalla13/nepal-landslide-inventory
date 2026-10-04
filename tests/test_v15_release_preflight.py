"""Tests for the v1.5 exact-date release preflight."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load():
    path = ROOT / "scripts/resolve_v15_release_preflight.py"
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_exact_date_gate_and_exclusion() -> None:
    module = load()
    assert module.has_exact_date({"event_date": "2024-07-01"})
    assert not module.has_exact_date({"event_date": "unclear"})
    row = module.exclusion_row(
        {"event_date": "unclear", "reviewed_by_final": "aayush"},
        ["event_date", "exclusion_stage", "reviewed_by", "review_notes", "production_status"],
    )
    assert row["exclusion_stage"] == "release_preflight_exact_date"
    assert "exact YYYY-MM-DD" in row["review_notes"]
