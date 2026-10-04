"""Tests for v0.9 structured-attribute plan wiring."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load():
    path = ROOT / "scripts" / "materialize_v09_structured_attribute_plan.py"
    spec = importlib.util.spec_from_file_location("v09_structured_plan", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_v09_plan_uses_v08_source_and_v09_outputs() -> None:
    module = load()
    assert module.RELEASE.parent.name == "nepal_landslide_inventory_v0.8.0_candidate_20260923"
    assert module.COMPLETED.name == "v09_structured_attribute_REVIEW_COMPLETED.csv"
    assert module.MANIFEST_OUTPUT.name == "v09_structured_attribute_plan_manifest.json"
