"""Tests for final post-correction candidate collision review."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _candidate(candidate_id: str, evidence: str) -> dict[str, str]:
    return {
        "candidate_event_id": candidate_id,
        "old_event_id": "old",
        "event_date": "2025-07-10",
        "district": "Kaski",
        "municipality": "Pokhara",
        "event_type": "landslide",
        "hazard_type": "landslide",
        "evidence": evidence,
        "article_urls_json": '["https://same"]',
    }


def test_candidate_compare_treats_shared_source_as_review_signal() -> None:
    module = _load(
        "build_final_collision", "scripts/build_post_correction_final_collision_pack.py"
    )
    result = module.compare(
        _candidate("one", "Pokhara hillside failure"),
        _candidate("two", "Pokhara hillside failure"),
    )
    assert result is not None
    assert result["collision_tier"] == "high"
    assert "same_reconstruction_source" in result["reasons"]


def _template(candidate_id: str) -> dict[str, str]:
    return {
        "candidate_event_id": candidate_id,
        "final_candidate_action": "",
        "merge_candidate_event_id": "",
        "reviewed_by_final": "",
        "final_collision_notes": "",
    }


def test_validator_accepts_merge_into_retained_candidate() -> None:
    module = _load(
        "validate_final_collision", "scripts/validate_post_correction_final_collisions.py"
    )
    first = {
        **_template("one"),
        "final_candidate_action": "merge_candidate",
        "merge_candidate_event_id": "two",
        "reviewed_by_final": "reviewer",
        "final_collision_notes": "same failure",
    }
    second = {
        **_template("two"),
        "final_candidate_action": "new_event",
        "reviewed_by_final": "reviewer",
    }
    pairs = [{"candidate_event_id_a": "one", "candidate_event_id_b": "two"}]
    result = module.validate([first, second], [_template("one"), _template("two")], pairs)
    assert result["action_counts"] == {"merge_candidate": 1, "new_event": 1}


def test_validator_rejects_merge_chain() -> None:
    module = _load(
        "validate_final_collision_chain",
        "scripts/validate_post_correction_final_collisions.py",
    )
    first = {
        **_template("one"),
        "final_candidate_action": "merge_candidate",
        "merge_candidate_event_id": "two",
        "reviewed_by_final": "reviewer",
        "final_collision_notes": "same failure",
    }
    second = {
        **_template("two"),
        "final_candidate_action": "merge_candidate",
        "merge_candidate_event_id": "one",
        "reviewed_by_final": "reviewer",
        "final_collision_notes": "same failure",
    }
    pairs = [{"candidate_event_id_a": "one", "candidate_event_id_b": "two"}]
    with pytest.raises(ValueError, match="target must be retained"):
        module.validate([first, second], [_template("one"), _template("two")], pairs)


def test_materializer_blocks_entire_old_event_bundle() -> None:
    module = _load(
        "materialize_existing_collision",
        "scripts/materialize_post_correction_existing_collisions.py",
    )
    rows = [
        {"candidate_event_id": "one", "old_event_id": "old", "final_action": "new_event"},
        {"candidate_event_id": "two", "old_event_id": "old", "final_action": "unclear"},
    ]
    new, merges, excluded, blocked, blocked_old = module.materialize(rows)
    assert new == merges == excluded == []
    assert len(blocked) == 2
    assert blocked_old == {"old"}
