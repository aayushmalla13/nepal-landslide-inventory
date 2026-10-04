"""Tests for v1.1 collision outcome wrappers."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load(name: str):
    path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_existing_collision_wrapper_targets_v11() -> None:
    module = load("materialize_v11_existing_collisions.py")
    assert module.core.COMPLETED.name == (
        "v11_reconstruction_COLLISION_DECISIONS_COMPLETED.csv"
    )
    assert module.core.NEW_OUTPUT.name == "v11_existing_collision_NEW_CANDIDATES.csv"
    assert module.core.SCRIPT_PATH.name == "materialize_v11_existing_collisions.py"


def test_final_collision_wrapper_targets_v11() -> None:
    module = load("build_v11_final_collision_pack.py")
    assert module.core.CANDIDATES.name == "v11_existing_collision_NEW_CANDIDATES.csv"
    assert module.core.DECISIONS.name == (
        "v11_reconstruction_FINAL_COLLISION_DECISIONS.csv"
    )
    assert module.core.AUDIT_NAME == "v11_candidate_to_candidate_collision_v1"
