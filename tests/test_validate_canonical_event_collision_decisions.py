"""Tests for final reconstruction collision-decision validation."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load():
    path = ROOT / "scripts" / "validate_canonical_event_collision_decisions.py"
    spec = importlib.util.spec_from_file_location("validate_collisions", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def blank(candidate_id: str = "candidate-1") -> dict[str, str]:
    return {
        "candidate_event_id": candidate_id, "event_date": "2020-01-01",
        "final_collision_action": "", "merge_target_event_id": "",
        "reviewed_by_collision": "", "collision_review_notes": "",
    }


def test_new_event_requires_no_target() -> None:
    module = load()
    row = {**blank(), "final_collision_action": "new_event", "reviewed_by_collision": "D"}
    result = module.validate([row], [blank()], [])
    assert result["action_counts"] == {"new_event": 1}


def test_merge_requires_listed_target_and_notes() -> None:
    module = load()
    row = {
        **blank(), "final_collision_action": "merge_existing",
        "merge_target_event_id": "existing-1", "reviewed_by_collision": "D",
        "collision_review_notes": "Same physical event.",
    }
    pairs = [{"candidate_event_id": "candidate-1", "existing_event_id": "existing-1"}]
    result = module.validate([row], [blank()], pairs)
    assert result["unique_merge_targets"] == 1


def test_unknown_merge_target_is_rejected() -> None:
    module = load()
    row = {
        **blank(), "final_collision_action": "exclude_duplicate",
        "merge_target_event_id": "other", "reviewed_by_collision": "D",
        "collision_review_notes": "Duplicate.",
    }
    pairs = [{"candidate_event_id": "candidate-1", "existing_event_id": "existing-1"}]
    with pytest.raises(ValueError, match="absent from its collision pairs"):
        module.validate([row], [blank()], pairs)
