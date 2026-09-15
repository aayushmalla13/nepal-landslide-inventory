"""Tests for the design-faithful matched-sample estimators."""

from __future__ import annotations

import math
from datetime import date, timedelta

import pytest

from landslide_inventory.analysis.matched import (
    build_matched_sets,
    conditional_logistic,
    matching_diagnostics,
    strict_matched_sets,
    within_stratum_concordance,
)
from landslide_inventory.analysis.rainfall import RainRecord


def record(
    record_id: str,
    matched: str,
    day: date,
    district: str,
    label: int,
    value: float,
    lagged: float | None = None,
) -> RainRecord:
    return RainRecord(
        record_id=record_id,
        matched_event_id=matched,
        event_date=day,
        district=district,
        label=label,
        confidence=0.9,
        values={5: value},
        lagged_values={5: value if lagged is None else lagged},
    )


def make_sets(count: int, controls_each: int, offset: float) -> list:
    """Build ``count`` strata where cases are wetter on average but overlap.

    Every third case is deliberately drier than its controls so the conditional
    likelihood has an interior maximum; a perfectly separated fixture would test
    the separation branch instead of the estimator.
    """

    cases = []
    controls = []
    start = date(2020, 7, 1)
    for index in range(count):
        district = f"D{index % 4}"
        case_id = f"case:{district}:{index}"
        case_value = 40.0 + offset if index % 3 else 40.0 - offset
        cases.append(record(case_id, "e", start + timedelta(days=index), district, 1, case_value))
        for control_index in range(controls_each):
            controls.append(
                record(
                    f"control:{case_id}:{control_index}",
                    case_id,
                    start + timedelta(days=index + 100 + control_index),
                    district,
                    0,
                    40.0 + control_index - controls_each / 2,
                )
            )
    return build_matched_sets(cases, controls)


def test_build_matched_sets_keeps_cases_without_controls() -> None:
    day = date(2021, 8, 1)
    case_a = record("case:A:1", "e1", day, "A", 1, 50.0)
    case_b = record("case:B:1", "e2", day, "B", 1, 10.0)
    control = record("control:case:A:1:1", "case:A:1", day + timedelta(days=30), "A", 0, 5.0)
    sets = build_matched_sets([case_a, case_b], [control])
    assert [item.stratum_id for item in sets] == ["case:A:1", "case:B:1"]
    assert sets[0].is_complete
    assert not sets[1].is_complete


def test_matching_diagnostics_report_incomplete_strata_and_control_reuse() -> None:
    day = date(2021, 8, 1)
    shared = day + timedelta(days=20)
    case_a = record("case:A:1", "e1", day, "A", 1, 50.0)
    case_b = record("case:A:2", "e2", day + timedelta(days=1), "A", 1, 60.0)
    case_c = record("case:C:1", "e3", day, "C", 1, 70.0)
    controls = [
        record("control:case:A:1:1", "case:A:1", shared, "A", 0, 5.0),
        record("control:case:A:2:1", "case:A:2", shared, "A", 0, 5.0),
    ]
    diagnostics = matching_diagnostics(build_matched_sets([case_a, case_b, case_c], controls))
    assert diagnostics["strata"] == 3
    assert diagnostics["strata_without_controls"] == 1
    assert diagnostics["control_rows"] == 2
    assert diagnostics["distinct_control_district_days"] == 1
    assert diagnostics["duplicate_control_rows"] == 1
    assert diagnostics["max_control_reuse"] == 2
    assert diagnostics["controls_per_case_distribution"] == {"0": 1, "1": 2}


def test_strict_matched_sets_use_each_control_day_once_and_are_deterministic() -> None:
    day = date(2021, 8, 1)
    shared = day + timedelta(days=20)
    case_a = record("case:A:1", "e1", day, "A", 1, 50.0)
    case_b = record("case:A:2", "e2", day + timedelta(days=1), "A", 1, 60.0)
    lonely = record("case:B:1", "e3", day, "B", 1, 70.0)
    controls = [
        record("control:case:A:1:1", "case:A:1", shared, "A", 0, 5.0),
        record("control:case:A:2:1", "case:A:2", shared, "A", 0, 5.0),
    ]
    sets = build_matched_sets([case_a, case_b, lonely], controls)
    first = strict_matched_sets(sets, seed=7)
    second = strict_matched_sets(sets, seed=7)
    assert [item.stratum_id for item in first] == [item.stratum_id for item in second]
    used = [
        (control.district, control.event_date) for item in first for control in item.controls
    ]
    assert len(used) == len(set(used))
    # The case with no eligible control at all is dropped from the strict sample.
    assert "case:B:1" not in {item.stratum_id for item in first}


def test_within_stratum_concordance_counts_ties_as_half() -> None:
    day = date(2021, 8, 1)
    case = record("case:A:1", "e1", day, "A", 1, 10.0)
    controls = [
        record("control:case:A:1:1", "case:A:1", day + timedelta(days=20), "A", 0, 5.0),
        record("control:case:A:1:2", "case:A:1", day + timedelta(days=21), "A", 0, 10.0),
        record("control:case:A:1:3", "case:A:1", day + timedelta(days=22), "A", 0, 15.0),
    ]
    sets = build_matched_sets([case], controls)
    value, pairs = within_stratum_concordance(sets, lambda item: item.values[5])
    assert pairs == 3
    assert value == pytest.approx((1.0 + 0.5 + 0.0) / 3)


def test_within_stratum_concordance_ignores_cases_without_controls() -> None:
    day = date(2021, 8, 1)
    case = record("case:A:1", "e1", day, "A", 1, 10.0)
    sets = build_matched_sets([case], [])
    value, pairs = within_stratum_concordance(sets, lambda item: item.values[5])
    assert pairs == 0
    assert math.isnan(value)


def test_conditional_logistic_recovers_a_null_effect() -> None:
    """With cases and controls drawn from the same values, beta must be ~0."""

    day = date(2020, 7, 1)
    cases = []
    controls = []
    for index in range(60):
        district = f"D{index % 5}"
        case_id = f"case:{district}:{index}"
        cases.append(record(case_id, "e", day + timedelta(days=index), district, 1, 20.0))
        for control_index in range(4):
            controls.append(
                record(
                    f"control:{case_id}:{control_index}",
                    case_id,
                    day + timedelta(days=200 + index * 4 + control_index),
                    district,
                    0,
                    20.0,
                )
            )
    fit = conditional_logistic(
        build_matched_sets(cases, controls),
        [("r5", lambda item: item.values[5])],
        scale=10.0,
    )
    assert fit is None or fit.coefficients[0] == pytest.approx(0.0, abs=1e-6)


def test_conditional_logistic_is_positive_when_cases_are_wetter() -> None:
    sets = make_sets(count=80, controls_each=4, offset=12.0)
    fit = conditional_logistic(sets, [("r5", lambda item: item.values[5])], scale=10.0)
    assert fit is not None
    assert fit.converged
    assert fit.coefficients[0] > 0
    assert fit.odds_ratio() > 1.0
    low, high = fit.odds_ratio_interval()
    assert low <= fit.odds_ratio() <= high
    assert fit.strata == 80
    assert fit.clusters == 4


def test_conditional_logistic_matches_a_hand_computed_one_to_one_likelihood() -> None:
    """Two 1:1 strata with a unit contrast have a closed-form conditional MLE.

    For M strata each contributing ``exp(b*x_case)/(exp(b*x_case)+exp(b*x_ctrl))``
    with a constant contrast d = x_case - x_ctrl, the score is
    ``M*d/(1+exp(b*d))`` which is strictly positive for every finite b, so the
    likelihood is monotone and the fit must diverge rather than converge to an
    interior maximum.  The estimator must not silently report a finite optimum.
    """

    day = date(2020, 7, 1)
    cases = [
        record("case:A:1", "e1", day, "A", 1, 11.0),
        record("case:B:1", "e2", day, "B", 1, 11.0),
    ]
    controls = [
        record("control:case:A:1:1", "case:A:1", day + timedelta(days=30), "A", 0, 10.0),
        record("control:case:B:1:1", "case:B:1", day + timedelta(days=30), "B", 0, 10.0),
    ]
    fit = conditional_logistic(
        build_matched_sets(cases, controls), [("r5", lambda item: item.values[5])]
    )
    assert fit is not None
    assert not fit.converged
    assert fit.diagnostics["separated"] is True
    assert fit.coefficients[0] > 5.0


def test_conditional_logistic_returns_none_without_complete_strata() -> None:
    day = date(2020, 7, 1)
    sets = build_matched_sets([record("case:A:1", "e1", day, "A", 1, 10.0)], [])
    assert conditional_logistic(sets, [("r5", lambda item: item.values[5])]) is None


def test_wald_z_is_reported_when_the_p_value_underflows() -> None:
    sets = make_sets(count=200, controls_each=5, offset=40.0)
    fit = conditional_logistic(sets, [("r5", lambda item: item.values[5])], scale=10.0)
    assert fit is not None
    assert math.isfinite(fit.wald_z())
    assert 0.0 <= fit.wald_p_value() <= 1.0


def test_conditional_logistic_reproduces_the_matched_pair_odds_ratio() -> None:
    """For 1:1 matched pairs with a binary exposure the conditional MLE is b/c.

    This is the McNemar result: concordant pairs contribute nothing to the
    conditional likelihood, and the maximum-likelihood odds ratio equals the
    ratio of the two discordant-pair counts.  Checking against that closed form
    validates the Newton-Raphson implementation against an external reference
    rather than against itself.
    """

    day = date(2020, 7, 1)
    cases: list[RainRecord] = []
    controls: list[RainRecord] = []
    counts = {"case_only": 30, "control_only": 10, "both": 12, "neither": 15}
    index = 0
    for kind, total in counts.items():
        for _ in range(total):
            district = f"D{index % 6}"
            case_id = f"case:{district}:{index}"
            case_value = 1.0 if kind in ("case_only", "both") else 0.0
            control_value = 1.0 if kind in ("control_only", "both") else 0.0
            cases.append(
                record(case_id, "e", day + timedelta(days=index), district, 1, case_value)
            )
            controls.append(
                record(
                    f"control:{case_id}:1",
                    case_id,
                    day + timedelta(days=index + 500),
                    district,
                    0,
                    control_value,
                )
            )
            index += 1
    fit = conditional_logistic(
        build_matched_sets(cases, controls), [("x", lambda item: item.values[5])]
    )
    assert fit is not None
    assert fit.converged
    expected = math.log(counts["case_only"] / counts["control_only"])
    assert fit.coefficients[0] == pytest.approx(expected, abs=1e-8)
    assert fit.odds_ratio() == pytest.approx(3.0, rel=1e-8)


def test_conditional_logistic_model_and_robust_errors_agree_under_independence() -> None:
    """With one stratum per cluster the sandwich should track the model error.

    A large discrepancy would indicate the cluster accumulation is wrong rather
    than that the data are correlated.
    """

    day = date(2020, 7, 1)
    cases: list[RainRecord] = []
    controls: list[RainRecord] = []
    for index in range(150):
        district = f"D{index}"
        case_id = f"case:{district}:1"
        # Every fourth case is drier than its own controls, so the exposure does
        # not separate cases from controls and the likelihood has a maximum.
        case_value = 34.0 if index % 4 == 0 else 44.0 + index % 5
        cases.append(record(case_id, "e", day + timedelta(days=index), district, 1, case_value))
        for control_index in range(3):
            controls.append(
                record(
                    f"control:{case_id}:{control_index}",
                    case_id,
                    day + timedelta(days=index + 400 + control_index),
                    district,
                    0,
                    38.0 + (index + control_index) % 5,
                )
            )
    fit = conditional_logistic(
        build_matched_sets(cases, controls), [("r5", lambda item: item.values[5])]
    )
    assert fit is not None
    ratio = fit.robust_standard_errors[0] / fit.model_standard_errors[0]
    assert 0.5 < ratio < 2.0
