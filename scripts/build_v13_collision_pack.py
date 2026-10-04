#!/usr/bin/env python3
"""Build existing-event collision evidence for v1.3 reconstruction candidates."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_core():
    path = Path(__file__).with_name("build_v09_collision_pack.py")
    spec = importlib.util.spec_from_file_location("v13_collision_core", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load collision core: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


core = _load_core()
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/outputs"
RELEASE_DIR = ROOT / "data/releases/nepal_landslide_inventory_v1.2.0_candidate_20260929"


def configure_core() -> None:
    core.RELEASE_DIR = RELEASE_DIR
    core.CANONICAL = RELEASE_DIR / "canonical_events_final.csv"
    core.RELEASE_MANIFEST = RELEASE_DIR / "release_manifest.json"
    core.GROUPS = OUTPUT / "v13_reconstruction_GROUPS.csv"
    core.RECONSTRUCTION_MANIFEST = OUTPUT / "v13_reconstruction_manifest.json"
    core.MAPPING_DECISIONS = OUTPUT / "v13_article_mapping_DECISIONS_COMPLETED.csv"
    core.MAPPING_VALIDATION = OUTPUT / "v13_article_mapping_validation.json"
    core.COLLISION_PAIRS = OUTPUT / "v13_reconstruction_COLLISION_PAIRS.csv"
    core.COLLISION_DECISIONS = OUTPUT / "v13_reconstruction_COLLISION_DECISIONS.csv"
    core.MANIFEST_OUTPUT = OUTPUT / "v13_collision_manifest.json"
    core.REPORT_OUTPUT = OUTPUT / "v13_collision_report.md"
    core.SCRIPT_PATH = Path(__file__).resolve()
    core.AUDIT_NAME = "v13_existing_event_collision_v1"
    core.REPORT_TITLE = "v1.3 existing-event collision screen"
    core.RELEASE_LABEL = "v1.2 candidate"


configure_core()
compare = core.compare
build_pairs = core.build_pairs
build_decisions = core.build_decisions


def main() -> int:
    configure_core()
    return core.main()


if __name__ == "__main__":
    raise SystemExit(main())
