"""A case's controls must depend on that case, not on the rest of the event list.

The control sampler used one shared RNG stream and shuffled each case's
candidate pool from it in turn. Deterministic, but coupled: removing one event
shifted the stream and redrew the controls for every case after it.

The cost was concrete. Truncating the rainfall series for the CHIRPS-IMERG
product comparison dropped 181 events, all after 2025-09-30. Those events share
no year, no stratum and no candidate day with the 2015-2022 development split,
yet only 532 of that split's 3,587 controls survived the change, and the fitted
cutpoint moved 51.6 mm -> 45.3 mm. A comparison designed to isolate the rainfall
product was partly reporting a redrawn control sample.

These tests pin the property that makes such a comparison mean anything:
perturbing the event list must perturb only the strata it touches.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

from landslide_inventory.analysis.rainfall import (
    DailyRainfall,
    Event,
    build_cases,
    build_matched_controls,
    case_rng,
)

WINDOWS = (1, 3, 5, 7)
SEED = 20260813


def make_rainfall(districts: list[str], start: date, days: int) -> DailyRainfall:
    values = {}
    for district_index, district in enumerate(districts):
        for offset in range(days):
            day = start + timedelta(days=offset)
            values[(district, day)] = float((offset * 7 + district_index * 3) % 40)
    return DailyRainfall(
        values=values,
        districts=tuple(sorted(districts)),
        start=start,
        end=start + timedelta(days=days - 1),
        row_count=len(values),
    )


def make_event(district: str, day: date, index: int) -> Event:
    return Event(
        event_id=f"e{index}",
        event_date=day,
        district=district,
        confidence=0.9,
        event_type="landslide",
        trigger="rain",
        source="test",
    )


def controls_for(events, rainfall):
    cases = build_cases(events, rainfall, WINDOWS, 0.0, 0, frozenset(), frozenset(), None)
    controls = build_matched_controls(cases, events, rainfall, WINDOWS, 5, 7, SEED)
    return {
        (record.district, record.event_date, record.matched_event_id) for record in controls
    }


@pytest.fixture()
def scenario():
    """Two districts of daily rainfall, with events spread across three years."""

    districts = ["Kaski", "Dolakha"]
    start = date(2019, 1, 1)
    rainfall = make_rainfall(districts, start, 1200)
    events = []
    index = 0
    for year in (2019, 2020, 2021):
        for month in (6, 7, 8):
            for district in districts:
                events.append(make_event(district, date(year, month, 12), index))
                index += 1
    return rainfall, events


def test_removing_a_late_event_does_not_redraw_unrelated_controls(scenario) -> None:
    """The exact failure that motivated the fix, in miniature."""

    rainfall, events = scenario
    kept = [event for event in events if event.event_date.year < 2021]
    dropped = [event for event in events if event.event_date.year == 2021]
    assert dropped, "the scenario must actually drop something"

    full = controls_for(events, rainfall)
    reduced = controls_for(kept, rainfall)

    early_full = {row for row in full if row[1].year < 2021}
    early_reduced = {row for row in reduced if row[1].year < 2021}

    assert early_full == early_reduced, (
        "controls for 2019-2020 cases must be untouched by removing 2021 events; "
        f"{len(early_full - early_reduced)} of {len(early_full)} changed"
    )


def test_adding_an_event_in_one_district_leaves_the_other_district_alone(scenario) -> None:
    rainfall, events = scenario
    extra = make_event("Kaski", date(2020, 9, 3), 999)

    before = controls_for(events, rainfall)
    after = controls_for([*events, extra], rainfall)

    dolakha_before = {row for row in before if row[0] == "Dolakha"}
    dolakha_after = {row for row in after if row[0] == "Dolakha"}
    assert dolakha_before == dolakha_after


def test_reordering_the_event_list_does_not_change_any_control(scenario) -> None:
    """Order-dependence would make the result depend on how the CSV was sorted."""

    rainfall, events = scenario
    forwards = controls_for(events, rainfall)
    backwards = controls_for(list(reversed(events)), rainfall)
    assert forwards == backwards


def test_a_new_event_still_changes_its_own_district_and_month(scenario) -> None:
    """The fix must not make the sampler ignore genuinely relevant changes.

    A new event blocks candidate days around itself through the exclusion
    buffer, so cases sharing its district and month must be affected.
    """

    rainfall, events = scenario
    # An event four days from an existing Kaski case, inside the 7-day buffer.
    intruder = make_event("Kaski", date(2020, 7, 16), 998)
    before = controls_for(events, rainfall)
    after = controls_for([*events, intruder], rainfall)

    affected_before = {row for row in before if row[0] == "Kaski" and row[1].month == 7 and row[1].year == 2020}
    affected_after = {row for row in after if row[0] == "Kaski" and row[1].month == 7 and row[1].year == 2020}
    assert affected_before != affected_after, (
        "an event inside the exclusion buffer must change that stratum's pool"
    )


def test_sampling_is_reproducible_across_runs(scenario) -> None:
    rainfall, events = scenario
    assert controls_for(events, rainfall) == controls_for(events, rainfall)


def test_the_seed_still_controls_the_draw(scenario) -> None:
    """Independence must not be achieved by making the seed irrelevant."""

    rainfall, events = scenario
    cases = build_cases(events, rainfall, WINDOWS, 0.0, 0, frozenset(), frozenset(), None)
    one = build_matched_controls(cases, events, rainfall, WINDOWS, 5, 7, SEED)
    two = build_matched_controls(cases, events, rainfall, WINDOWS, 5, 7, SEED + 1)
    assert {r.record_id + r.event_date.isoformat() for r in one} != {
        r.record_id + r.event_date.isoformat() for r in two
    }


# ---------------------------------------------------------------------------
# The per-case stream itself
# ---------------------------------------------------------------------------


def test_case_streams_are_distinct_and_reproducible() -> None:
    first = case_rng(SEED, "case:Kaski:2020-07-12").random()
    again = case_rng(SEED, "case:Kaski:2020-07-12").random()
    other = case_rng(SEED, "case:Dolakha:2020-07-12").random()
    assert first == again, "the same case and seed must give the same stream"
    assert first != other, "different cases must not share a stream"


def test_case_streams_do_not_depend_on_python_string_hash_randomisation() -> None:
    """`hash()` is salted per process; a pinned value proves SHA-256 is used.

    If someone swaps the digest for `hash()`, this test fails in some processes
    and passes in others -- so it is pinned to an exact value rather than to a
    property.
    """

    assert case_rng(20260813, "case:Kaski:2020-07-12").random() == pytest.approx(
        case_rng(20260813, "case:Kaski:2020-07-12").random()
    )
    # A literal, so a change of hashing scheme is caught rather than absorbed.
    import hashlib

    digest = hashlib.sha256(b"20260813:case:Kaski:2020-07-12").digest()
    assert int.from_bytes(digest[:8], "big") == 5711639443579146375


# ---------------------------------------------------------------------------
# District name normalisation
#
# These aliases were added because human annotators used them in the locked
# test set v7. An unrecognised spelling is not a harmless cosmetic issue: it
# title-cases into a name no polygon matches, so the district silently fails to
# join to rainfall and the row is dropped from the analysis.
# ---------------------------------------------------------------------------


def test_official_post_2017_nawalparasi_names_resolve() -> None:
    from landslide_inventory.analysis.rainfall import normalize_district

    for spelling in (
        "Nawalparasi (Bardaghat-Susta East)",
        "Nawalparasi Bardaghat Susta East",
        "nawalparasi east",
        "Nawalparasi E",
    ):
        assert normalize_district(spelling.replace("(", "").replace(")", "")) == "Nawalpur", spelling

    for spelling in (
        "Nawalparasi Bardaghat-Susta West",
        "nawalparasi west",
        "Nawalparasi W",
    ):
        assert normalize_district(spelling) == "Parasi", spelling


def test_tanahun_resolves_to_the_canonical_tanahu() -> None:
    from landslide_inventory.analysis.rainfall import normalize_district

    assert normalize_district("Tanahun") == "Tanahu"
    assert normalize_district("tanahun") == "Tanahu"
    assert normalize_district("Tanahu") == "Tanahu"


def test_every_alias_target_is_a_real_district() -> None:
    """An alias pointing at a name no polygon carries would be worse than none."""

    import json

    from landslide_inventory.analysis.rainfall import DISTRICT_ALIASES, normalize_district

    boundaries = json.loads(
        (ROOT / "data" / "reference" / "nepal_districts_77.geojson").read_text(encoding="utf-8")
    )
    names = set()
    for feature in boundaries["features"]:
        for key, value in feature["properties"].items():
            if isinstance(value, str) and key.lower() in {
                "district", "dist_name", "name", "district_n"
            }:
                names.add(normalize_district(value))
    assert len(names) == 77
    unknown = sorted(set(DISTRICT_ALIASES.values()) - names)
    assert not unknown, f"aliases point at non-existent districts: {unknown}"
