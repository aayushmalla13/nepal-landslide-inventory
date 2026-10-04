"""Tests for final v1.1 collision review preparation and validation."""

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


def test_prepare_prefills_none_and_low_only() -> None:
    module = load("prepare_v11_final_collision_review.py")
    base = {
        "final_candidate_action": "",
        "reviewed_by_final": "",
        "final_collision_notes": "",
    }
    rows = module.prepare(
        [
            {**base, "top_candidate_collision_tier": "none"},
            {**base, "top_candidate_collision_tier": "low"},
            {**base, "top_candidate_collision_tier": "medium"},
        ]
    )
    assert [row["final_candidate_action"] for row in rows] == [
        "new_event",
        "new_event",
        "",
    ]


def test_validator_targets_v11_final_artifacts() -> None:
    module = load("validate_v11_final_collisions.py")
    assert module.core.DEFAULT_COMPLETED.name == (
        "v11_reconstruction_FINAL_COLLISION_DECISIONS_COMPLETED.csv"
    )
    assert module.core.PAIRS.name == "v11_reconstruction_FINAL_COLLISION_PAIRS.csv"
