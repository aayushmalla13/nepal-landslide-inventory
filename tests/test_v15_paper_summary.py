"""Tests for the generated v1.5 paper summary."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load():
    path = ROOT / "scripts/build_v15_paper_summary.py"
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_inventory_profile_counts_frozen_dimensions() -> None:
    module = load()
    rows = [
        {
            "event_date_ad": "2025-06-01",
            "district": "Kaski",
            "representative_source": "source-a",
            "event_type": "landslide",
            "hazard_type": "landslide",
            "event_granularity": "single",
            "cluster_size": "2",
        },
        {
            "event_date_ad": "2026-01-01",
            "district": "Dolakha",
            "representative_source": "source-b",
            "event_type": "road_obstruction",
            "hazard_type": "landslide",
            "event_granularity": "single",
            "cluster_size": "1",
        },
    ]
    profile = module.inventory_profile(rows)
    assert profile["events"] == 2
    assert profile["districts_represented"] == 2
    assert profile["representative_sources"] == 2
    assert profile["multi_article_clusters"] == 1
    assert profile["monsoon_events_jun_sep"] == 1


def test_prespecified_and_descriptive_metric_labels_are_distinct() -> None:
    module = load()
    score = {
        "promotion_decision": {
            "checks": {
                "event_existence_precision": {"passed": True},
                "date_accuracy": {"passed": False},
            }
        }
    }
    assert module.metric_result("event_existence_precision", score) == "pass"
    assert module.metric_result("date_accuracy", score) == "fail"
    assert module.metric_result("deaths_exact_accuracy", score) == "descriptive"
