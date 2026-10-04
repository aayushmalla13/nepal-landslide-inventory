#!/usr/bin/env python3
"""Materialize the reviewed v1.4 identity corrections without applying them."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_core():
    path = Path(__file__).with_name("materialize_v09_identity_plan.py")
    spec = importlib.util.spec_from_file_location("v14_identity_core", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load identity-plan core: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


core = _load_core()
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/outputs"
SOURCE_RELEASE = ROOT / "data/releases/nepal_landslide_inventory_v1.3.0_candidate_20260930"


def configure_core() -> None:
    core.SOURCE_RELEASE = SOURCE_RELEASE
    core.SOURCE_CANONICAL = SOURCE_RELEASE / "canonical_events_final.csv"
    core.FINAL_DECISIONS = (
        OUTPUT / "v14_reconstruction_FINAL_COLLISION_DECISIONS_COMPLETED.csv"
    )
    core.FINAL_VALIDATION = OUTPUT / "v14_final_collision_validation.json"
    core.EXISTING_MANIFEST = OUTPUT / "v14_existing_collision_outcomes_manifest.json"
    core.EXISTING_NEW = OUTPUT / "v14_existing_collision_NEW_CANDIDATES.csv"
    core.EXISTING_MERGES = OUTPUT / "v14_existing_collision_MERGES.csv"
    core.EXISTING_EXCLUDED = OUTPUT / "v14_existing_collision_EXCLUDED.csv"
    core.EXISTING_BLOCKED = OUTPUT / "v14_existing_collision_BLOCKED_CANDIDATES.csv"
    core.MAPPING_DECISIONS = OUTPUT / "v14_article_mapping_DECISIONS_COMPLETED.csv"
    core.EXCLUDED_ARTICLES = OUTPUT / "v14_reconstruction_EXCLUDED_ARTICLES.csv"
    core.RECONSTRUCTION_MANIFEST = OUTPUT / "v14_reconstruction_manifest.json"

    core.PREFIX = "v14_identity_plan"
    core.REMOVE_OUTPUT = OUTPUT / f"{core.PREFIX}_REMOVE_OLD_EVENTS.csv"
    core.NEW_OUTPUT = OUTPUT / f"{core.PREFIX}_NEW_EVENTS.csv"
    core.MERGE_EXISTING_OUTPUT = OUTPUT / f"{core.PREFIX}_MERGES_EXISTING.csv"
    core.MERGE_CANDIDATE_OUTPUT = OUTPUT / f"{core.PREFIX}_MERGES_CANDIDATES.csv"
    core.EXCLUDE_OUTPUT = OUTPUT / f"{core.PREFIX}_EXCLUDED_CANDIDATES.csv"
    core.BLOCKED_OUTPUT = OUTPUT / f"{core.PREFIX}_BLOCKED_CANDIDATES.csv"
    core.RETAINED_OUTPUT = OUTPUT / f"{core.PREFIX}_RETAINED_OLD_EVENTS.csv"
    core.MANIFEST_OUTPUT = OUTPUT / f"{core.PREFIX}_manifest.json"
    core.REPORT_OUTPUT = OUTPUT / f"{core.PREFIX}_report.md"
    core.IDENTITY_STATUS = (
        "v14_identity_plan_unapplied_true_value_and_structured_attribute_gates_pending"
    )
    core.REPORT_TITLE = "v1.4 identity plan result"
    core.SOURCE_LABEL = "v1.3 candidate"
    core.PLAN_LABEL = "v1.4"


configure_core()
expected_counts = core.expected_counts


def main() -> int:
    configure_core()
    return core.main()


if __name__ == "__main__":
    raise SystemExit(main())
