"""Tests for mapping audited canonical events to source articles."""

from __future__ import annotations

import csv
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "outputs"


def load():
    path = ROOT / "scripts" / "build_canonical_event_article_mapping_pack.py"
    spec = importlib.util.spec_from_file_location("build_article_mapping", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def candidate(actions: str, size: int) -> dict[str, str]:
    return {"recommended_actions": actions, "cluster_article_count": str(size)}


def test_resolution_routes_false_events_and_aggregate_articles() -> None:
    module = load()
    assert module.proposed_resolution(candidate("exclude_false_event", 1)) == "exclude_cluster"
    assert (
        module.proposed_resolution(candidate("split_or_exclude_aggregate;correct_date", 1))
        == "decompose_source_article"
    )
    assert (
        module.proposed_resolution(candidate("split_or_exclude_aggregate;recluster_articles", 3))
        == "recluster_and_decompose"
    )


@pytest.mark.skipif(
    not (OUTPUT / "canonical_event_article_membership_MAP.csv").exists(),
    reason="article mapping pack has not been generated",
)
def test_generated_pack_maps_every_candidate_and_article_once() -> None:
    module = load()

    def read(path: Path) -> list[dict[str, str]]:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))

    candidates = read(module.CANDIDATES)
    articles = read(module.ARTICLE_MAP)
    decisions = read(module.DECISIONS)
    assert len(decisions) == len(candidates)
    assert {row["candidate_id"] for row in decisions} == {row["candidate_id"] for row in candidates}
    assert len({row["mapping_id"] for row in articles}) == len(articles)
    expected = sum(int(row["cluster_article_count"]) for row in candidates)
    assert len(articles) == expected
    assert all(not row["final_resolution"] and not row["reviewed_by"] for row in decisions)
    assert all(not row["final_article_action"] and not row["final_event_groups"] for row in articles)
