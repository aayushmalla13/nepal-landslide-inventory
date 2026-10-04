"""Tests for the v1.5 locked final-validation draw and scorer."""

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


def test_draw_targets_v15_candidate_and_frozen_article_database() -> None:
    module = load("draw_v15_final_validation.py")
    assert module.RELEASE_ID == "nepal_landslide_inventory_v1.5.0_candidate_20261003"
    assert module.DATABASE.parent.name == "nepal_landslide_inventory_v1.2.0_candidate_20260929"
    assert module.CANONICAL_SHA256 == "313745c27218be7989764cc9614b71cc69a9549ff05c483247a6c89bd276ae19"
    assert module.SEED == 20261003
    assert "v14_final_validation_COMPLETED.csv" in module.REVIEWED_FILES
    assert "v15_structured_attribute_REVIEW_COMPLETED.csv" in module.REVIEWED_FILES


def test_scorer_targets_v15_artifacts() -> None:
    module = load("score_v15_final_validation.py")
    assert module.core.MANIFEST.name == "v15_final_validation_manifest.json"
    assert module.core.DEFAULT_COMPLETED.name == "v15_final_validation_COMPLETED.csv"
    assert module.core.JSON_OUTPUT.name == "v15_final_validation_score.json"
