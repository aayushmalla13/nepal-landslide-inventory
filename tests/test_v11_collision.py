"""Tests for the v1.1 existing-event collision wrapper."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load():
    path = ROOT / "scripts/build_v11_collision_pack.py"
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_wrapper_targets_v10_candidate_and_v11_outputs() -> None:
    module = load()
    assert module.core.RELEASE_DIR.name == (
        "nepal_landslide_inventory_v1.0.0_candidate_20260927"
    )
    assert module.core.GROUPS.name == "v11_reconstruction_GROUPS.csv"
    assert module.core.COLLISION_DECISIONS.name == (
        "v11_reconstruction_COLLISION_DECISIONS.csv"
    )
    assert module.core.SCRIPT_PATH.name == "build_v11_collision_pack.py"
    assert module.core.AUDIT_NAME == "v11_existing_event_collision_v1"
