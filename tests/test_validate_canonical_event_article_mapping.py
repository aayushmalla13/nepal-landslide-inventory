"""Tests for completed canonical-event article mapping validation."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load():
    path = ROOT / "scripts" / "validate_canonical_event_article_mapping.py"
    spec = importlib.util.spec_from_file_location("validate_article_mapping", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def base() -> tuple[dict[str, str], dict[str, str], list[dict[str, str]]]:
    template = {
        "candidate_id": "CEC-001", "event_id": "event-1",
        "final_resolution": "", "final_event_count": "",
        "final_event_groups_json": "", "excluded_article_mapping_ids_json": "",
        "reviewed_by": "", "review_notes": "",
    }
    completed = dict(template)
    mapping = [{"candidate_id": "CEC-001", "mapping_id": "CEC-001-A01"}]
    return completed, template, mapping


def test_valid_exclusion_requires_every_article() -> None:
    module = load()
    completed, template, mapping = base()
    completed.update(
        final_resolution="exclude_cluster", final_event_count="0",
        final_event_groups_json="[]",
        excluded_article_mapping_ids_json='["CEC-001-A01"]', reviewed_by="reviewer_D",
    )
    result = module.validate([completed], [template], mapping)
    assert result["excluded_clusters"] == 1


def test_valid_group_must_account_for_membership() -> None:
    module = load()
    completed, template, mapping = base()
    group = {
        "group_id": "A", "article_mapping_ids": ["CEC-001-A01"],
        "event_date": "2025-01-01", "district": "Chitwan", "municipality": "",
        "event_type": "landslide", "hazard_type": "landslide",
        "deaths": "not_reported", "evidence": "Specific dated failure.",
    }
    completed.update(
        final_resolution="keep_cluster", final_event_count="1",
        final_event_groups_json=json.dumps([group]),
        excluded_article_mapping_ids_json="[]", reviewed_by="reviewer_D",
    )
    result = module.validate([completed], [template], mapping)
    assert result["retained_event_groups"] == 1


def test_unaccounted_article_is_rejected() -> None:
    module = load()
    completed, template, mapping = base()
    completed.update(
        final_resolution="keep_cluster", final_event_count="1",
        final_event_groups_json=json.dumps([{
            "group_id": "A", "article_mapping_ids": ["CEC-001-A02"],
            "event_date": "2025-01-01", "district": "Chitwan", "municipality": "",
            "event_type": "landslide", "hazard_type": "landslide",
            "deaths": "not_reported", "evidence": "Specific dated failure.",
        }]),
        excluded_article_mapping_ids_json="[]", reviewed_by="reviewer_D",
    )
    with pytest.raises(ValueError, match="unknown mapping ID"):
        module.validate([completed], [template], mapping)
