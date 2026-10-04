"""Tests for v0.9 true-value plan wiring."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load():
    path = ROOT / "scripts" / "materialize_v09_true_value_plan.py"
    spec = importlib.util.spec_from_file_location("v09_true_value_plan", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_validation_count() -> None:
    module = load()
    rows = [
        {"reviewed_action": "retain"},
        {"reviewed_action": "exclude_candidate"},
        {"reviewed_action": "retain"},
    ]
    assert module.validation_count("retain", rows) == 2
    assert module.validation_count("exclude_candidate", rows) == 1


def test_v09_plan_uses_v08_source_and_v09_identity() -> None:
    module = load()
    assert module.RELEASE.parent.name == "nepal_landslide_inventory_v0.8.0_candidate_20260923"
    assert module.IDENTITY_MANIFEST.name == "v09_identity_plan_manifest.json"


def test_empty_outcome_schemas_are_defined() -> None:
    module = load()
    assert "changed_fields_json" in module.CORRECTION_COLUMNS
    assert "final_event_date" in module.CORRECTION_COLUMNS
    assert "event_date" in module.EXCLUSION_COLUMNS
    assert "production_status" in module.EXCLUSION_COLUMNS
