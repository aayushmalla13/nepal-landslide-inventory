"""Tests for v0.9 candidate assembler configuration."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load():
    path = ROOT / "scripts" / "assemble_v09_candidate_release.py"
    spec = importlib.util.spec_from_file_location("v09_candidate_release", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_v09_release_configuration() -> None:
    module = load()
    assert module.SOURCE_RELEASE_ID == "nepal_landslide_inventory_v0.8.0_candidate_20260923"
    assert module.EXPECTED_SOURCE_ROWS == 2872
    assert module.EXPECTED_ROWS == 2858
    assert module.PLAN_FILES["new"] == "v09_release_identity_NEW_EVENTS.csv"


def test_v09_candidate_suffix() -> None:
    module = load()
    assert module.candidate_suffix("v09_candidate_abc") == "abc"
    with pytest.raises(ValueError, match="Unexpected v0.9"):
        module.candidate_suffix("postcorr_candidate_abc")
