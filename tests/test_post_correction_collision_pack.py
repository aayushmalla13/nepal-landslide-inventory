"""Tests for the post-correction existing-event collision gate."""

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
    module = _load("build_post_collision", "scripts/build_post_correction_collision_pack.py")
    result = module.compare(_candidate(), _existing())
    assert result is not None
    assert result["collision_tier"] == "high"
    assert "same_date" in result["reasons"]


def test_compare_ignores_distant_unrelated_event() -> None:
    module = _load(
        "build_post_collision_distant", "scripts/build_post_correction_collision_pack.py"
    )
    assert (
        module.compare(
            _candidate(), _existing(event_date_ad="2025-08-10", district="Myagdi")
        )
        is None
    )


def _template() -> dict[str, str]:
    return {
        "candidate_event_id": "candidate-1",
        "event_date": "2025-07-10",
        "final_action": "",
        "merge_existing_event_id": "",
        "reviewed_by": "",
        "collision_review_notes": "",
    }


def test_validator_accepts_listed_merge_target() -> None:
    module = _load(
        "validate_post_collision",
        "scripts/validate_post_correction_collision_decisions.py",
    )
    completed = {
        **_template(),
        "final_action": "merge_existing",
        "merge_existing_event_id": "existing-1",
        "reviewed_by": "reviewer",
    }
    pairs = [{"candidate_event_id": "candidate-1", "existing_event_id": "existing-1"}]
    result = module.validate([completed], [_template()], pairs)
    assert result["action_counts"] == {"merge_existing": 1}


def test_validator_rejects_unlisted_merge_target() -> None:
    module = _load(
        "validate_post_collision_bad",
        "scripts/validate_post_correction_collision_decisions.py",
    )
    completed = {
        **_template(),
        "final_action": "merge_existing",
        "merge_existing_event_id": "existing-2",
        "reviewed_by": "reviewer",
    }
    pairs = [{"candidate_event_id": "candidate-1", "existing_event_id": "existing-1"}]
    with pytest.raises(ValueError, match="not a collision candidate"):
        module.validate([completed], [_template()], pairs)
