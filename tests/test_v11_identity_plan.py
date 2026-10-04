"""Tests for the v1.1 identity-plan wrapper."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load():
    path = ROOT / "scripts/materialize_v11_identity_plan.py"
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_wrapper_uses_frozen_v10_candidate_and_v11_outputs() -> None:
    module = load()
    assert module.core.SOURCE_RELEASE.name == (
        "nepal_landslide_inventory_v1.0.0_candidate_20260927"
    )
    assert module.core.FINAL_DECISIONS.name == (
        "v11_reconstruction_FINAL_COLLISION_DECISIONS_COMPLETED.csv"
    )
    assert module.core.NEW_OUTPUT.name == "v11_identity_plan_NEW_EVENTS.csv"
    assert module.core.IDENTITY_STATUS.startswith("v11_identity_plan_")
