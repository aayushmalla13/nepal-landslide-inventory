"""Tests for applying the three canonical-event correction layers."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "assemble_corrected_inventory_release.py"
)
_spec = importlib.util.spec_from_file_location("assemble_corrected_inventory_release", MODULE_PATH)
release = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(release)


COLUMNS = [
    "event_id", "dedup_cluster_id", "event_date_ad", "district", "province",
    "municipality", "event_type", "hazard_type", "event_granularity", "article_role",
    "extraction_basis", "cluster_size", "sources_json", "representative_url",
    "representative_source", "representative_title", "trigger", "deaths", "missing",
    "injured", "conf_date", "conf_class", "specificity_reason", "in_nepal", "scope_reason",
    "location_consistent", "location_reason", "municipality_candidates_json",
    "ward_candidates_json", "place_name_candidates_json", "event_payload",
]


def _row(event_id: str, url: str, district: str = "A") -> dict[str, str]:
    row = {column: "" for column in COLUMNS}
    row.update(
        {
            "event_id": event_id,
            "dedup_cluster_id": "cluster_" + event_id,
            "event_date_ad": "2020-01-01",
            "district": district,
            "province": "P",
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


def test_assembly_applies_identity_exclusion_and_attribute_layers(monkeypatch) -> None:
    frozen = [
        _row("old_remove", "u1"),
        _row("target", "u2"),
        _row("exclude", "u3"),
        _row("fix", "u4"),
    ]
    plans = {
        "remove": [{"old_event_id": "old_remove", "reviewed_by": "r", "reason": "split"}],
        "new": [
            {
                "candidate_event_id": "candidate_aaaaaaaaaaaaaaaa",
                "old_event_id": "old_remove",
                "event_date": "2020-02-01",
                "district": "A",
                "municipality": "Town",
                "event_type": "road_obstruction",
                "hazard_type": "landslide",
                "deaths": "not_reported",
                "article_mapping_ids_json": '["m1"]',
                "article_urls_json": '["u1"]',
                "evidence": "separate slide",
                "reviewed_by": "r",
                "review_notes": "confirmed",
            }
        ],
        "merge": [
            {
                "candidate_event_id": "candidate_bbbbbbbbbbbbbbbb",
                "old_event_id": "old_remove",
                "merge_target_event_id": "target",
                "article_urls_json": '["u5"]',
                "evidence": "same event",
                "reviewed_by": "r",
                "review_notes": "confirmed",
            }
        ],
        "identity_excluded": [],
        "true_exclusions": [
            {"event_id": "exclude", "candidate_id": "c1", "reviewed_by": "r", "review_notes": "bad"}
        ],
        "true_corrections": [
            {
                "event_id": "fix", "candidate_id": "c2", "reviewed_by": "r",
                "review_notes": "corrected", "changed_fields_json": '["district","deaths"]',
                "final_event_date": "2020-01-02", "final_district": "B",
                "final_municipality": "", "final_event_type": "landslide",
                "final_hazard_type": "rockfall", "final_deaths": "0", "final_province": "Q",
            }
        ],
        "structured_corrections": [],
        "structured_exclusions": [],
    }
    articles = {
        "u1": {"url": "u1", "source": "source", "title": "new title"},
        "u5": {"url": "u5", "source": "other", "title": "merge title"},
    }
    monkeypatch.setattr(release, "EXPECTED_ROWS", 3)
    rows, log, provenance = release.assemble_rows(frozen, plans, articles)
    by_id = {row["event_id"]: row for row in rows}

    assert set(by_id) == {"target", "fix", "event_aaaaaaaaaaaaaaaa"}
    assert by_id["fix"]["district"] == "B"
    assert by_id["fix"]["deaths"] == "0"
    assert by_id["event_aaaaaaaaaaaaaaaa"]["deaths"] == ""
    assert json.loads(by_id["target"]["sources_json"]) == ["other", "source"]
    assert set(json.loads(by_id["target"]["event_payload"])["urls"]) == {"u2", "u5"}
    assert len(log) == 5
    assert len(provenance) == 2


def test_plan_layers_must_not_overlap(monkeypatch) -> None:
    frozen = [_row("same", "u1")]
    plans = {
        "remove": [{"old_event_id": "same"}],
        "new": [], "merge": [], "identity_excluded": [],
        "true_exclusions": [{"event_id": "same"}],
        "true_corrections": [], "structured_corrections": [], "structured_exclusions": [],
    }
    monkeypatch.setattr(release, "EXPECTED_ROWS", 1)
    try:
        release.assemble_rows(frozen, plans, {})
    except ValueError as error:
        assert "overlap" in str(error)
    else:
        raise AssertionError("Overlapping plans were accepted")
