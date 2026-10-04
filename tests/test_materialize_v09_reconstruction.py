"""Tests for v0.9 reconstruction-plan materialization."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "materialize_v09_reconstruction.py"
_spec = importlib.util.spec_from_file_location("materialize_v09", MODULE_PATH)
module = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(module)


def test_materialize_keeps_unclear_original_unapplied() -> None:
    decision = {
        "queue_id": "V9R-001",
        "row_id": "V8F-001",
        "event_id": "event_1",
        "cluster_id": "cluster_1",
        "article_mapping_ids_json": '["V9R-001-A01"]',
        "final_resolution": "unclear",
        "final_event_groups_json": "",
        "excluded_article_mapping_ids_json": "",
        "reviewed_by": "reviewer",
        "review_notes": "insufficient date evidence",
    }
    groups, exclusions, unresolved = module.materialize([decision], [])
    assert groups == []
    assert exclusions == []
    assert unresolved[0]["production_status"] == "unresolved_original_event_retained"


def test_materialize_creates_stable_group_and_exclusion() -> None:
    group = {
        "group_id": "G1",
        "article_mapping_ids": ["V9R-001-A01"],
        "event_date": "2024-07-01",
        "district": "Kaski",
        "municipality": "",
        "event_type": "landslide",
        "hazard_type": "landslide",
        "deaths": "not_reported",
        "evidence": "Article states the event.",
    }
    decision = {
        "queue_id": "V9R-001",
        "row_id": "V8F-001",
        "event_id": "event_1",
        "cluster_id": "cluster_1",
        "article_mapping_ids_json": '["V9R-001-A01", "V9R-001-A02"]',
        "final_resolution": "recluster_articles",
        "final_event_groups_json": json.dumps([group]),
        "excluded_article_mapping_ids_json": '["V9R-001-A02"]',
        "reviewed_by": "reviewer",
        "review_notes": "reviewed",
    }
    mapping = [
        {"mapping_id": "V9R-001-A01", "article_url": "u1", "source": "s", "title": "t"},
        {"mapping_id": "V9R-001-A02", "article_url": "u2", "source": "s", "title": "t"},
    ]
    groups, exclusions, unresolved = module.materialize([decision], mapping)
    assert groups[0]["candidate_event_id"].startswith("v09_candidate_")
    assert json.loads(groups[0]["article_urls_json"]) == ["u1"]
    assert exclusions[0]["article_url"] == "u2"
    assert unresolved == []
