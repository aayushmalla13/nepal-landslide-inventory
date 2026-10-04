"""Tests for v1.3 true-value review preparation and wrappers."""

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


def row(actions: str) -> dict[str, str]:
    return {
        "row_id": "V12F-001",
        "recommended_actions": actions,
        "proposed_event_date": "",
        "reviewed_action": "",
        "reviewed_by": "",
        "review_notes": "",
    }


def test_prepare_reuses_verified_exact_date() -> None:
    module = load("prepare_v13_true_value_review.py")
    replay = [{"row_id": "V12F-001", "outcome": "corrected_exact_date", "v13_event_date": "2024-07-01"}]
    prepared, complete, partial = module.prepare([row("correct_date")], replay)
    assert prepared[0]["proposed_event_date"] == "2024-07-01"
    assert prepared[0]["reviewed_action"] == "retain"
    assert (complete, partial) == (1, 0)


def test_prepare_leaves_other_actions_for_human() -> None:
    module = load("prepare_v13_true_value_review.py")
    replay = [{"row_id": "V12F-001", "outcome": "corrected_exact_date", "v13_event_date": "2024-07-01"}]
    prepared, complete, partial = module.prepare([row("correct_date;correct_deaths")], replay)
    assert prepared[0]["proposed_event_date"] == "2024-07-01"
    assert prepared[0]["reviewed_action"] == ""
    assert (complete, partial) == (0, 1)


def test_prepare_reuses_unresolved_date_exclusion() -> None:
    module = load("prepare_v13_true_value_review.py")
    replay = [{"row_id": "V12F-001", "outcome": "excluded_exact_date_or_identity_unresolved", "v13_event_date": ""}]
    prepared, complete, partial = module.prepare([row("correct_date")], replay)
    assert prepared[0]["reviewed_action"] == "exclude_candidate"
    assert (complete, partial) == (1, 0)


def test_wrappers_target_v13_and_frozen_v12() -> None:
    validator = load("validate_v13_true_value_review.py")
    materializer = load("materialize_v13_true_value_plan.py")
    assert validator.core.TEMPLATE.name == "v13_remediation_BATCH_TRUE_VALUE_REVIEW.csv"
    assert validator.core.RELEASE == materializer.core.RELEASE
    assert materializer.core.COMPLETED.name == "v13_remediation_BATCH_TRUE_VALUE_REVIEW_COMPLETED.csv"
    assert materializer.core.TRUE_VALUE_STATUS == (
        "v13_true_value_plan_unapplied_structured_attribute_gate_pending"
    )
