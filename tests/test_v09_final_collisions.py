"""Tests for v0.9 collision outcome materialization and final screening."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str):
    path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


materialize = _load("materialize_v09_existing_collisions.py")
final = _load("build_v09_final_collision_pack.py")


def test_unclear_candidate_blocks_entire_old_event_bundle() -> None:
    rows = [
        {"candidate_event_id": "a", "old_event_id": "old", "final_action": "new_event"},
        {"candidate_event_id": "b", "old_event_id": "old", "final_action": "unclear"},
    ]
    new, merges, excluded, blocked, blocked_ids = materialize.materialize(rows)
    assert new == merges == excluded == []
    assert len(blocked) == 2
    assert blocked_ids == {"old"}


def test_candidate_compare_ignores_distant_district() -> None:
    first = {
        "article_urls_json": '["u1"]',
        "district": "Kaski",
        "event_date": "2024-01-01",
        "municipality": "Pokhara",
        "event_type": "landslide",
        "hazard_type": "landslide",
        "evidence": "event one",
        "old_event_id": "old1",
    }
    second = {
        **first,
        "article_urls_json": '["u2"]',
        "district": "Myagdi",
        "event_date": "2024-02-01",
        "old_event_id": "old2",
    }
    assert final.compare(first, second) is None


def test_candidate_compare_ignores_unresolved_date_for_unrelated_candidates() -> None:
    first = {
        "article_urls_json": '["u1"]',
        "district": "Kaski",
        "event_date": "unclear",
        "municipality": "Pokhara",
        "event_type": "landslide",
        "hazard_type": "landslide",
        "evidence": "event one",
        "old_event_id": "old1",
    }
    second = {
        **first,
        "article_urls_json": '["u2"]',
        "event_date": "2024-01-01",
        "old_event_id": "old2",
    }
    assert final.compare(first, second) is None


def test_candidate_compare_surfaces_same_source_with_unresolved_date() -> None:
    first = {
        "article_urls_json": '["u1"]',
        "district": "Kaski",
        "event_date": "unclear",
        "municipality": "Pokhara",
        "event_type": "landslide",
        "hazard_type": "landslide",
        "evidence": "event one",
        "old_event_id": "old1",
    }
    second = {
        **first,
        "article_urls_json": '["u2"]',
        "event_date": "2024-01-01",
    }
    result = final.compare(first, second)
    assert result is not None
    assert result["collision_tier"] == "low"
    assert result["day_difference"] == ""
    assert "unresolved_date" in result["reasons"]
