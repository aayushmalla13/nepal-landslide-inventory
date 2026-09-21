"""Tests for the bundle-safe post-correction identity plan."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load():
    path = ROOT / "scripts" / "materialize_post_correction_identity_plan.py"
    spec = importlib.util.spec_from_file_location("postcorr_identity", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def final_row(candidate: str, old: str, action: str, target: str = ""):
    return {
        "candidate_event_id": candidate,
        "old_event_id": old,
        "final_candidate_action": action,
        "merge_candidate_event_id": target,
        "reviewed_by_final": "reviewer",
        "final_collision_notes": "note",
    }


def mapping(old: str, resolution: str = "recluster_articles"):
    return {
        "event_id": old,
        "cluster_id": f"cluster-{old}",
        "final_resolution": resolution,
        "reviewed_by": "reviewer",
        "review_notes": "note",
    }


def source(old: str):
    return {
        "event_id": old,
        "event_date_ad": "2020-01-01",
        "district": "Kaski",
        "municipality": "Pokhara",
    }


def test_final_unclear_blocks_entire_old_event_bundle() -> None:
    module = load()
    rows = [
        final_row("candidate-a", "old-a", "new_event"),
        final_row("candidate-b", "old-a", "unclear"),
    ]
    blocked = module.final_blocked_old_ids(rows, set())
    assert blocked == {"old-a"}


def test_block_propagates_through_candidate_merge_dependency() -> None:
    module = load()
    rows = [
        final_row("candidate-a", "old-a", "unclear"),
        final_row("candidate-b", "old-b", "merge_candidate", "candidate-a"),
    ]
    blocked = module.final_blocked_old_ids(rows, set())
    assert blocked == {"old-a", "old-b"}


def test_materialize_preserves_mapping_and_collision_blocks() -> None:
    module = load()
    final = [final_row("candidate-a", "old-a", "new_event")]
    eligible = [{"candidate_event_id": "candidate-a", "old_event_id": "old-a"}]
    upstream_blocked = [{"candidate_event_id": "blocked", "old_event_id": "old-b"}]
    result = module.materialize(
        final,
        eligible,
        [],
        [],
        upstream_blocked,
        [mapping("old-a"), mapping("old-b"), mapping("old-c", "unclear")],
        [],
        [source("old-a"), source("old-b"), source("old-c")],
    )
    assert [row["old_event_id"] for row in result["remove"]] == ["old-a"]
    assert len(result["new"]) == 1
    assert {row["old_event_id"] for row in result["retained_old"]} == {
        "old-b",
        "old-c",
    }
    assert len(result["blocked_candidates"]) == 1
    assert set(result["blocked_candidates"][0]) == set(module.candidate_base({})) | {
        "blocked_reason",
        "production_status",
    }
