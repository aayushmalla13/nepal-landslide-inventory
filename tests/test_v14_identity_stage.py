"""Tests for v1.4 reconstruction and existing-collision wrappers."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load(name: str):
    path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_reconstruction_targets_v14_outputs_and_ids() -> None:
    module = load("materialize_v14_reconstruction.py")
    assert module.core.COMPLETED.name == "v14_article_mapping_DECISIONS_COMPLETED.csv"
    assert module.core.GROUPS_OUTPUT.name == "v14_reconstruction_GROUPS.csv"
    group = {
        "group_id": "G1",
        "event_date": "2024-01-01",
        "district": "Kaski",
        "article_mapping_ids": ["V14R-001-A01"],
        "evidence": "Observed event.",
    }
    assert module.core.candidate_event_id("old", group).startswith("v14_candidate_")


def test_collision_wrapper_targets_v13_release() -> None:
    module = load("build_v14_collision_pack.py")
    assert module.RELEASE_DIR.name == "nepal_landslide_inventory_v1.3.0_candidate_20260930"
    assert module.core.COLLISION_DECISIONS.name == "v14_reconstruction_COLLISION_DECISIONS.csv"


def test_review_prefills_only_no_match_rows() -> None:
    module = load("prepare_v14_collision_review.py")
    rows = [
        {"top_collision_tier": "none", "final_action": "", "reviewed_by": "", "collision_review_notes": ""},
        {"top_collision_tier": "high", "final_action": "", "reviewed_by": "", "collision_review_notes": ""},
    ]
    prepared = module.prepare(rows)
    assert prepared[0]["final_action"] == "new_event"
    assert prepared[1]["final_action"] == ""


def test_validator_targets_v14_outputs() -> None:
    module = load("validate_v14_collision_decisions.py")
    assert module.core.DEFAULT_COMPLETED.name == "v14_reconstruction_COLLISION_DECISIONS_COMPLETED.csv"
    assert module.core.VALIDATION_OUTPUT.name == "v14_collision_validation.json"
