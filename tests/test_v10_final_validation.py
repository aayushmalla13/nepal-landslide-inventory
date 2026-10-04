"""Tests for the locked v1.0 final-validation workflow."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load(name: str):
    path = ROOT / 'scripts' / name
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_draw_targets_exact_v10_candidate() -> None:
    module = load('draw_v10_final_validation.py')
    assert module.RELEASE_ID == 'nepal_landslide_inventory_v1.0.0_candidate_20260927'
    assert module.CANONICAL_SHA256 == (
        '68f2efd27a2c929c0df879974afcde14560ecbd6edf2ce389cc03a18f0857c8a'
    )
    assert module.DATABASE.parent == module.RELEASE_DIR
    assert 'v09_final_validation_COMPLETED.csv' in module.REVIEWED_FILES
    assert 'dedup_collision_review_BATCH_01_COMPLETED.csv' in module.REVIEWED_FILES
    assert module.SEED == 20260927


def test_scorer_uses_v10_locked_artifacts() -> None:
    module = load('score_v10_final_validation.py')
    assert module.MANIFEST.name == 'v10_final_validation_manifest.json'
    assert module.DEFAULT_COMPLETED.name == 'v10_final_validation_COMPLETED.csv'
