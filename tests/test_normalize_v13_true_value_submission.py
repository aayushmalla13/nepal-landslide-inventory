"""Tests for v1.3 true-value submission normalization."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load():
    path = ROOT / "scripts/normalize_v13_true_value_submission.py"
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_clears_proposed_values_only_for_non_retained_rows() -> None:
    module = load()
    rows = [
        {
            "queue_id": "V13R-001",
            "reviewed_action": "exclude_candidate",
            "proposed_event_date": "",
            "proposed_event_type": "road_obstruction",
            "review_notes": "Exclude after review.",
        },
        {
            "queue_id": "V13R-002",
            "reviewed_action": "retain",
            "proposed_event_date": "2024-07-01",
            "proposed_event_type": "",
            "review_notes": "Retain corrected date.",
        },
    ]
    normalized, changes = module.normalize(rows)
    assert normalized[0]["proposed_event_type"] == ""
    assert normalized[0]["review_notes"] == rows[0]["review_notes"]
    assert normalized[1] == rows[1]
    assert changes == [
        {
            "queue_id": "V13R-001",
            "column": "proposed_event_type",
            "old_value": "road_obstruction",
            "new_value": "",
            "reason": "non-retained rows must not carry proposed values",
        }
    ]


def test_canonicalizes_known_municipality_alias_for_retained_row() -> None:
    module = load()
    rows = [
        {
            "queue_id": "V13R-024",
            "reviewed_action": "retain",
            "proposed_municipality": "Besisahar Municipality",
        }
    ]
    normalized, changes = module.normalize(rows)
    assert normalized[0]["proposed_municipality"] == "Besishahar Municipality"
    assert changes[0]["reason"] == "canonical gazetteer alias normalization"


def test_excludes_verified_event_before_inventory_scope() -> None:
    module = load()
    rows = [
        {
            "queue_id": "V13R-029",
            "reviewed_action": "retain",
            "proposed_event_date": "2014-08-02",
            "review_notes": "Exact historical date verified.",
        }
    ]
    normalized, changes = module.normalize(rows)
    assert normalized[0]["reviewed_action"] == "exclude_candidate"
    assert normalized[0]["proposed_event_date"] == ""
    assert "predates" in normalized[0]["review_notes"]
    assert len(changes) == 3
