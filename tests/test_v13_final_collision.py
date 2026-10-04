"""Tests for v1.3 collision outcome and final-collision wrappers."""

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


def test_existing_collision_wrapper_targets_v13_outputs() -> None:
    module = load("materialize_v13_existing_collisions.py")
    assert module.core.COMPLETED.name == "v13_reconstruction_COLLISION_DECISIONS_COMPLETED.csv"
    assert module.core.NEW_OUTPUT.name == "v13_existing_collision_NEW_CANDIDATES.csv"
    assert module.core.BLOCKED_OUTPUT.name == "v13_existing_collision_BLOCKED_CANDIDATES.csv"
    assert module.core.REPORT_TITLE == "v1.3 existing-event collision outcomes"


def test_final_collision_wrapper_targets_v13_outputs() -> None:
    module = load("build_v13_final_collision_pack.py")
    assert module.core.CANDIDATES.name == "v13_existing_collision_NEW_CANDIDATES.csv"
    assert module.core.DECISIONS.name == "v13_reconstruction_FINAL_COLLISION_DECISIONS.csv"
    assert module.core.AUDIT_NAME == "v13_candidate_to_candidate_collision_v1"


def test_final_review_prefills_only_low_risk_candidates() -> None:
    module = load("prepare_v13_final_collision_review.py")
    rows = [
        {"top_candidate_collision_tier": "none", "final_candidate_action": "", "reviewed_by_final": "", "final_collision_notes": ""},
        {"top_candidate_collision_tier": "low", "final_candidate_action": "", "reviewed_by_final": "", "final_collision_notes": ""},
        {"top_candidate_collision_tier": "high", "final_candidate_action": "", "reviewed_by_final": "", "final_collision_notes": ""},
    ]
    prepared = module.prepare(rows)
    assert [row["final_candidate_action"] for row in prepared] == ["new_event", "new_event", ""]


def test_final_validator_targets_v13_artifacts() -> None:
    module = load("validate_v13_final_collisions.py")
    assert module.core.TEMPLATE.name == "v13_reconstruction_FINAL_COLLISION_DECISIONS.csv"
    assert module.core.PAIRS.name == "v13_reconstruction_FINAL_COLLISION_PAIRS.csv"
    assert module.core.DEFAULT_COMPLETED.name == (
        "v13_reconstruction_FINAL_COLLISION_DECISIONS_COMPLETED.csv"
    )
    assert module.core.VALIDATION.name == "v13_final_collision_validation.json"
