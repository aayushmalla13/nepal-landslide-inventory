"""Tests for v1.3 candidate-release assembly configuration."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load():
    path = ROOT / "scripts/assemble_v13_candidate_release.py"
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_v13_release_configuration() -> None:
    module = load()
    assert module.SOURCE_RELEASE_ID == "nepal_landslide_inventory_v1.2.0_candidate_20260929"
    assert module.DEFAULT_RELEASE_ID == "nepal_landslide_inventory_v1.3.0_candidate_20260930"
    assert module.EXPECTED_SOURCE_ROWS == 2160
    assert module.EXPECTED_ROWS == 2146
    assert module.PLAN_FILES["new"] == "v13_identity_plan_NEW_EVENTS.csv"
    assert module.core.ARTICLE_DATABASE_RELATIVE.name == "landslide_inventory.sqlite"


def test_v13_candidate_suffix() -> None:
    module = load()
    assert module.candidate_suffix("v13_candidate_abc123") == "abc123"
