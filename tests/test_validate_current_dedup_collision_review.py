"""Tests for validation of current dedup collision review decisions."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def load():
    path = ROOT / "scripts" / "validate_current_dedup_collision_review.py"
    spec = importlib.util.spec_from_file_location("validate_current_collision", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def row(pair_id: str, left: str, right: str) -> dict[str, str]:
    return {
        "pair_id": pair_id, "left_event_id": left, "right_event_id": right,
        "decision": "", "merge_survivor_event_id": "", "reviewed_by": "",
        "review_notes": "", "district": "Dhading",
    }


def test_valid_merge_and_distinct_decisions_pass() -> None:
    module = load()
    template = [row("pair-1", "a", "b"), row("pair-2", "c", "d")]
    completed = [dict(item) for item in template]
    completed[0].update(decision="merge", merge_survivor_event_id="a", reviewed_by="human", review_notes="same ward and victims")
    completed[1].update(decision="keep_distinct", reviewed_by="human")
    result = module.validate(completed, template)
    assert result["decision_counts"] == {"merge": 1, "keep_distinct": 1}


def test_transitive_merge_cannot_contradict_keep_distinct() -> None:
    module = load()
    template = [row("ab", "a", "b"), row("bc", "b", "c"), row("ac", "a", "c")]
    completed = [dict(item) for item in template]
    completed[0].update(decision="merge", merge_survivor_event_id="a", reviewed_by="human", review_notes="same event")
    completed[1].update(decision="merge", merge_survivor_event_id="b", reviewed_by="human", review_notes="same event")
    completed[2].update(decision="keep_distinct", reviewed_by="human")
    with pytest.raises(ValueError, match="transitive merge"):
        module.validate(completed, template)


def test_frozen_evidence_column_cannot_change() -> None:
    module = load()
    template = [row("pair-1", "a", "b")]
    completed = [dict(template[0])]
    completed[0].update(decision="keep_distinct", reviewed_by="human", district="Other")
    with pytest.raises(ValueError, match="frozen column"):
        module.validate(completed, template)


def test_component_with_two_survivors_is_reported_as_blocked() -> None:
    module = load()
    template = [row("ab", "a", "b"), row("bc", "b", "c")]
    completed = [dict(item) for item in template]
    completed[0].update(decision="merge", merge_survivor_event_id="a", reviewed_by="human", review_notes="same event")
    completed[1].update(decision="merge", merge_survivor_event_id="c", reviewed_by="human", review_notes="same event")
    result = module.validate(completed, template)
    assert result["survivor_conflict_count"] == 1
    assert result["status"] == "blocked_unresolved_or_inconsistent_collision_decisions"


def test_component_survivor_may_be_outside_one_edge() -> None:
    module = load()
    template = [row("ab", "a", "b"), row("bc", "b", "c"), row("ac", "a", "c")]
    completed = [dict(item) for item in template]
    for item in completed:
        item.update(
            decision="merge", merge_survivor_event_id="c",
            reviewed_by="human", review_notes="same event",
        )

    result = module.validate(completed, template)

    assert result["survivor_conflict_count"] == 0
    assert result["status"] == "validated_collision_batch_not_yet_applied"
