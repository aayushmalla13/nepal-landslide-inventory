"""Tests for the v1.3 spent-sample date remediation verifier."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load():
    path = ROOT / "scripts/verify_v13_date_remediation.py"
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_current_v13_diagnostic_closes_all_confirmed_date_failures() -> None:
    module = load()
    replay, summary = module.verify(
        module.DEFAULT_COMPLETED,
        module.DEFAULT_CORRECTIONS,
        module.DEFAULT_DATABASE,
    )
    assert len(replay) == 23
    assert summary["unresolved_rows"] == 0
    assert summary["outcome_counts"] == {
        "corrected_exact_date": 17,
        "excluded_exact_date_or_identity_unresolved": 6,
    }
    assert all(row["claimed_event_date"] != row["v13_event_date"] for row in replay)
