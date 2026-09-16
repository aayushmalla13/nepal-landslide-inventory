"""Tests for the canonical-event identity release plan."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load():
    path = ROOT / "scripts" / "materialize_canonical_event_identity_plan.py"
    spec = importlib.util.spec_from_file_location("materialize_identity", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def collision(action: str, target: str = "") -> dict[str, str]:
    return {
        "candidate_event_id": f"candidate-{action}", "old_event_id": "old-1",
        "event_date": "2020-01-01", "district": "D", "municipality": "M",
        "event_type": "landslide", "hazard_type": "landslide", "deaths": "0",
        "article_mapping_ids_json": "[]", "article_urls_json": "[]",
        "evidence": "e", "reviewed_by_collision": "D",
        "collision_review_notes": "n", "final_collision_action": action,
        "merge_target_event_id": target,
    }


def test_materialize_routes_new_merge_and_excluded_candidates() -> None:
    module = load()
    frozen = [
        {"event_id": "old-1", "dedup_cluster_id": "c1", "event_date_ad": "2020-01-01", "district": "D", "municipality": "M", "representative_url": "u1"},
        {"event_id": "target", "dedup_cluster_id": "c2", "event_date_ad": "2020-01-01", "district": "D", "municipality": "M", "representative_url": "u2"},
    ]
    mapping = [{"event_id": "old-1", "cluster_id": "c1", "final_resolution": "recluster_articles", "reviewed_by": "D", "review_notes": "n"}]
    collisions = [collision("new_event"), collision("merge_existing", "target"), collision("exclude_candidate")]
    removed, new, merges, excluded = module.materialize(collisions, mapping, frozen, [])
    assert len(removed) == len(new) == len(merges) == len(excluded) == 1
    assert merges[0]["merge_target_event_id"] == "target"


def test_date_exclusion_is_preserved() -> None:
    module = load()
    frozen = [{"event_id": "old-1", "dedup_cluster_id": "c1", "event_date_ad": "2020-01-01", "district": "D", "municipality": "", "representative_url": "u"}]
    mapping = [{"event_id": "old-1", "cluster_id": "c1", "final_resolution": "exclude_cluster", "reviewed_by": "D", "review_notes": "n"}]
    date_excluded = [{"candidate_event_id": "x", "old_event_id": "old-1", "district": "D", "evidence": "e", "reviewed_by": "D", "review_notes": "no date"}]
    _removed, _new, _merges, excluded = module.materialize([], mapping, frozen, date_excluded)
    assert excluded[0]["exclusion_stage"] == "date_review"
