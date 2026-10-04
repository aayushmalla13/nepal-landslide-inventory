"""Tests for the locked v0.9 final-validation workflow."""

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


def test_draw_targets_exact_v09_candidate() -> None:
    module = load("draw_v09_final_validation.py")
    assert module.RELEASE_ID == "nepal_landslide_inventory_v0.9.0_candidate_20260924"
    assert module.CANONICAL_SHA256 == "9331668017b1ea34709acfbda34ec9a52c4ab5a02bcdc127cab0a58769379f22"
    assert "v08_fresh_validation_COMPLETED.csv" in module.REVIEWED_FILES
    assert module.SEED == 20260924


def test_scorer_uses_v09_locked_artifacts() -> None:
    module = load("score_v09_final_validation.py")
    assert module.MANIFEST.name == "v09_final_validation_manifest.json"
    assert module.DEFAULT_COMPLETED.name == "v09_final_validation_COMPLETED.csv"
