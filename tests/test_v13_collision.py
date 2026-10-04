"""Tests for the v1.3 existing-event collision wrapper."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load():
    path = ROOT / "scripts/build_v13_collision_pack.py"
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_wrapper_targets_v13_outputs_and_frozen_v12_release() -> None:
    module = load()
    assert module.RELEASE_DIR.name == "nepal_landslide_inventory_v1.2.0_candidate_20260929"
    assert module.core.GROUPS.name == "v13_reconstruction_GROUPS.csv"
    assert module.core.COLLISION_DECISIONS.name == "v13_reconstruction_COLLISION_DECISIONS.csv"
    assert module.core.MANIFEST_OUTPUT.name == "v13_collision_manifest.json"
    assert module.core.AUDIT_NAME == "v13_existing_event_collision_v1"
    assert module.core.RELEASE_LABEL == "v1.2 candidate"
