"""Tests for materializing post-correction identity decisions."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "materialize_post_correction_reconstruction.py"
_spec = importlib.util.spec_from_file_location("post_correction_reconstruction", MODULE_PATH)
module = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(module)


def _decision(**overrides: str) -> dict[str, str]:
    group = {
        "group_id": "A",
        "article_mapping_ids": ["PCR-001-A01"],
        "event_date": "2025-01-01",
        "district": "Chitwan",
        "municipality": "",
        "event_type": "landslide",
        "hazard_type": "landslide",
        "deaths": "not_reported",
        "evidence": "Specific failure.",
    }
    row = {
        "queue_id": "PCR-001",
        "row_id": "PCF-001",
        "sample_role": "fresh_probability",
        "correction_layer": "",
        "event_id": "old-1",
        "cluster_id": "cluster-1",
        "article_mapping_ids_json": '["PCR-001-A01", "PCR-001-A02"]',
        "final_resolution": "recluster_articles",
        "final_event_groups_json": json.dumps([group]),
        "excluded_article_mapping_ids_json": '["PCR-001-A02"]',
        "reviewed_by": "reviewer",
        "review_notes": "resolved",
    }
    row.update(overrides)
    return row


def _mapping() -> list[dict[str, str]]:
    return [
        {
            "mapping_id": "PCR-001-A01",
            "article_url": "https://a",
            "source": "s",
            "title": "A",
        },
        {
            "mapping_id": "PCR-001-A02",
            "article_url": "https://b",
            "source": "s",
            "title": "B",
        },
    ]


def test_materialize_preserves_groups_and_exclusions() -> None:
    groups, exclusions, unresolved = module.materialize([_decision()], _mapping())
    assert len(groups) == len(exclusions) == 1
    assert unresolved == []
    assert json.loads(groups[0]["article_urls_json"]) == ["https://a"]
    assert exclusions[0]["article_url"] == "https://b"
    assert groups[0]["candidate_event_id"].startswith("postcorr_candidate_")


def test_unclear_decision_retains_original_as_unresolved() -> None:
    decision = _decision(
        final_resolution="unclear",
        final_event_groups_json="",
        excluded_article_mapping_ids_json="",
    )
    groups, exclusions, unresolved = module.materialize([decision], _mapping())
    assert groups == []
    assert exclusions == []
    assert unresolved[0]["old_event_id"] == "old-1"
    assert unresolved[0]["production_status"] == "unresolved_original_event_retained"


def test_candidate_event_id_is_deterministic() -> None:
    group = {
        "group_id": "A",
        "article_mapping_ids": ["m2", "m1"],
        "event_date": "2025-01-01",
        "district": "Chitwan",
        "evidence": "Evidence",
    }
    assert module.candidate_event_id("old", group) == module.candidate_event_id(
        "old", group
    )
