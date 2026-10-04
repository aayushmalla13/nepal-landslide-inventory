"""Tests for v0.9 identity-plan count derivation and bundle safety."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load():
    path = ROOT / "scripts" / "materialize_v09_identity_plan.py"
    spec = importlib.util.spec_from_file_location("v09_identity", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_expected_counts_derive_from_validated_manifests() -> None:
    module = load()
    final = [
        {"final_candidate_action": "new_event"},
        {"final_candidate_action": "merge_candidate"},
        {"final_candidate_action": "exclude_duplicate"},
    ]
    mapping = [
        {"final_resolution": "unclear"},
        {"final_resolution": "recluster_articles"},
    ]
    existing = {
        "safe_superseded_old_events": 4,
        "safe_merges_into_existing": 2,
        "excluded_candidates": 3,
        "blocked_candidates": 5,
        "blocked_old_event_bundles": 2,
    }
    assert module.expected_counts(final, mapping, existing) == {
        "remove": 4,
        "new": 1,
        "merge_existing": 2,
        "merge_candidate": 1,
        "excluded": 4,
        "blocked_candidates": 5,
        "retained_old": 3,
    }


def test_v09_uses_v08_as_immutable_source() -> None:
    module = load()
    assert module.SOURCE_RELEASE.name == "nepal_landslide_inventory_v0.8.0_candidate_20260923"
    assert module.SOURCE_CANONICAL.name == "canonical_events_final.csv"


def test_report_does_not_hardcode_historical_unresolved_counts() -> None:
    source = (ROOT / "scripts/materialize_v09_identity_plan.py").read_text()
    assert "Eighteen mapping-unclear" not in source
