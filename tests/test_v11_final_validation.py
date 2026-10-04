"""Tests for the locked v1.1 final-validation workflow."""

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


def test_draw_targets_exact_v11_candidate() -> None:
    module = load("draw_v11_final_validation.py")
    assert module.RELEASE_ID == "nepal_landslide_inventory_v1.1.0_candidate_20260928"
    assert module.CANONICAL_SHA256 == (
        "eca57e481a01b29ad38b0c6b9203aab5f080a631def887646bbac9a8e4583581"
    )
    assert module.DATABASE.name == "landslide_inventory.sqlite"
    assert "v11_structured_attribute_REVIEW_COMPLETED.csv" in module.REVIEWED_FILES
    assert module.SEED == 20260928


def test_scorer_uses_v11_locked_artifacts() -> None:
    module = load("score_v11_final_validation.py")
    assert module.MANIFEST.name == "v11_final_validation_manifest.json"
    assert module.DEFAULT_COMPLETED.name == "v11_final_validation_COMPLETED.csv"
