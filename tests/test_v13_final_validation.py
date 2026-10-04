"""Tests for the v1.3 locked final-validation draw and scorer."""

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


def test_draw_targets_v13_candidate_and_v12_article_database() -> None:
    module = load("draw_v13_final_validation.py")
    assert module.RELEASE_ID == "nepal_landslide_inventory_v1.3.0_candidate_20260930"
    assert module.DATABASE.parent.name == "nepal_landslide_inventory_v1.2.0_candidate_20260929"
    assert module.CANONICAL_SHA256 == "9e8d44be3bf08b649d34c9b06f0e3d26e1983c46ee389b4295ac4f8416914c3e"
    assert module.SEED == 20260930
    assert "v13_structured_attribute_REVIEW_COMPLETED.csv" in module.REVIEWED_FILES


def test_scorer_targets_v13_artifacts() -> None:
    module = load("score_v13_final_validation.py")
    assert module.core.MANIFEST.name == "v13_final_validation_manifest.json"
    assert module.core.DEFAULT_COMPLETED.name == "v13_final_validation_COMPLETED.csv"
    assert module.core.JSON_OUTPUT.name == "v13_final_validation_score.json"
