"""Tests for the v1.4 remediation queue wrapper."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load():
    path = ROOT / "scripts/build_v14_remediation_queue.py"
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_wrapper_targets_v13_validation_and_v14_outputs() -> None:
    module = load()
    assert module.core.COMPLETED.name == "v13_final_validation_COMPLETED.csv"
    assert module.core.VALIDATION_SCORE.name == "v13_final_validation_score.json"
    assert module.core.QUEUE.name == "v14_remediation_queue.csv"
    assert module.core.BATCH_OUTPUTS["requires_article_mapping"].name == (
        "v14_remediation_BATCH_ARTICLE_MAPPING.csv"
    )


def test_queue_rows_are_versioned_v14() -> None:
    module = load()
    labels = [
        {
            "row_id": "V13F-001",
            "event_id": "event-1",
            "event_really_happened": "no",
            "one_physical_event": "",
            "district_correct": "",
            "date_correct": "",
            "municipality_correct": "",
            "event_type_true": "",
            "hazard_type_true": "",
            "deaths_true": "",
            "duplicate_merge_correct": "",
            "notes": "Not an event.",
            "annotator": "aayush",
            "claimed_event_date": "2024-01-01",
            "claimed_district": "Kaski",
            "claimed_municipality": "",
            "claimed_event_type": "landslide",
            "claimed_hazard_type": "landslide",
            "claimed_deaths": "",
            "claimed_missing": "",
            "claimed_injured": "",
            "cluster_article_count": "1",
            "representative_title": "Example",
            "representative_url": "https://example.test/1",
        }
    ]
    reading = {"V13F-001": {**labels[0], "article_evidence": "Evidence"}}
    weights = {
        "V13F-001": {
            "stratum": "en|early|landslide|single",
            "sampling_weight": "1.0",
        }
    }
    rows = module.build_queue_rows(labels, reading, weights)
    assert rows[0]["queue_id"] == "V14R-001"
    assert rows[0]["sample_role"] == "v13_final_probability"
    assert rows[0]["correction_layer"] == "v14_remediation"
