"""Tests for the v0.9 existing-event collision gate."""

from __future__ import annotations

import importlib.util
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


build = _load("build_v09_collision_pack.py")
validate = _load("validate_v09_collision_decisions.py")


def _candidate() -> dict[str, str]:
    return {
        "candidate_event_id": "candidate-1",
        "event_date": "2025-07-10",
        "district": "Kaski",
        "municipality": "Pokhara",
        "event_type": "landslide",
        "hazard_type": "landslide",
        "evidence": "Landslide at Pokhara",
        "article_urls_json": '["https://candidate"]',
    }


def _existing(**overrides: str) -> dict[str, str]:
    row = {
        "event_id": "existing-1",
        "event_date_ad": "2025-07-10",
        "district": "Kaski",
        "municipality": "Pokhara",
        "event_type": "landslide",
        "hazard_type": "landslide",
        "representative_title": "Pokhara landslide",
        "representative_url": "https://existing",
        "event_payload": '{"urls":["https://existing"]}',
    }
    row.update(overrides)
    return row


def test_compare_identifies_same_date_and_municipality() -> None:
    result = build.compare(_candidate(), _existing())
    assert result is not None
    assert result["collision_tier"] == "high"
    assert "same_date" in result["reasons"]


def test_compare_ignores_distant_unrelated_event() -> None:
    assert (
        build.compare(_candidate(), _existing(event_date_ad="2025-08-10", district="Myagdi"))
        is None
    )


def test_validator_restricts_merge_to_listed_target() -> None:
    template = {
        "candidate_event_id": "candidate-1",
        "final_action": "",
        "merge_existing_event_id": "",
        "reviewed_by": "",
        "collision_review_notes": "",
    }
    completed = {
        **template,
        "final_action": "merge_existing",
        "merge_existing_event_id": "existing-2",
        "reviewed_by": "reviewer",
    }
    pairs = [{"candidate_event_id": "candidate-1", "existing_event_id": "existing-1"}]
    with pytest.raises(ValueError, match="not a collision candidate"):
        validate.validate([completed], [template], pairs)
