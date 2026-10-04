#!/usr/bin/env python3
"""Validate completed v1.4 existing-event collision decisions."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_core():
    path = Path(__file__).with_name("validate_v09_collision_decisions.py")
    spec = importlib.util.spec_from_file_location("v14_collision_validation_core", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load collision validator core: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


core = _load_core()
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/outputs"


def configure_core() -> None:
    core.TEMPLATE = OUTPUT / "v14_reconstruction_COLLISION_DECISIONS.csv"
    core.PAIRS = OUTPUT / "v14_reconstruction_COLLISION_PAIRS.csv"
    core.COLLISION_MANIFEST = OUTPUT / "v14_collision_manifest.json"
    core.DEFAULT_COMPLETED = OUTPUT / "v14_reconstruction_COLLISION_DECISIONS_COMPLETED.csv"
    core.VALIDATION_OUTPUT = OUTPUT / "v14_collision_validation.json"


configure_core()
validate = core.validate


def main() -> int:
    configure_core()
    return core.main()


if __name__ == "__main__":
    raise SystemExit(main())
