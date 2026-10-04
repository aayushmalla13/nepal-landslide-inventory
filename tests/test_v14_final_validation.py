"""Tests for the v1.4 locked final-validation draw and scorer."""

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


def test_draw_targets_v14_candidate_and_frozen_article_database() -> None:
    module = load("draw_v14_final_validation.py")
    assert module.RELEASE_ID == "nepal_landslide_inventory_v1.4.0_candidate_20261002"
    assert module.DATABASE.parent.name == "nepal_landslide_inventory_v1.2.0_candidate_20260929"
    assert module.CANONICAL_SHA256 == "bbf0f77960da94d7199268a3521715762ff833c0a4283ef3badedbe6d9ee9541"
    assert module.SEED == 20261002
    assert "v13_final_validation_COMPLETED.csv" in module.REVIEWED_FILES
    assert "v14_structured_attribute_REVIEW_COMPLETED.csv" in module.REVIEWED_FILES


def test_scorer_targets_v14_artifacts() -> None:
    module = load("score_v14_final_validation.py")
    assert module.core.MANIFEST.name == "v14_final_validation_manifest.json"
    assert module.core.DEFAULT_COMPLETED.name == "v14_final_validation_COMPLETED.csv"
    assert module.core.JSON_OUTPUT.name == "v14_final_validation_score.json"
