"""Tests for the scope-limited v1.5 research release."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def load():
    path = ROOT / "scripts/freeze_v15_event_detection_release.py"
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def score(*, event: bool = True, district: bool = True, full: bool = False):
    metric = {"estimate": 0.95, "ci95_stratified_bootstrap": [0.91, 0.98]}
    return {
        "metrics": {
            "event_existence_precision": metric,
            "district_accuracy": metric,
        },
        "promotion_decision": {
            "passed": full,
            "checks": {
                "event_existence_precision": {"passed": event},
                "district_accuracy": {"passed": district},
                "usable_record_precision": {"passed": False},
                "single_event_accuracy": {"passed": False},
                "date_accuracy": {"passed": False},
            },
        },
    }


def test_release_scope_records_partial_validation() -> None:
    module = load()
    scope = module.validation_scope(score())
    assert scope["event_detection"]["validated"] is True
    assert scope["district_assignment"]["validated"] is True
    assert scope["full_record"]["validated"] is False
    assert scope["full_record"]["failed_prespecified_metrics"] == [
        "usable_record_precision",
        "single_event_accuracy",
        "date_accuracy",
    ]


def test_release_scope_rejects_failed_event_detection() -> None:
    module = load()
    with pytest.raises(ValueError, match="event-existence"):
        module.validation_scope(score(event=False))


def test_partial_freezer_rejects_full_promotion() -> None:
    module = load()
    with pytest.raises(ValueError, match="cannot promote"):
        module.validation_scope(score(full=True))
