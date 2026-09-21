"""Tests for the post-correction reconstruction date gate."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _template(candidate_id: str = "candidate-1") -> dict[str, str]:
    return {
        "candidate_event_id": candidate_id,
        "event_evidence": "evidence",
        "final_action": "",
        "resolved_event_date": "",
        "reviewed_by": "",
        "review_notes": "",
    }


def test_build_date_review_embeds_article_evidence() -> None:
    module = _load("build_post_dates", "scripts/build_post_correction_date_review.py")
    group = {
        "candidate_event_id": "one",
        "queue_id": "PCR-001",
        "row_id": "PCF-001",
        "old_event_id": "old",
        "event_date": "unclear",
        "district": "Kaski",
        "municipality": "",
        "event_type": "landslide",
        "hazard_type": "landslide",
        "deaths": "not_reported",
        "article_mapping_ids_json": '["PCR-001-A01"]',
        "article_urls_json": '["https://example.com"]',
        "evidence": "failure evidence",
    }
    mapping = {
        "PCR-001-A01": {
            "title": "Article",
            "published_date_ad": "2025-07-02",
            "article_text": "The slide occurred Tuesday.",
        }
    }
    rows = module.build_date_review([group], mapping)
    assert len(rows) == 1
    assert "The slide occurred Tuesday." in rows[0]["source_evidence"]
    assert not rows[0]["final_action"]


def test_validate_accepts_date_and_exclusion() -> None:
    module = _load(
        "resolve_post_dates", "scripts/resolve_post_correction_reconstruction_dates.py"
    )
    first = {
        **_template("one"),
        "final_action": "set_date",
        "resolved_event_date": "2020-07-10",
        "reviewed_by": "reviewer",
    }
    second = {
        **_template("two"),
        "final_action": "exclude_candidate",
        "reviewed_by": "reviewer",
    }
    module.validate([first, second], [_template("one"), _template("two")])


def test_validate_rejects_out_of_period_date() -> None:
    module = _load(
        "resolve_post_dates_period",
        "scripts/resolve_post_correction_reconstruction_dates.py",
    )
    row = {
        **_template(),
        "final_action": "set_date",
        "resolved_event_date": "2010-01-01",
        "reviewed_by": "reviewer",
    }
    with pytest.raises(ValueError, match="outside the inventory period"):
        module.validate([row], [_template()])


def test_resolve_updates_and_excludes_candidates() -> None:
    module = _load(
        "resolve_post_dates_rows",
        "scripts/resolve_post_correction_reconstruction_dates.py",
    )
    groups = [
        {
            "candidate_event_id": "one",
            "event_date": "unclear",
            "review_notes": "original",
            "queue_id": "PCR-001",
            "old_event_id": "old-1",
            "district": "D",
            "evidence": "E",
        },
        {
            "candidate_event_id": "two",
            "event_date": "unclear",
            "review_notes": "",
            "queue_id": "PCR-002",
            "old_event_id": "old-2",
            "district": "D",
            "evidence": "E",
        },
    ]
    decisions = [
        {
            "candidate_event_id": "one",
            "final_action": "set_date",
            "resolved_event_date": "2020-07-10",
            "reviewed_by": "reviewer",
            "review_notes": "resolved",
        },
        {
            "candidate_event_id": "two",
            "final_action": "exclude_candidate",
            "resolved_event_date": "",
            "reviewed_by": "reviewer",
            "review_notes": "insufficient",
        },
    ]
    resolved, excluded = module.resolve(groups, decisions)
    assert [row["candidate_event_id"] for row in resolved] == ["one"]
    assert resolved[0]["event_date"] == "2020-07-10"
    assert [row["candidate_event_id"] for row in excluded] == ["two"]
