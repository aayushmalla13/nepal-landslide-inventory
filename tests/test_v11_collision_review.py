"""Tests for the v1.1 collision review preparation and validation wrappers."""

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


def test_prepare_prefills_only_no_match_rows() -> None:
    module = load("prepare_v11_collision_review.py")
    rows = module.prepare(
        [
            {"top_collision_tier": "none", "final_action": "", "reviewed_by": "", "collision_review_notes": ""},
            {"top_collision_tier": "medium", "final_action": "", "reviewed_by": "", "collision_review_notes": ""},
        ]
    )
    assert rows[0]["final_action"] == "new_event"
    assert rows[0]["reviewed_by"] == "collision_screen_v1"
    assert rows[1]["final_action"] == ""


def test_validator_targets_v11_artifacts() -> None:
    module = load("validate_v11_collision_decisions.py")
    assert module.core.DEFAULT_COMPLETED.name == (
        "v11_reconstruction_COLLISION_DECISIONS_COMPLETED.csv"
    )
    assert module.core.PAIRS.name == "v11_reconstruction_COLLISION_PAIRS.csv"
