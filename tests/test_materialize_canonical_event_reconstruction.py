"""Tests for normalized canonical-event reconstruction inputs."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load():
    path = ROOT / "scripts" / "materialize_canonical_event_reconstruction.py"
    spec = importlib.util.spec_from_file_location("materialize_reconstruction", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_materialize_preserves_group_membership_and_exclusions() -> None:
    module = load()
    group = {
        "group_id": "A", "article_mapping_ids": ["CEC-001-A01"],
        "event_date": "2025-01-01", "district": "Chitwan", "municipality": "",
        "event_type": "landslide", "hazard_type": "landslide",
        "deaths": "not_reported", "evidence": "Specific failure.",
    }
    decision = {
        "candidate_id": "CEC-001", "event_id": "old-1", "cluster_id": "cluster-1",
        "final_resolution": "recluster_articles", "final_event_groups_json": json.dumps([group]),
        "excluded_article_mapping_ids_json": '["CEC-001-A02"]',
        "reviewed_by": "reviewer_D", "review_notes": "resolved",
    }
    mapping = [
        {"mapping_id": "CEC-001-A01", "article_url": "https://a", "source": "s", "title": "A"},
        {"mapping_id": "CEC-001-A02", "article_url": "https://b", "source": "s", "title": "B"},
    ]
    groups, exclusions = module.materialize([decision], mapping)
    assert len(groups) == len(exclusions) == 1
    assert json.loads(groups[0]["article_urls_json"]) == ["https://a"]
    assert exclusions[0]["article_url"] == "https://b"
    assert groups[0]["candidate_event_id"].startswith("candidate_")


def test_candidate_event_id_is_deterministic() -> None:
    module = load()
    group = {
        "group_id": "A", "article_mapping_ids": ["m2", "m1"],
        "event_date": "2025-01-01", "district": "Chitwan", "evidence": "Evidence",
    }
    assert module.candidate_event_id("old", group) == module.candidate_event_id("old", group)
