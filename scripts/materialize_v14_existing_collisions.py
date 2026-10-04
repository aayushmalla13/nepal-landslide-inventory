#!/usr/bin/env python3
"""Materialize validated v1.4 existing-event collision outcomes without applying them."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_core():
    path = Path(__file__).with_name("materialize_v09_existing_collisions.py")
    spec = importlib.util.spec_from_file_location("v14_existing_collision_core", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load existing-collision core: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


core = _load_core()
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/outputs"


def configure_core() -> None:
    core.COMPLETED = OUTPUT / "v14_reconstruction_COLLISION_DECISIONS_COMPLETED.csv"
    core.VALIDATION = OUTPUT / "v14_collision_validation.json"
    core.MAPPING_DECISIONS = OUTPUT / "v14_article_mapping_DECISIONS_COMPLETED.csv"
    core.NEW_OUTPUT = OUTPUT / "v14_existing_collision_NEW_CANDIDATES.csv"
    core.MERGE_OUTPUT = OUTPUT / "v14_existing_collision_MERGES.csv"
    core.EXCLUDE_OUTPUT = OUTPUT / "v14_existing_collision_EXCLUDED.csv"
    core.BLOCKED_OUTPUT = OUTPUT / "v14_existing_collision_BLOCKED_CANDIDATES.csv"
    core.MANIFEST_OUTPUT = OUTPUT / "v14_existing_collision_outcomes_manifest.json"
    core.REPORT_OUTPUT = OUTPUT / "v14_existing_collision_outcomes_report.md"
    core.SCRIPT_PATH = Path(__file__).resolve()
    core.REPORT_TITLE = "v1.4 existing-event collision outcomes"


configure_core()
materialize = core.materialize


def main() -> int:
    configure_core()
    return core.main()


if __name__ == "__main__":
    raise SystemExit(main())
