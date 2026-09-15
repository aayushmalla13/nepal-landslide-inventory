from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name: str):
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_stratified_allocation_has_requested_size_and_minimum() -> None:
    draw = load("draw_v7_interannotator_pack")
    sizes = {"large": 100, "medium": 30, "small": 5}
    allocation = draw.allocate_strata(sizes, 30)
    assert sum(allocation.values()) == 30
    assert allocation["small"] == 5
    assert all(allocation[key] <= sizes[key] for key in sizes)


def test_blind_row_removes_every_truth_value() -> None:
    draw = load("draw_v7_interannotator_pack")
    row = {column: f"fixed-{column}" for column in draw.FROZEN_COLUMNS}
    row.update({column: "SECRET" for column in draw.TRUTH_COLUMNS})
    blinded = draw.blank_label_row(row)
    assert all(blinded[column] == "" for column in draw.TRUTH_COLUMNS)
    assert all(blinded[column] == row[column] for column in draw.FROZEN_COLUMNS)


def test_cohen_kappa_is_one_for_perfect_nonconstant_agreement() -> None:
    score = load("score_v7_interannotator")
    assert score.cohen_kappa(["yes", "no", "yes"], ["yes", "no", "yes"]) == 1.0


def test_headline_uses_the_frozen_single_event_definition() -> None:
    score = load("score_v7_interannotator")
    base = {
        "is_landslide_event_true": "yes",
        "in_nepal_true": "yes",
        "hazard_type_true": "landslide",
        "event_granularity_true": "single",
    }
    assert score.headline(base) == "yes"
    assert score.headline({**base, "event_granularity_true": "multi"}) == "no"
    assert score.headline({**base, "hazard_type_true": "unclear"}) == "unclear"
