"""Tests for post-correction candidate assembly."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts" / "assemble_post_correction_candidate_release.py"
SPEC = importlib.util.spec_from_file_location("post_candidate", MODULE)
assert SPEC and SPEC.loader
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)

COLUMNS = [
    "event_id", "dedup_cluster_id", "event_date_ad", "district", "province",
    "municipality", "event_type", "hazard_type", "event_granularity",
    "article_role", "extraction_basis", "cluster_size", "sources_json",
    "representative_url", "representative_source", "representative_title",
    "trigger", "deaths", "missing", "injured", "conf_date", "conf_class",
    "specificity_reason", "in_nepal", "scope_reason", "location_consistent",
    "location_reason", "municipality_candidates_json", "ward_candidates_json",
    "place_name_candidates_json", "event_payload",
]


def source_row(event_id: str, url: str) -> dict[str, str]:
    row = {column: "" for column in COLUMNS}
    row.update(
        {
            "event_id": event_id,
            "dedup_cluster_id": f"cluster_{event_id}",
            "event_date_ad": "2020-01-01",
            "district": "Chitwan",
            "province": "Bagmati",
            "event_type": "landslide",
            "hazard_type": "landslide",
            "cluster_size": "1",
            "sources_json": '["source"]',
            "representative_url": url,
            "representative_source": "source",
            "representative_title": "title",
            "event_payload": json.dumps({"urls": [url], "sources": ["source"], "size": 1}),
        }
    )
    return row


def empty_plans() -> dict[str, list[dict[str, str]]]:
    return {key: [] for key in release.PLAN_FILES}


def test_new_event_location_is_canonicalized(monkeypatch) -> None:
    source = [source_row("old", "u1")]
    plans = empty_plans()
    plans["remove"] = [{"old_event_id": "old", "reviewed_by": "r", "reason": "split"}]
    plans["new"] = [
        {
            "candidate_event_id": "postcorr_candidate_aaaaaaaaaaaaaaaa",
            "old_event_id": "old",
            "event_date": "2020-01-02",
            "district": "Tanahun",
            "municipality": "Anbukhaireni Rural Municipality-2",
            "event_type": "road_obstruction",
            "hazard_type": "landslide",
            "deaths": "not_reported",
            "article_mapping_ids_json": '["m1"]',
            "article_urls_json": '["u1"]',
            "evidence": "road blocked",
            "reviewed_by_final": "r",
            "final_collision_notes": "distinct",
        }
    ]
    articles = {
        "u1": {
            "source": "source", "title": "new", "trigger": "rainfall",
            "conf_date": "0.9", "conf_class": "0.8",
        }
    }
    monkeypatch.setattr(release, "EXPECTED_SOURCE_ROWS", 1)
    monkeypatch.setattr(release, "EXPECTED_ROWS", 1)
    rows, log, provenance, locations = release.assemble_rows(source, plans, articles)
    assert rows[0]["event_id"] == "event_aaaaaaaaaaaaaaaa"
    assert rows[0]["district"] == "Tanahu"
    assert rows[0]["municipality"] == "Anbukhaireni Rural Municipality"
    assert rows[0]["deaths"] == ""
    assert len(log) == 2 and len(provenance) == 1 and len(locations) == 1


def test_plan_overlap_is_rejected(monkeypatch) -> None:
    source = [source_row("same", "u1")]
    plans = empty_plans()
    plans["remove"] = [{"old_event_id": "same"}]
    plans["true_exclusions"] = [{"event_id": "same"}]
    monkeypatch.setattr(release, "EXPECTED_SOURCE_ROWS", 1)
    with pytest.raises(ValueError, match="overlap"):
        release.assemble_rows(source, plans, {})


def test_kaligandaki_location_override() -> None:
    plan = {
        "candidate_event_id": "postcorr_candidate_7b2a51eea180d84c",
        "district": "unclear",
        "municipality": "unclear",
    }
    location_log: list[dict[str, str]] = []
    district, municipality = release.canonical_location(plan, location_log)
    assert district == "Baglung"
    assert municipality == "Baglung Municipality"
    assert len(location_log) == 1


def test_inherited_legacy_municipality_is_not_silently_rewritten(monkeypatch) -> None:
    source = [source_row("old", "u1")]
    source[0]["district"] = "Dhading"
    source[0]["municipality"] = "Khaniyabas Rural Municipality"
    monkeypatch.setattr(release, "EXPECTED_SOURCE_ROWS", 1)
    monkeypatch.setattr(release, "EXPECTED_ROWS", 1)

    rows, _, _, _ = release.assemble_rows(source, empty_plans(), {})

    assert rows[0]["municipality"] == "Khaniyabas Rural Municipality"
