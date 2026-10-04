"""Tests for v1.5 candidate-release assembly configuration."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load():
    path = ROOT / "scripts/assemble_v15_candidate_release.py"
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_v15_release_configuration() -> None:
    module = load()
    assert module.SOURCE_RELEASE_ID == "nepal_landslide_inventory_v1.4.0_candidate_20261002"
    assert module.DEFAULT_RELEASE_ID == "nepal_landslide_inventory_v1.5.0_candidate_20261003"
    assert module.EXPECTED_SOURCE_ROWS == 2138
    assert module.EXPECTED_ROWS == 2122
    assert module.PLAN_FILES["new"] == "v15_release_identity_NEW_EVENTS.csv"
    assert module.core.ARTICLE_DATABASE_RELATIVE.parent.name == (
        "nepal_landslide_inventory_v1.2.0_candidate_20260929"
    )


def test_v15_candidate_suffix_and_exact_dates() -> None:
    module = load()
    assert module.candidate_suffix("v15_candidate_abc123") == "abc123"
    assert module.all_dates_are_exact([{"event_date_ad": "2026-09-01"}])
    assert not module.all_dates_are_exact([{"event_date_ad": "unclear"}])
