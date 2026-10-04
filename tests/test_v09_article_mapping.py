"""Tests for the v0.9 article-mapping gate."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str):
    path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


build = _load("build_v09_article_mapping_pack.py")
validate = _load("validate_v09_article_mapping.py")


def _candidate(actions: str, count: str = "1") -> dict[str, str]:
    return {"recommended_actions": actions, "cluster_article_count": count}


def test_proposed_resolution_prioritizes_exclusion() -> None:
    row = _candidate("exclude_false_event;correct_date")
    assert build.proposed_resolution(row) == "exclude_cluster"


def test_proposed_resolution_routes_single_article_aggregate_to_decomposition() -> None:
    row = _candidate("split_or_exclude_aggregate")
    assert build.proposed_resolution(row) == "decompose_source_article"


def test_validator_accepts_complete_exclusion() -> None:
    blank = {
        "queue_id": "V9R-001",
        "event_id": "event_1",
        "final_resolution": "",
        "final_event_count": "",
        "final_event_groups_json": "",
        "excluded_article_mapping_ids_json": "",
        "reviewed_by": "",
        "review_notes": "",
    }
    completed = {
        **blank,
        "final_resolution": "exclude_cluster",
        "final_event_count": "0",
        "final_event_groups_json": "[]",
        "excluded_article_mapping_ids_json": '["V9R-001-A01"]',
        "reviewed_by": "reviewer",
    }
    result = validate.validate(
        [completed], [blank], [{"queue_id": "V9R-001", "mapping_id": "V9R-001-A01"}]
    )
    assert result["excluded_clusters"] == 1


def test_validator_rejects_unaccounted_article() -> None:
    blank = {
        "queue_id": "V9R-001",
        "final_resolution": "",
        "final_event_count": "",
        "final_event_groups_json": "",
        "excluded_article_mapping_ids_json": "",
        "reviewed_by": "",
        "review_notes": "",
    }
    group = {
        "group_id": "G1",
        "article_mapping_ids": ["V9R-001-A01"],
        "event_date": "2024-01-01",
        "district": "Kaski",
        "municipality": "",
        "event_type": "landslide",
        "hazard_type": "landslide",
        "deaths": "not_reported",
        "evidence": "Article states the event.",
    }
    completed = {
        **blank,
        "final_resolution": "keep_cluster",
        "final_event_count": "1",
        "final_event_groups_json": json.dumps([group]),
        "excluded_article_mapping_ids_json": "[]",
        "reviewed_by": "reviewer",
    }
    mappings = [
        {"queue_id": "V9R-001", "mapping_id": "V9R-001-A01"},
        {"queue_id": "V9R-001", "mapping_id": "V9R-001-A02"},
    ]
    with pytest.raises(ValueError, match="every article"):
        validate.validate([completed], [blank], mappings)
