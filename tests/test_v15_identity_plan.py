"""Tests for v1.5 identity-plan materialization configuration."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load():
    path = ROOT / "scripts/materialize_v15_identity_plan.py"
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_wrapper_targets_frozen_v14_and_v15_outputs() -> None:
    module = load()
    assert module.SOURCE_RELEASE.name == "nepal_landslide_inventory_v1.4.0_candidate_20261002"
    assert module.core.FINAL_DECISIONS.name == (
        "v15_reconstruction_FINAL_COLLISION_DECISIONS_COMPLETED.csv"
    )
    assert module.core.NEW_OUTPUT.name == "v15_identity_plan_NEW_EVENTS.csv"
    assert module.core.RETAINED_OUTPUT.name == "v15_identity_plan_RETAINED_OLD_EVENTS.csv"
    assert module.core.PLAN_LABEL == "v1.5"
    assert module.core.SOURCE_LABEL == "v1.4 candidate"
