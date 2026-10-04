"""Tests for the isolated v1.3 remediation rebuild runner."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load():
    path = ROOT / "scripts/run_v13_diagnostic_rebuild.py"
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_v13_rebuild_starts_from_frozen_v12_candidate() -> None:
    module = load()
    assert module.DEFAULT_SOURCE.name == "landslide_inventory.sqlite"
    assert module.DEFAULT_SOURCE.parent.name == (
        "nepal_landslide_inventory_v1.2.0_candidate_20260929"
    )
    assert module.DEFAULT_OUTPUT.name == "v13_pipeline_diagnostic"


def test_v13_rebuild_preserves_stage_order() -> None:
    module = load()
    names = [name for name, _ in module.STAGES]
    assert names == [
        "extract",
        "event_specificity",
        "location_consistency",
        "filter_scope",
        "corrections",
        "dedup",
        "event_typing",
        "export_final",
    ]
