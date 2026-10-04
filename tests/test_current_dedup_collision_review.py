"""Tests for the current-state dedup collision review pack."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from landslide_inventory.unify.similarity import TfidfIndex


ROOT = Path(__file__).resolve().parents[1]


def load():
    path = ROOT / "scripts" / "build_current_dedup_collision_review.py"
    spec = importlib.util.spec_from_file_location("current_collision_review", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def article(module, *, title: str, body: str, ward: str = "", place: str = "",
            deaths: int | None = None):
    return module.ArticleEvidence(
        url=f"https://example.test/{title}", source="source", title=title, body=body,
        route_lang="en", ward=ward, place=place, deaths=deaths,
        missing=None, injured=None,
    )


def cluster(module, event_id: str, evidence):
    return module.ClusterEvidence(
        event_id=event_id, cluster_id=f"cluster-{event_id}", district="Dhading",
        event_date="2024-07-16", municipality="Nilkantha Municipality",
        event_type="landslide", hazard_type="landslide",
        representative_url=evidence.url, articles=(evidence,),
    )


def test_strong_factual_pair_is_prioritized_as_likely_merge() -> None:
    module = load()
    left_article = article(
        module, title="Three killed in Nilkantha landslide",
        body="A landslide at Ward 4 killed three people after rain.",
        ward="4", place="Besi", deaths=3,
    )
    right_article = article(
        module, title="Nilkantha landslide leaves three dead",
        body="Three people died when a rain-triggered landslide hit Ward 4.",
        ward="4", place="Besi", deaths=3,
    )
    tfidf = TfidfIndex([left_article.body, right_article.body])
    result = module.score_pair(
        cluster(module, "event-a", left_article),
        cluster(module, "event-b", right_article), tfidf,
    )
    assert result["priority"] == "P1_likely_merge"
    assert result["casualty_state"] == "agreement"
    assert "ward_overlap" in result["signals"]


def test_casualty_and_ward_conflicts_are_not_merge_recommendations() -> None:
    module = load()
    left_article = article(module, title="Landslide one", body="First failure.", ward="4", place="Besi", deaths=1)
    right_article = article(module, title="Landslide two", body="Second failure.", ward="9", place="Danda", deaths=6)
    tfidf = TfidfIndex([left_article.body, right_article.body])
    result = module.score_pair(
        cluster(module, "event-a", left_article),
        cluster(module, "event-b", right_article), tfidf,
    )
    assert result["priority"] == "P3_conflict_or_likely_distinct"
    assert result["recommendation"] == "review_likely_distinct"
    assert "casualty_conflict" in result["conflicts"]
    assert "ward_conflict" in result["conflicts"]


def test_pair_id_is_order_stable_when_event_ids_are_sorted() -> None:
    module = load()
    assert module.stable_id("collision_pair", "event-a", "event-b") == module.stable_id(
        "collision_pair", "event-a", "event-b"
    )
