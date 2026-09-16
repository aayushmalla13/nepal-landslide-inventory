"""Tests for audit-driven canonical event correction candidates."""

from __future__ import annotations

import importlib.util
import csv
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def load():
    path = ROOT / "scripts" / "build_canonical_event_correction_candidates.py"
    spec = importlib.util.spec_from_file_location("build_candidates", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def valid_row() -> dict[str, str]:
    return {
        "event_really_happened": "yes",
        "one_physical_event": "yes",
        "district_correct": "yes",
        "date_correct": "yes",
        "municipality_correct": "",
        "claimed_event_type": "landslide",
        "event_type_true": "landslide",
        "claimed_hazard_type": "landslide",
        "hazard_type_true": "landslide",
        "claimed_deaths": "",
        "deaths_true": "not_reported",
        "duplicate_merge_correct": "not_applicable",
    }


def test_false_event_is_an_exclusion_candidate() -> None:
    module = load()
    actions, proposed = module.classify({**valid_row(), "event_really_happened": "no"})
    assert actions == ["exclude_false_event"]
    assert not any(proposed.values())
    assert module.priority(actions) == "P0_identity_or_linkage"
    assert module.readiness(actions) == "requires_article_mapping"


def test_structured_attribute_corrections_are_proposed() -> None:
    module = load()
    row = {
        **valid_row(),
        "event_type_true": "road_obstruction",
        "hazard_type_true": "debris_flow",
        "deaths_true": "3",
    }
    actions, proposed = module.classify(row)
    assert actions == ["correct_event_type", "correct_hazard_type", "correct_deaths"]
    assert proposed == {"event_type": "road_obstruction", "hazard_type": "debris_flow", "deaths": "3"}
    assert module.readiness(actions) == "structured_attribute_candidate"
    assert module.priority(actions) == "P1_attribute"


def test_identity_failures_require_source_review() -> None:
    module = load()
    row = {
        **valid_row(),
        "one_physical_event": "no",
        "district_correct": "no",
        "date_correct": "unclear",
        "duplicate_merge_correct": "no",
    }
    actions, _proposed = module.classify(row)
    assert actions == [
        "split_or_exclude_aggregate", "correct_district", "review_date",
        "recluster_articles",
    ]
    assert module.readiness(actions) == "requires_article_mapping"
    assert module.priority(actions) == "P0_identity_or_linkage"


def test_valid_row_has_no_candidate_actions() -> None:
    module = load()
    actions, proposed = module.classify(valid_row())
    assert actions == []
    assert not any(proposed.values())


@pytest.mark.skipif(
    not (ROOT / "data" / "outputs" / "canonical_event_correction_candidates.csv").exists(),
    reason="correction candidate artifacts have not been generated",
)
def test_generated_batches_partition_candidate_queue() -> None:
    module = load()

    def ids(path: Path) -> set[str]:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return {row["candidate_id"] for row in csv.DictReader(handle)}

    all_ids = ids(module.CANDIDATES)
    batches = [ids(path) for path in module.BATCH_OUTPUTS.values()]
    assert all_ids == set().union(*batches)
    assert sum(len(batch) for batch in batches) == len(all_ids)
