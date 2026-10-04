"""Tests for the locked v0.8 fresh-validation workflow."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str):
    path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


draw = _load("draw_v08_fresh_validation.py")
score = _load("score_v08_fresh_validation.py")


def _row(event_id: str, url: str, event_type: str = "landslide") -> dict[str, str]:
    return {
        "event_id": event_id,
        "event_date_ad": "2024-07-01",
        "event_type": event_type,
        "cluster_size": "1",
        "representative_title": "Landslide report",
        "representative_url": url,
        "event_payload": json.dumps({"urls": [url]}),
    }


def test_stratified_selection_is_deterministic() -> None:
    rows = [
        _row(f"e{i}", f"u{i}", "landslide" if i < 10 else "road_obstruction") for i in range(20)
    ]
    first, sizes, allocation = draw.stratified_select(rows, lambda row: row["event_type"], 8, 2, 42)
    second, _, _ = draw.stratified_select(rows, lambda row: row["event_type"], 8, 2, 42)
    assert [row["event_id"] for row in first] == [row["event_id"] for row in second]
    assert sizes == {"landslide": 10, "road_obstruction": 10}
    assert allocation == {"landslide": 4, "road_obstruction": 4}


def test_embedded_urls_handles_json_and_evidence_text() -> None:
    value = '["https://example.test/a", "https://example.test/b"]\nURL: https://example.test/c'
    assert draw.embedded_urls(value) == {
        "https://example.test/a",
        "https://example.test/b",
        "https://example.test/c",
    }


def test_usable_record_requires_event_identity_location_and_date() -> None:
    base = {
        "event_really_happened": "yes",
        "one_physical_event": "yes",
        "district_correct": "yes",
        "date_correct": "yes",
    }
    assert score.usable_record(base) == 1.0
    assert score.usable_record({**base, "date_correct": "no"}) == 0.0
    assert score.usable_record({**base, "district_correct": "unclear"}) is None
    assert score.usable_record({**base, "event_really_happened": "no"}) == 0.0


def test_promotion_rule_requires_every_check() -> None:
    metrics = {
        name: {
            "estimate": estimate,
            "ci95_stratified_bootstrap": interval,
            "unclear_or_not_applicable_n": 0,
        }
        for name, estimate, interval in (
            ("event_existence_precision", 0.92, [0.86, 0.97]),
            ("usable_record_precision", 0.75, [0.63, 0.83]),
            ("single_event_accuracy", 0.90, [0.80, 0.96]),
            ("district_accuracy", 0.90, [0.80, 0.96]),
            ("date_accuracy", 0.90, [0.80, 0.96]),
        )
    }
    result = score.apply_promotion_rule(metrics, draw.PROMOTION_RULE, 150)
    assert result["passed"] is True
    metrics["date_accuracy"]["estimate"] = 0.84
    assert score.apply_promotion_rule(metrics, draw.PROMOTION_RULE, 150)["passed"] is False
