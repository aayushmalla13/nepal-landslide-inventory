#!/usr/bin/env python3
"""Materialize validated v1.3 mapping decisions as an unapplied identity plan."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_core():
    path = Path(__file__).with_name("materialize_v09_reconstruction.py")
    spec = importlib.util.spec_from_file_location("v13_reconstruction_core", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load reconstruction core: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


core = _load_core()
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/outputs"


def configure_core() -> None:
    core.COMPLETED = OUTPUT / "v13_article_mapping_DECISIONS_COMPLETED.csv"
    core.TEMPLATE = OUTPUT / "v13_article_mapping_DECISIONS.csv"
    core.ARTICLE_MAP = OUTPUT / "v13_article_membership_MAP.csv"
    core.VALIDATION = OUTPUT / "v13_article_mapping_validation.json"
    core.GROUPS_OUTPUT = OUTPUT / "v13_reconstruction_GROUPS.csv"
    core.EXCLUSIONS_OUTPUT = OUTPUT / "v13_reconstruction_EXCLUDED_ARTICLES.csv"
    core.UNRESOLVED_OUTPUT = OUTPUT / "v13_reconstruction_UNRESOLVED.csv"
    core.MANIFEST_OUTPUT = OUTPUT / "v13_reconstruction_manifest.json"
    core.REPORT_OUTPUT = OUTPUT / "v13_reconstruction_report.md"
    core.SCRIPT_PATH = Path(__file__)
    core.REPORT_TITLE = "v1.3 reconstruction candidates"
    core.PLAN_VERSION = "v1.3"

    if not hasattr(core, "_v13_original_candidate_event_id"):
        core._v13_original_candidate_event_id = core.candidate_event_id

    def candidate_event_id(old_event_id, group):
        return core._v13_original_candidate_event_id(old_event_id, group).replace(
            "v09_candidate_", "v13_candidate_", 1
        )

    core.candidate_event_id = candidate_event_id


configure_core()
materialize = core.materialize


def main() -> int:
    configure_core()
    return core.main()


if __name__ == "__main__":
    raise SystemExit(main())
