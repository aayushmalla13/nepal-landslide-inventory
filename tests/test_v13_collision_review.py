"""Tests for v1.3 collision review preparation and validation."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load(name: str):
    path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_prepare_prefills_only_no_match_candidates() -> None:
    module = load("prepare_v13_collision_review.py")
    rows = [
        {"top_collision_tier": "none", "final_action": "", "reviewed_by": "", "collision_review_notes": ""},
        {"top_collision_tier": "high", "final_action": "", "reviewed_by": "", "collision_review_notes": ""},
    ]
    prepared = module.prepare(rows)
    assert prepared[0]["final_action"] == "new_event"
    assert prepared[0]["reviewed_by"] == "collision_screen_v1"
    assert prepared[1]["final_action"] == ""
    assert prepared[1]["reviewed_by"] == ""


def test_validator_targets_v13_artifacts() -> None:
    module = load("validate_v13_collision_decisions.py")
    assert module.core.TEMPLATE.name == "v13_reconstruction_COLLISION_DECISIONS.csv"
    assert module.core.PAIRS.name == "v13_reconstruction_COLLISION_PAIRS.csv"
    assert module.core.DEFAULT_COMPLETED.name == "v13_reconstruction_COLLISION_DECISIONS_COMPLETED.csv"
    assert module.core.VALIDATION_OUTPUT.name == "v13_collision_validation.json"
