"""Tests for v0.9 true-value identity reconciliation."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load():
    path = ROOT / "scripts" / "validate_v09_true_value_review.py"
    spec = importlib.util.spec_from_file_location("v09_true_value", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_overlap_catches_removed_events_and_merge_targets() -> None:
    module = load()
    reviewed = [{"event_id": "removed"}, {"event_id": "target"}, {"event_id": "safe"}]
    removed = [{"old_event_id": "removed"}]
    merges = [{"merge_existing_event_id": "target"}]
    assert module.overlapping_event_ids(reviewed, removed, merges) == {"removed", "target"}


def test_v09_validator_uses_v08_source() -> None:
    module = load()
    assert module.RELEASE.parent.name == "nepal_landslide_inventory_v0.8.0_candidate_20260923"
