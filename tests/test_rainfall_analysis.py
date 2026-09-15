from __future__ import annotations

from datetime import date, timedelta

import pytest

from landslide_inventory.analysis.rainfall import (
    DailyRainfall,
    Event,
    RainRecord,
    accumulation,
    auc,
    balanced_panel_sources,
    bootstrap_metric_intervals,
    bootstrap_threshold_interval,
    build_cases,
    build_matched_controls,
    normalize_district,
    read_daily_rainfall,
    read_events,
    round_output,
    youden_threshold,
)


def test_read_daily_rainfall_normalizes_boundary_names_and_rejects_duplicates(tmp_path) -> None:
    path = tmp_path / "rain.csv"
    path.write_text(
        "date,district,rain_mm\n"
        "2024-07-01,CHITAWAN,4.5\n"
        "2024-07-01,RUKUM_E,2.0\n",
        encoding="utf-8",
    )
    data = read_daily_rainfall(path)
    assert data.values[("Chitwan", date(2024, 7, 1))] == 4.5
    assert data.values[("Eastern Rukum", date(2024, 7, 1))] == 2.0

    with path.open("a", encoding="utf-8") as handle:
        handle.write("2024-07-01,Chitwan,3.0\n")
    with pytest.raises(ValueError, match="Duplicate rainfall district-day"):
        read_daily_rainfall(path)


def test_antecedent_windows_include_event_day_and_require_complete_history() -> None:
    start = date(2024, 6, 25)
    values = {("Dhading", start + timedelta(days=index)): float(index + 1) for index in range(10)}
    rainfall = DailyRainfall(values, ("Dhading",), start, start + timedelta(days=9), 10)
    event_day = date(2024, 7, 1)
    assert accumulation(rainfall, "Dhading", event_day, 1) == 7.0
    assert accumulation(rainfall, "Dhading", event_day, 3) == 18.0
    assert accumulation(rainfall, "Dhading", start, 3) is None


def test_matched_controls_are_deterministic_and_respect_event_buffer() -> None:
    start = date(2024, 7, 1)
    values = {("Dhading", start + timedelta(days=index)): 1.0 for index in range(31)}
    rainfall = DailyRainfall(values, ("Dhading",), start, date(2024, 7, 31), 31)
    events = [Event("e1", date(2024, 7, 16), "Dhading", 0.9, "landslide")]
    cases = build_cases(events, rainfall, [1, 3, 5, 7], 0.78)
    first = build_matched_controls(cases, events, rainfall, [1, 3, 5, 7], 5, 7, 42)
    second = build_matched_controls(cases, events, rainfall, [1, 3, 5, 7], 5, 7, 42)
    assert [record.event_date for record in first] == [record.event_date for record in second]
    assert len(first) == 5
    assert all(abs((record.event_date - events[0].event_date).days) > 7 for record in first)
    assert all(record.district == "Dhading" for record in first)


def test_auc_and_youden_threshold_on_separable_scores() -> None:
    labels = [0, 0, 0, 1, 1, 1]
    scores = [1.0, 2.0, 3.0, 8.0, 9.0, 10.0]
    threshold = youden_threshold(labels, scores)
    assert threshold == 8.0
    assert auc(labels, scores) == 1.0


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("NAWALPARASI_E", "Nawalpur"),
        ("NAWALPARASI_W", "Parasi"),
        ("KABHREPALANCHOK", "Kavrepalanchok"),
        ("SIRAHA", "Siraha"),
    ],
)
def test_boundary_district_crosswalk(raw: str, expected: str) -> None:
    assert normalize_district(raw) == expected


def test_lagged_windows_exclude_the_reported_event_day() -> None:
    """The strictly antecedent co-primary exposure must not see the event day."""

    start = date(2024, 6, 25)
    values = {("Dhading", start + timedelta(days=index)): float(index + 1) for index in range(10)}
    rainfall = DailyRainfall(values, ("Dhading",), start, start + timedelta(days=9), 10)
    event = Event("e1", date(2024, 7, 1), "Dhading", 0.9, "landslide")
    cases = build_cases([event], rainfall, [1, 3], 0.78)
    assert len(cases) == 1
    record = cases[0]
    # Day 2024-07-01 is the 7th day, worth 7.0 mm.
    assert record.values[1] == 7.0
    assert record.values[3] == 18.0
    assert record.lagged_values[1] == 6.0
    assert record.lagged_values[3] == 15.0
    # The lagged window drops the event day (7.0) and picks up the day before
    # the concurrent window started (4.0).
    assert record.lagged_values[3] == record.values[3] - record.values[1] + 4.0


def test_build_cases_can_restrict_to_a_source_panel() -> None:
    start = date(2024, 7, 1)
    values = {("Dhading", start + timedelta(days=index)): 1.0 for index in range(31)}
    rainfall = DailyRainfall(values, ("Dhading",), start, date(2024, 7, 31), 31)
    events = [
        Event("e1", date(2024, 7, 10), "Dhading", 0.9, "landslide", source="setopati"),
        Event("e2", date(2024, 7, 20), "Dhading", 0.9, "landslide", source="deshsanchar"),
    ]
    everything = build_cases(events, rainfall, [1], 0.78)
    restricted = build_cases(
        events, rainfall, [1], 0.78, included_sources=frozenset({"setopati"})
    )
    assert len(everything) == 2
    assert [record.event_date for record in restricted] == [date(2024, 7, 10)]


def test_balanced_panel_keeps_only_publishers_present_on_both_sides_of_the_split() -> None:
    split = date(2022, 12, 31)
    events = [
        Event(f"a{i}", date(2021, 7, 1), "Dhading", 0.9, "landslide", source="steady")
        for i in range(3)
    ]
    events += [
        Event(f"b{i}", date(2024, 7, 1), "Dhading", 0.9, "landslide", source="steady")
        for i in range(3)
    ]
    events += [
        Event(f"c{i}", date(2021, 7, 1), "Dhading", 0.9, "landslide", source="stopped")
        for i in range(9)
    ]
    events += [
        Event(f"d{i}", date(2024, 7, 1), "Dhading", 0.9, "landslide", source="started")
        for i in range(9)
    ]
    assert balanced_panel_sources(events, split, minimum_per_period=3) == ("steady",)
    assert balanced_panel_sources(events, split, minimum_per_period=4) == ()


def test_read_events_carries_the_representative_source() -> None:
    import csv
    import tempfile
    from pathlib import Path as _Path

    with tempfile.TemporaryDirectory() as folder:
        path = _Path(folder) / "canonical.csv"
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "event_id",
                    "event_date_ad",
                    "district",
                    "conf_date",
                    "event_type",
                    "trigger",
                    "event_granularity",
                    "representative_source",
                ],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "event_id": "event_1",
                    "event_date_ad": "2024-07-10",
                    "district": "DHADING",
                    "conf_date": "0.88",
                    "event_type": "landslide",
                    "trigger": "rainfall",
                    "event_granularity": "single",
                    "representative_source": "setopati",
                }
            )
        events = read_events(path)
    assert [event.source for event in events] == ["setopati"]
    assert events[0].district == "Dhading"


def test_round_output_stabilizes_emitted_values_without_touching_unknowns() -> None:
    """Float summation order differs across platforms; release hashes must not."""

    assert round_output(46.121095999999994) == round_output(46.121096)
    assert round_output(float("nan")) != round_output(float("nan"))  # nan stays nan
    assert round_output(float("inf")) == float("inf")
    assert round_output(3) == 3


def test_bootstrap_helpers_accept_an_alternative_exposure() -> None:
    start = date(2024, 7, 1)
    records = []
    for index, district in enumerate(("A", "B", "C")):
        for label, value in ((1, 90.0), (0, 5.0)):
            records.append(
                RainRecord(
                    record_id=f"{district}:{label}",
                    matched_event_id="m",
                    event_date=start + timedelta(days=index + label),
                    district=district,
                    label=label,
                    confidence=0.9,
                    values={5: value},
                    lagged_values={5: value * 2},
                )
            )
    concurrent = bootstrap_threshold_interval(records, 5, iterations=25, seed=1)
    antecedent = bootstrap_threshold_interval(
        records, 5, iterations=25, seed=1, value_of=lambda record: record.lagged_values[5]
    )
    assert concurrent is not None and antecedent is not None
    assert antecedent[0] == pytest.approx(concurrent[0] * 2)
    intervals = bootstrap_metric_intervals(
        records, 5, 10.0, iterations=25, seed=1, value_of=lambda record: record.lagged_values[5]
    )
    assert intervals["auc"][0] == pytest.approx(1.0)
