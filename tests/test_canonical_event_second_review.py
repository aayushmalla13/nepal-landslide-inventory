"""Tests for independent second review of the canonical event audit."""

from __future__ import annotations

import csv
import importlib.util
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


def test_second_review_order_is_deterministic_and_permuted() -> None:
    draw = load("draw_canonical_event_second_review")
    row_ids = [f"CEA-{index:03d}" for index in range(1, 151)]
    first = draw.shuffled_ids(row_ids)
    assert first == draw.shuffled_ids(row_ids)
    assert first != row_ids
    assert sorted(first) == sorted(row_ids)


def test_blank_second_review_does_not_copy_answers() -> None:
    draw = load("draw_canonical_event_second_review")
    source = {column: f"claim-{column}" for column in draw.CLAIM_COLUMNS}
    source.update({column: "SECRET" for column in draw.LABEL_COLUMNS})
    row = draw.blank_row(source, "CEA2-001")
    assert row["row_id"] == "CEA2-001"
    assert all(row[column] == "" for column in draw.LABEL_COLUMNS)


def test_kappa_and_usable_status() -> None:
    score = load("score_canonical_event_second_review")
    assert score.cohen_kappa(["yes", "no", "yes"], ["yes", "no", "yes"]) == 1.0
    valid = {
        "event_really_happened": "yes",
        "one_physical_event": "yes",
        "district_correct": "yes",
        "date_correct": "yes",
    }
    assert score.usable_status(valid) == "valid"
    assert score.usable_status({**valid, "date_correct": "no"}) == "invalid"
    assert score.usable_status({**valid, "district_correct": "unclear"}) == "unclear"


PACK = OUTPUT / "canonical_event_audit_second_LABEL_HERE.csv"
READING = OUTPUT / "canonical_event_audit_second_reading_pack.csv"
MAPPING = OUTPUT / "canonical_event_audit_second_mapping.csv"


@pytest.mark.skipif(not PACK.exists(), reason="second-review pack has not been drawn")
def test_generated_second_pack_is_complete_blind_and_joinable() -> None:
    labels, readings, mappings = read(PACK), read(READING), read(MAPPING)
    assert len(labels) == len(readings) == len(mappings) == 150
    assert [row["row_id"] for row in labels] == [row["row_id"] for row in readings]
    assert [row["row_id"] for row in labels] == [row["second_row_id"] for row in mappings]
    assert all(not row["event_really_happened"] and not row["notes"] for row in labels)
    assert all(len(row["article_evidence"].strip()) >= 50 for row in readings)
    first_ids = [row["first_row_id"] for row in mappings]
    assert first_ids != sorted(first_ids)
    assert len(set(first_ids)) == 150
