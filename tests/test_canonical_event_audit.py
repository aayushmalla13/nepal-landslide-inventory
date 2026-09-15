"""Regression tests for the frozen canonical event-level audit."""

from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "outputs"


def load(name: str):
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_allocation_preserves_small_strata_and_total() -> None:
    draw = load("draw_canonical_event_audit")
    sizes = {"large": 200, "medium": 40, "small": 4}
    allocation = draw.allocate_strata(sizes, 30, minimum=3)
    assert sum(allocation.values()) == 30
    assert allocation["small"] >= 3
    assert all(0 < allocation[key] <= sizes[key] for key in sizes)


def test_selection_is_deterministic_and_stratified() -> None:
    draw = load("draw_canonical_event_audit")
    rows = []
    for index in range(80):
        rows.append(
            {
                "event_id": f"event-{index:03d}",
                "event_date_ad": "2017-07-01" if index < 40 else "2024-07-01",
                "representative_title": "पहिरो" if index % 2 else "Landslide",
                "event_type": "road_obstruction" if index % 3 == 0 else "landslide",
                "cluster_size": "2" if index % 5 == 0 else "1",
            }
        )
    first, sizes, allocation = draw.select_rows(rows, total=40, seed=99)
    second, _, _ = draw.select_rows(rows, total=40, seed=99)
    assert [row["event_id"] for row in first] == [row["event_id"] for row in second]
    assert len(first) == 40
    assert set(allocation) == set(sizes)


def test_weighted_estimate_respects_sampling_weights() -> None:
    score = load("score_canonical_event_audit")
    rows = [
        {"answer": "yes", "sampling_weight": "9", "stratum": "a"},
        {"answer": "no", "sampling_weight": "1", "stratum": "b"},
    ]
    estimate, represented, decisive, unclear = score.weighted_estimate(
        rows, lambda row: score.binary_label(row["answer"])
    )
    assert estimate == 0.9
    assert represented == 10
    assert decisive == 2
    assert unclear == 0


def test_usable_record_requires_event_location_and_date() -> None:
    score = load("score_canonical_event_audit")
    valid = {
        "event_really_happened": "yes",
        "one_physical_event": "yes",
        "district_correct": "yes",
        "date_correct": "yes",
    }
    assert score.usable_record(valid) == 1.0
    assert score.usable_record({**valid, "date_correct": "no"}) == 0.0
    assert score.usable_record({**valid, "district_correct": "unclear"}) is None
    assert score.usable_record({**valid, "event_really_happened": "no"}) == 0.0


PACK = OUTPUT / "canonical_event_audit_LABEL_HERE.csv"
READING = OUTPUT / "canonical_event_audit_reading_pack.csv"
WEIGHTS = OUTPUT / "canonical_event_audit_weights.csv"
MANIFEST = OUTPUT / "canonical_event_audit_manifest.json"


@pytest.mark.skipif(not PACK.exists(), reason="canonical event audit has not been drawn")
def test_generated_pack_is_blind_complete_and_joinable() -> None:
    labels, readings, weights = read(PACK), read(READING), read(WEIGHTS)
    assert len(labels) == len(readings) == len(weights) == 150
    assert [row["row_id"] for row in labels] == [row["row_id"] for row in readings]
    assert [row["row_id"] for row in labels] == [row["row_id"] for row in weights]
    assert all(not row["event_really_happened"] for row in labels)
    assert not any("conf" in column or "specificity" in column for column in labels[0])
    assert sum(len(row["article_evidence"].strip()) >= 50 for row in readings) >= 142
    assert all(
        abs(float(row["sampling_weight"]) * float(row["inclusion_probability"]) - 1) < 1e-8
        for row in weights
    )
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["canonical_rows"] == 2885
    assert manifest["sample_rows"] == 150
    assert manifest["canonical_sha256"] == load("draw_canonical_event_audit").CANONICAL_SHA256
