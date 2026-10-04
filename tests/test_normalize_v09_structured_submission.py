"""Tests for the documented v0.9 structured submission normalization."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load():
    path = ROOT / "scripts" / "normalize_v09_structured_submission.py"
    spec = importlib.util.spec_from_file_location("normalize_v09_structured", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_normalizes_explicit_no_casualty_evidence_to_zero() -> None:
    module = load()
    row = {
        "queue_id": "V9R-097",
        "recommended_actions": "correct_hazard_type;correct_deaths",
        "claimed_deaths": "",
        "final_deaths": "",
        "final_record_action": "retain",
        "review_notes": "Reports explicitly confirm no human casualties.",
    }
    result = module.normalize([row])
    assert result[0]["final_deaths"] == "0"
    assert "blank claimed death value" in result[0]["review_notes"]
