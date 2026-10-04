"""Tests for v1.5 collision outcome and final-collision wrappers."""

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


def test_existing_outcomes_target_v15() -> None:
    module = load("materialize_v15_existing_collisions.py")
    assert module.core.NEW_OUTPUT.name == "v15_existing_collision_NEW_CANDIDATES.csv"
    assert module.core.BLOCKED_OUTPUT.name == "v15_existing_collision_BLOCKED_CANDIDATES.csv"


def test_final_pack_targets_v15() -> None:
    module = load("build_v15_final_collision_pack.py")
    assert module.core.CANDIDATES.name == "v15_existing_collision_NEW_CANDIDATES.csv"
    assert module.core.DECISIONS.name == "v15_reconstruction_FINAL_COLLISION_DECISIONS.csv"


def test_final_review_prefills_low_risk() -> None:
    module = load("prepare_v15_final_collision_review.py")
    rows = [
        {"top_candidate_collision_tier": "none", "final_candidate_action": "", "reviewed_by_final": "", "final_collision_notes": ""},
        {"top_candidate_collision_tier": "low", "final_candidate_action": "", "reviewed_by_final": "", "final_collision_notes": ""},
        {"top_candidate_collision_tier": "medium", "final_candidate_action": "", "reviewed_by_final": "", "final_collision_notes": ""},
    ]
    assert [r["final_candidate_action"] for r in module.prepare(rows)] == ["new_event", "new_event", ""]


def test_final_validator_targets_v15() -> None:
    module = load("validate_v15_final_collisions.py")
    assert module.core.DEFAULT_COMPLETED.name == "v15_reconstruction_FINAL_COLLISION_DECISIONS_COMPLETED.csv"
    assert module.core.VALIDATION.name == "v15_final_collision_validation.json"
