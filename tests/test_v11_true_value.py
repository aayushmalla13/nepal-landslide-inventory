"""Tests for v1.1 true-value validation and materialization wrappers."""

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


def test_validator_allows_retained_merge_targets_but_not_removed_events() -> None:
    module = load("validate_v11_true_value_review.py")
    reviewed = [{"event_id": "removed"}, {"event_id": "merge-target"}]
    removed = [{"old_event_id": "removed"}]
    merges = [{"merge_existing_event_id": "merge-target"}]
    assert module.overlapping_event_ids(reviewed, removed, merges) == {"removed"}
    assert module.core.ALLOW_MERGE_TARGETS is True


def test_materializer_targets_v11_outputs() -> None:
    module = load("materialize_v11_true_value_plan.py")
    assert module.core.COMPLETED.name == (
        "v11_remediation_BATCH_TRUE_VALUE_REVIEW_COMPLETED.csv"
    )
    assert module.core.CORRECTIONS_OUTPUT.name == "v11_true_value_plan_CORRECTIONS.csv"
    assert module.core.ALLOW_MERGE_TARGETS is True
