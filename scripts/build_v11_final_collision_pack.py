#!/usr/bin/env python3
"""Build the final v1.1 candidate-to-candidate collision pack."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_core():
    path = Path(__file__).with_name("build_v09_final_collision_pack.py")
    spec = importlib.util.spec_from_file_location("v11_final_collision_core", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load final-collision core: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


core = _load_core()
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/outputs"


def configure_core() -> None:
    core.CANDIDATES = OUTPUT / "v11_existing_collision_NEW_CANDIDATES.csv"
    core.OUTCOME_MANIFEST = OUTPUT / "v11_existing_collision_outcomes_manifest.json"
    core.PAIRS = OUTPUT / "v11_reconstruction_FINAL_COLLISION_PAIRS.csv"
    core.DECISIONS = OUTPUT / "v11_reconstruction_FINAL_COLLISION_DECISIONS.csv"
    core.MANIFEST = OUTPUT / "v11_final_collision_manifest.json"
    core.REPORT = OUTPUT / "v11_final_collision_report.md"
    core.SCRIPT_PATH = Path(__file__).resolve()
    core.AUDIT_NAME = "v11_candidate_to_candidate_collision_v1"
    core.REPORT_TITLE = "Final v1.1 candidate collision screen"


configure_core()
compare = core.compare
build_pairs = core.build_pairs
build_decisions = core.build_decisions


def main() -> int:
    configure_core()
    return core.main()


if __name__ == "__main__":
    raise SystemExit(main())
