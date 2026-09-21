"""Tests for the post-correction article-mapping gate."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_proposed_resolution_routes_identity_actions() -> None:
    module = _load("build_post_mapping", "scripts/build_post_correction_article_mapping_pack.py")
    assert (
        module.proposed_resolution(
            {"recommended_actions": "exclude_false_event", "cluster_article_count": "1"}
        )
        == "exclude_cluster"
    )
    assert (
        module.proposed_resolution(
            {
                "recommended_actions": "split_or_exclude_aggregate;correct_date",
                "cluster_article_count": "1",
            }
        )
        == "decompose_source_article"
    )
    assert (
        module.proposed_resolution(
            {
                "recommended_actions": "split_or_exclude_aggregate;recluster_articles",
                "cluster_article_count": "2",
            }
        )
        == "recluster_and_decompose"
    )


def _base() -> tuple[dict[str, str], dict[str, str], list[dict[str, str]]]:
    template = {
        "queue_id": "PCR-001",
        "event_id": "event-1",
        "final_resolution": "",
        "final_event_count": "",
        "final_event_groups_json": "",
        "excluded_article_mapping_ids_json": "",
        "reviewed_by": "",
        "review_notes": "",
    }
    return dict(template), template, [
        {"queue_id": "PCR-001", "mapping_id": "PCR-001-A01"}
    ]


def test_valid_exclusion_accounts_for_every_article() -> None:
    module = _load("validate_post_mapping", "scripts/validate_post_correction_article_mapping.py")
    completed, template, mapping = _base()
    completed.update(
        final_resolution="exclude_cluster",
        final_event_count="0",
        final_event_groups_json="[]",
        excluded_article_mapping_ids_json='["PCR-001-A01"]',
        reviewed_by="reviewer",
    )
    result = module.validate([completed], [template], mapping)
    assert result["excluded_clusters"] == 1


def test_valid_retained_group_accounts_for_article() -> None:
    module = _load(
        "validate_post_mapping_group",
        "scripts/validate_post_correction_article_mapping.py",
    )
    completed, template, mapping = _base()
    group = {
        "group_id": "A",
        "article_mapping_ids": ["PCR-001-A01"],
        "event_date": "2025-01-01",
        "district": "Chitwan",
        "municipality": "",
        "event_type": "landslide",
        "hazard_type": "landslide",
        "deaths": "not_reported",
        "evidence": "Specific dated failure.",
    }
    completed.update(
        final_resolution="keep_cluster",
        final_event_count="1",
        final_event_groups_json=json.dumps([group]),
        excluded_article_mapping_ids_json="[]",
        reviewed_by="reviewer",
    )
    result = module.validate([completed], [template], mapping)
    assert result["retained_event_groups"] == 1


def test_unaccounted_article_is_rejected() -> None:
    module = _load(
        "validate_post_mapping_missing",
        "scripts/validate_post_correction_article_mapping.py",
    )
    completed, template, mapping = _base()
    completed.update(
        final_resolution="keep_cluster",
        final_event_count="1",
        final_event_groups_json=json.dumps(
            [
                {
                    "group_id": "A",
                    "article_mapping_ids": ["PCR-001-A02"],
                    "event_date": "2025-01-01",
                    "district": "Chitwan",
                    "municipality": "",
                    "event_type": "landslide",
                    "hazard_type": "landslide",
                    "deaths": "not_reported",
                    "evidence": "Specific dated failure.",
                }
            ]
        ),
        excluded_article_mapping_ids_json="[]",
        reviewed_by="reviewer",
    )
    with pytest.raises(ValueError, match="unknown mapping ID"):
        module.validate([completed], [template], mapping)


def test_unclear_resolution_cannot_define_events() -> None:
    module = _load(
        "validate_post_mapping_unclear",
        "scripts/validate_post_correction_article_mapping.py",
    )
    completed, template, mapping = _base()
    completed.update(
        final_resolution="unclear",
        final_event_count="1",
        reviewed_by="reviewer",
    )
    with pytest.raises(ValueError, match="must not define events"):
        module.validate([completed], [template], mapping)
