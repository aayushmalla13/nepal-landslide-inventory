"""Tests for leave-one-year-out and spatially held-out validation."""

from __future__ import annotations

import math
from datetime import date, timedelta

import pytest

from landslide_inventory.analysis.rainfall import RainRecord
from landslide_inventory.analysis.validation import (
    district_folds,
    leave_one_year_out,
    spatial_holdout,
    summarize_folds,
)


def make(day: date, district: str, label: int, value: float) -> RainRecord:
    return RainRecord(
        record_id=f"{district}:{day}:{label}:{value}",
        matched_event_id="m",
        event_date=day,
        district=district,
        label=label,
        confidence=0.9,
        values={5: value},
        lagged_values={5: value / 2},
    )


def separable_records(years: tuple[int, ...], districts: tuple[str, ...]) -> list[RainRecord]:
    records: list[RainRecord] = []
    for year in years:
        for index, district in enumerate(districts):
            base = date(year, 7, 1)
            records.append(make(base + timedelta(days=index), district, 1, 80.0 + index))
            records.append(make(base + timedelta(days=index + 20), district, 0, 5.0 + index))
    return records


def test_district_folds_are_deterministic_and_independent_of_input_order() -> None:
    names = ["Kaski", "Achham", "Dolakha", "Bajura", "Jhapa"]
    first = district_folds(names, 3)
    second = district_folds(list(reversed(names)), 3)
    assert first == second
    assert set(first.values()) <= {0, 1, 2}
    with pytest.raises(ValueError, match="at least two folds"):
        district_folds(names, 1)


def test_leave_one_year_out_returns_one_result_per_year() -> None:
    records = separable_records((2019, 2020, 2021), ("A", "B", "C"))
    results = leave_one_year_out(records, lambda record: record.values[5])
    assert [result.fold for result in results] == ["2019", "2020", "2021"]
    assert all(result.n_cases == 3 and result.n_controls == 3 for result in results)
    assert all(result.auc == pytest.approx(1.0) for result in results)


def test_leave_one_year_out_skips_years_without_both_labels() -> None:
    records = separable_records((2019, 2020), ("A", "B"))
    records.append(make(date(2022, 7, 1), "A", 1, 90.0))
    results = leave_one_year_out(records, lambda record: record.values[5])
    assert [result.fold for result in results] == ["2019", "2020"]


def test_spatial_holdout_evaluates_districts_absent_from_the_fit() -> None:
    records = separable_records((2019, 2020), ("A", "B", "C", "D", "E"))
    results = spatial_holdout(records, lambda record: record.values[5], folds=5)
    assert len(results) == 5
    assert [result.fold for result in results] == [f"district_fold_{i}" for i in range(1, 6)]
    for result in results:
        assert result.n_cases == 2
        assert result.n_controls == 2


def test_validation_uses_the_requested_exposure() -> None:
    """The lagged accessor must actually change the fitted cutpoint."""

    records = separable_records((2019, 2020), ("A", "B"))
    concurrent = leave_one_year_out(records, lambda record: record.values[5])
    antecedent = leave_one_year_out(records, lambda record: record.lagged_values[5])
    assert concurrent[0].threshold_mm != antecedent[0].threshold_mm
    assert antecedent[0].threshold_mm == pytest.approx(concurrent[0].threshold_mm / 2)


def test_summarize_folds_reports_spread_and_threshold_range() -> None:
    records = separable_records((2019, 2020, 2021), ("A", "B"))
    summary = summarize_folds(leave_one_year_out(records, lambda record: record.values[5]))
    assert summary["folds"] == 3.0
    assert summary["auc_median"] == pytest.approx(1.0)
    assert summary["auc_sd"] == pytest.approx(0.0)
    assert math.isfinite(summary["threshold_min_mm"])
    assert summary["threshold_min_mm"] <= summary["threshold_max_mm"]


def test_summarize_folds_is_empty_without_results() -> None:
    assert summarize_folds([]) == {}
