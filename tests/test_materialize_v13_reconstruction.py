"""Tests for v1.3 reconstruction materialization."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load():
    path = ROOT / "scripts/materialize_v13_reconstruction.py"
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_wrapper_targets_v13_outputs() -> None:
    module = load()
    assert module.core.COMPLETED.name == "v13_article_mapping_DECISIONS_COMPLETED.csv"
    assert module.core.GROUPS_OUTPUT.name == "v13_reconstruction_GROUPS.csv"
    assert module.core.UNRESOLVED_OUTPUT.name == "v13_reconstruction_UNRESOLVED.csv"
    assert module.core.SCRIPT_PATH.name == "materialize_v13_reconstruction.py"
    assert module.core.REPORT_TITLE == "v1.3 reconstruction candidates"


def test_candidate_ids_are_versioned_v13() -> None:
    module = load()
    group = {
        "group_id": "G1",
        "event_date": "2024-01-01",
        "district": "Kaski",
        "article_mapping_ids": ["V13R-001-A01"],
        "evidence": "Observed event.",
    }
    candidate_id = module.core.candidate_event_id("event-old", group)
    assert candidate_id.startswith("v13_candidate_")
