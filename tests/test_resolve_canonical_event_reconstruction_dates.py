"""Tests for reconstruction date-review validation and resolution."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load():
    path = ROOT / "scripts" / "resolve_canonical_event_reconstruction_dates.py"
    spec = importlib.util.spec_from_file_location("resolve_dates", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def template(candidate_id: str = "candidate-1") -> dict[str, str]:
    return {
        "candidate_event_id": candidate_id, "event_evidence": "evidence",
        "final_action": "", "resolved_event_date": "", "reviewed_by": "",
        "review_notes": "",
    }


def test_validate_accepts_date_and_exclusion() -> None:
    module = load()
    first = {**template("one"), "final_action": "set_date", "resolved_event_date": "2020-07-10", "reviewed_by": "D"}
    second = {**template("two"), "final_action": "exclude_candidate", "reviewed_by": "D"}
    module.validate([first, second], [template("one"), template("two")])


def test_validate_rejects_out_of_period_date() -> None:
    module = load()
    row = {**template(), "final_action": "set_date", "resolved_event_date": "2010-01-01", "reviewed_by": "D"}
    with pytest.raises(ValueError, match="outside the frozen inventory period"):
        module.validate([row], [template()])


def test_resolve_updates_and_excludes_candidates() -> None:
    module = load()
    groups = [
        {"candidate_event_id": "one", "event_date": "unclear", "review_notes": "original", "candidate_id": "c1", "old_event_id": "o1", "district": "D", "evidence": "E"},
        {"candidate_event_id": "two", "event_date": "unclear", "review_notes": "", "candidate_id": "c2", "old_event_id": "o2", "district": "D", "evidence": "E"},
    ]
    decisions = [
        {"candidate_event_id": "one", "final_action": "set_date", "resolved_event_date": "2020-07-10", "reviewed_by": "D", "review_notes": "resolved"},
        {"candidate_event_id": "two", "final_action": "exclude_candidate", "resolved_event_date": "", "reviewed_by": "D", "review_notes": "insufficient"},
    ]
    resolved, excluded = module.resolve(groups, decisions)
    assert [row["candidate_event_id"] for row in resolved] == ["one"]
    assert resolved[0]["event_date"] == "2020-07-10"
    assert [row["candidate_event_id"] for row in excluded] == ["two"]
