"""The gate that decides whether proposed place fills may enter a release.

The backfill proposes 84 municipality and 1,696 ward values from text the
pipeline already holds. They are cheap, which is exactly why they are dangerous:
a wrong municipality is not a missing value but a confident false location, and
nothing downstream can distinguish it from a correct one.

So the fills are gated on measured precision, and these tests pin the three
things that gate depends on: that precision is estimated with the sampling
design rather than as a raw accept rate, that already-labelled rows cannot be
drawn again, and that a place name attached to a person is not treated as an
event location.
"""

from __future__ import annotations

import csv
import importlib.util
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load(name: str):
    sys.path.insert(0, str(ROOT / "src"))
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def scorer():
    return load("score_place_backfill")


# ---------------------------------------------------------------------------
# Precision must respect the sampling design
# ---------------------------------------------------------------------------


def test_precision_is_stratified_not_a_raw_accept_rate(scorer) -> None:
    """A raw rate over the labelled rows would misweight the two strata.

    Municipality fills are a small stratum sampled heavily; ward fills a large
    stratum sampled lightly. Pooling them without weights lets the small
    stratum dominate an estimate meant to describe the population.
    """

    population = (
        [{"language": "en", "proposed_ward": "3"} for _ in range(1000)]
        + [{"language": "np", "proposed_ward": "4"} for _ in range(10)]
    )
    # The big stratum is excellent; the tiny one is terrible, and is sampled
    # just as heavily in the review pack.
    labelled = (
        [{"language": "en", "proposed_ward": "3", "ward_verdict": "accept"} for _ in range(10)]
        + [{"language": "np", "proposed_ward": "4", "ward_verdict": "reject"} for _ in range(10)]
    )
    result = scorer.score_field(
        labelled,
        population,
        proposal_column="proposed_ward",
        verdict_column="ward_verdict",
        field="ward",
    )
    assert result["pooled_precision"] == pytest.approx(0.5), "the naive rate"
    assert result["stratified_precision"] > 0.98, (
        "weighting by stratum size must let the 1000-row stratum dominate"
    )


def test_unsure_verdicts_are_excluded_from_both_sides_and_reported(scorer) -> None:
    """Counting them either way would be a decision disguised as arithmetic."""

    population = [{"language": "en", "proposed_ward": "1"} for _ in range(10)]
    labelled = [
        {"language": "en", "proposed_ward": "1", "ward_verdict": v}
        for v in ("accept", "accept", "reject", "unsure", "unsure")
    ]
    result = scorer.score_field(
        labelled, population, proposal_column="proposed_ward",
        verdict_column="ward_verdict", field="ward",
    )
    assert result["labelled_decided"] == 3
    assert result["unsure_excluded"] == 2
    assert result["pooled_precision"] == pytest.approx(2 / 3, abs=1e-4)


def test_rows_without_a_proposal_are_not_counted(scorer) -> None:
    """A blank proposal is not a correct one."""

    population = [{"language": "en", "proposed_municipality": ""} for _ in range(5)]
    labelled = [{"language": "en", "proposed_municipality": "", "municipality_verdict": "accept"}]
    result = scorer.score_field(
        labelled, population, proposal_column="proposed_municipality",
        verdict_column="municipality_verdict", field="municipality",
    )
    assert result["population_with_a_proposal"] == 0
    assert result["labelled_decided"] == 0
    assert result["pooled_precision"] is None


def test_wilson_interval_behaves_at_the_boundaries(scorer) -> None:
    """The normal approximation gives a zero-width interval at p=1; Wilson does not."""

    low, high = scorer.wilson_interval(10, 10)
    assert 0.0 < low < 1.0 and high == pytest.approx(1.0)
    low, high = scorer.wilson_interval(0, 10)
    assert low == pytest.approx(0.0) and 0.0 < high < 1.0
    assert all(math.isnan(v) for v in scorer.wilson_interval(0, 0))
    low, high = scorer.wilson_interval(5, 10)
    assert low < 0.5 < high


# ---------------------------------------------------------------------------
# A labelled row is spent
# ---------------------------------------------------------------------------


def test_a_previously_labelled_row_is_never_drawn_again() -> None:
    """The first pack motivated a code change, so re-using it flatters the fix."""

    report = load("place_backfill_report")
    spent = report._spent_keys(
        [ROOT / "data" / "outputs" / "place_backfill_review_pack_COMPLETED.csv"]
    )
    if not spent:
        pytest.skip("the completed first round is not present in this checkout")
    pack = ROOT / "data" / "outputs" / "place_backfill_review_pack.csv"
    if not pack.exists():
        pytest.skip("no review pack generated in this checkout")
    with pack.open("r", encoding="utf-8-sig", newline="") as handle:
        drawn = {(r["url"], r["event_date_ad"]) for r in csv.DictReader(handle)}
    assert not (drawn & spent), (
        f"{len(drawn & spent)} spent rows were drawn again; the confirmation "
        "sample would not be independent of the change it is meant to test"
    )


def test_spent_keys_tolerates_a_missing_file() -> None:
    report = load("place_backfill_report")
    assert report._spent_keys([ROOT / "data" / "outputs" / "no_such_pack.csv"]) == set()


# ---------------------------------------------------------------------------
# A place name attached to a person is not an event location
# ---------------------------------------------------------------------------


def test_a_municipality_in_a_home_address_is_not_proposed() -> None:
    """The dominant rejection reason in the first labelled round."""

    from landslide_inventory.unify.place_backfill import find_municipality_mentions
    from landslide_inventory.gazetteer_municipality import (
        municipality_districts,
        normalize_municipality,
    )

    # Use a real gazetteer name, found through the public API, so the test does
    # not depend on the gazetteer's internal structures.
    pretty = None
    for candidate in ("Melamchi Municipality", "Byas Municipality", "Bhaktapur Municipality"):
        if normalize_municipality(candidate, "en"):
            pretty = candidate
            break
    if pretty is None:
        pytest.skip("no known municipality resolves in this gazetteer build")

    event_text = f"A landslide swept away three houses in {pretty} on Tuesday."
    address_text = f"The deceased has been identified as Ram Bahadur, a resident of {pretty}."

    found_event = find_municipality_mentions(event_text, "en")
    found_address = find_municipality_mentions(address_text, "en")

    assert found_event, "an event-location mention must still be found"
    assert not found_address, (
        "a municipality given as a person's residence must not become a proposed fill"
    )
    assert municipality_districts(found_event[0].canonical)


def test_the_guard_does_not_silently_empty_the_proposals() -> None:
    """A guard that rejected everything would also pass the test above."""

    candidates = ROOT / "data" / "outputs" / "place_backfill_candidates.csv"
    if not candidates.exists():
        pytest.skip("no candidates generated in this checkout")
    with candidates.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    municipality = sum(1 for r in rows if r["proposed_municipality"].strip())
    ward = sum(1 for r in rows if r["proposed_ward"].strip())
    assert municipality > 50, municipality
    assert ward > 1000, ward


# ---------------------------------------------------------------------------
# The fills stay out of the inventory until precision earns them a place
# ---------------------------------------------------------------------------


def test_the_summary_still_records_the_fills_as_not_applied() -> None:
    import json

    path = ROOT / "data" / "outputs" / "place_backfill_summary.json"
    if not path.exists():
        pytest.skip("no summary in this checkout")
    summary = json.loads(path.read_text(encoding="utf-8"))
    assert "NOT APPLIED" in summary["status"].upper()
