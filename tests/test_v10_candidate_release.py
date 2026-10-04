"""Tests for the frozen v1.0 candidate release definition."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load():
    path = ROOT / 'scripts/assemble_v10_candidate_release.py'
    spec = importlib.util.spec_from_file_location('assemble_v10_candidate', path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_candidate_definition_is_pinned_to_reviewed_state() -> None:
    module = load()
    assert module.DEFAULT_RELEASE_ID == (
        'nepal_landslide_inventory_v1.0.0_candidate_20260927'
    )
    assert module.EXPECTED_ROWS == 2605
    assert module.EXPECTED_CANONICAL_SHA256 == (
        '68f2efd27a2c929c0df879974afcde14560ecbd6edf2ce389cc03a18f0857c8a'
    )
    assert module.EXPECTED_DATABASE_SHA256 == (
        'aed9e133ee511382f19ea7304168c3a3d7d2e59efb54cdcbc5047ec2117a198d'
    )
