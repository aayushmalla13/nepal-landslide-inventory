"""End-to-end media-event versus daily-rainfall analysis stage.

Analysis roles are explicit and fixed before the temporal test set is touched:

``primary``
    Matched district-day case-control comparison of *concurrent* rainfall
    accumulations (windows ending on and including the reported event day),
    restricted to ``conf_date >= min_date_confidence`` with explicitly
    earthquake- and anthropogenic-triggered events removed.  The window is
    chosen by development AUC and evaluated once, without retuning, from
    ``development_end + 1`` onward.

``co-primary``
    The identical comparison using *strictly antecedent* accumulations that end
    the day before the reported event.  CHIRPS reports a 24-hour total and
    media-derived event dates carry no time of day, so an event-day-inclusive
    window can contain rain that fell after the failure.  The strictly
    antecedent result is therefore the quantity that bounds what could be known
    beforehand, and it is reported next to the primary result rather than buried
    in a sensitivity table.

``secondary``
    Conditional (within-matched-set) association, leave-one-year-out and
    spatial validation, season stratification, and the district-month aggregate
    correlation.

``sensitivity``
    Prespecified variants of the case definition, including a balanced panel of
    continuously reporting publishers and a strictly matched control sample.

Absolute risk, probability calibration and decision-curve net benefit are
deliberately not produced.  In a 1:M matched case-control sample drawn from an
inventory with unknown and time-varying detection probability, the baseline rate
is not identifiable, so those quantities would have no referent.
"""

from __future__ import annotations

import csv
import hashlib
import json
import logging
import math
import statistics
from calendar import monthrange
from collections import Counter, defaultdict
from collections.abc import Callable, Sequence
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from ..config import AppConfig
from .matched import (
    MatchedSet,
    bootstrap_concordance_interval,
    build_matched_sets,
    conditional_logistic,
    matching_diagnostics,
    strict_matched_sets,
    within_stratum_concordance,
)
from .rainfall import (
    Event,
    RainRecord,
    auc,
    balanced_panel_sources,
    binary_metrics,
    bootstrap_metric_intervals,
    bootstrap_threshold_interval,
    build_cases,
    build_matched_controls,
    normalize_district,
    percentile,
    rainfall_quality,
    read_daily_rainfall,
    read_events,
    roc_curve,
    round_output,
    spearman,
    youden_threshold,
)
from .validation import leave_one_year_out, spatial_holdout, summarize_folds

LOGGER = logging.getLogger(__name__)

PRIMARY_VARIANT = "primary_conf_ge_0.78"
CONCURRENT = "concurrent_incl_event_day"
ANTECEDENT = "strictly_antecedent_excl_event_day"
EXPOSURES = (CONCURRENT, ANTECEDENT)
MONSOON_MONTHS = frozenset({6, 7, 8, 9})
ODDS_RATIO_SCALE_MM = 10.0
BALANCED_PANEL_MIN_EVENTS = 30
SPATIAL_FOLDS = 5


def _resolve(config: AppConfig, value: str) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return (config.config_path.parent / path).resolve()


def _relative(root: Path, path: Path) -> str:
    """Record repository-relative paths so a release is not machine-specific."""

    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.name


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _expected_districts(config: AppConfig) -> list[str]:
    path = config.config_path.parent / "resources" / "districts_en.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        return [row["district"] for row in csv.DictReader(handle)]


def _district_provinces(config: AppConfig) -> dict[str, str]:
    path = config.config_path.parent / "resources" / "districts_en.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        return {
            normalize_district(row["district"]): (row.get("province") or "").strip()
            for row in csv.DictReader(handle)
        }


def _json_value(value: Any) -> Any:
    if isinstance(value, float):
        return None if not math.isfinite(value) else round_output(value)
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_json_value(item) for item in value]
    return value


def _csv_value(value: Any) -> Any:
    if isinstance(value, float):
        return "" if not math.isfinite(value) else round_output(value)
    return value


def _write_rows(path: Path, rows: Sequence[dict[str, object]], columns: Sequence[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_value(row.get(key)) for key in columns})


def _exposure_getter(exposure: str, window: int) -> Callable[[RainRecord], float]:
    """Return the accessor for one exposure definition and accumulation length."""

    if exposure == CONCURRENT:
        return lambda record: record.values[window]
    return lambda record: record.lagged_values[window]


def _has_exposure(records: Sequence[RainRecord], exposure: str, window: int) -> bool:
    getter = _exposure_getter(exposure, window)
    try:
        for record in records:
            getter(record)
    except KeyError:
        return False
    return True


def _write_records(path: Path, records: Sequence[RainRecord], windows: Sequence[int]) -> None:
    columns = [
        "record_id",
        "matched_event_id",
        "date",
        "district",
        "label",
        "conf_date",
        "case_event_count",
    ]
    columns.extend(f"r{window}_mm" for window in windows)
    columns.extend(f"r{window}_lag1_mm" for window in windows)
    rows: list[dict[str, object]] = []
    for record in records:
        row: dict[str, object] = {
            "record_id": record.record_id,
            "matched_event_id": record.matched_event_id,
            "date": record.event_date.isoformat(),
            "district": record.district,
            "label": record.label,
            "conf_date": record.confidence,
            "case_event_count": record.case_event_count,
        }
        row.update({f"r{window}_mm": record.values[window] for window in windows})
        row.update(
            {f"r{window}_lag1_mm": record.lagged_values.get(window, "") for window in windows}
        )
        rows.append(row)
    _write_rows(path, rows, columns)


def _evaluate_variant(
    name: str,
    cases: Sequence[RainRecord],
    controls: Sequence[RainRecord],
    windows: Sequence[int],
    train_end: date,
    bootstrap_iterations: int,
    seed: int,
) -> list[dict[str, object]]:
    """Score one case definition under both exposure definitions.

    The threshold is always fitted in the development split and applied
    unchanged to the temporal test split.  Bootstrap intervals are spent only
    where they carry inferential weight -- the untouched test split of the
    primary variant -- so the run stays tractable.
    """

    rows: list[dict[str, object]] = []
    records = list(cases) + list(controls)
    train = [record for record in records if record.event_date <= train_end]
    test = [record for record in records if record.event_date > train_end]
    for exposure_index, exposure in enumerate(EXPOSURES):
        for window in windows:
            if not _has_exposure(records, exposure, window):
                continue
            getter = _exposure_getter(exposure, window)
            train_labels = [record.label for record in train]
            train_scores = [getter(record) for record in train]
            if len(set(train_labels)) < 2:
                continue
            threshold = youden_threshold(train_labels, train_scores)
            is_primary = name == PRIMARY_VARIANT
            threshold_interval = (
                bootstrap_threshold_interval(
                    train,
                    window,
                    iterations=bootstrap_iterations,
                    seed=seed + window + exposure_index * 1_000,
                    value_of=getter,
                )
                if is_primary
                else None
            )
            case_scores = [getter(record) for record in train if record.label == 1]
            control_scores = [getter(record) for record in train if record.label == 0]
            for split, sample in (("development", train), ("temporal_test", test)):
                labels = [record.label for record in sample]
                scores = [getter(record) for record in sample]
                if len(set(labels)) < 2:
                    continue
                metrics = binary_metrics(labels, scores, threshold)
                metrics["auc"] = auc(labels, scores)
                interval_iterations = (
                    bootstrap_iterations if is_primary and split == "temporal_test" else 0
                )
                intervals = bootstrap_metric_intervals(
                    sample,
                    window,
                    threshold,
                    iterations=interval_iterations,
                    seed=seed
                    + window
                    + exposure_index * 1_000
                    + (0 if split == "development" else 10_000),
                    value_of=getter,
                )
                row: dict[str, object] = {
                    "variant": name,
                    "exposure": exposure,
                    "split": split,
                    "window_days": window,
                    "threshold_mm": threshold,
                    "threshold_fitted_on": "development",
                    "threshold_ci_low": threshold_interval[0] if threshold_interval else None,
                    "threshold_ci_high": threshold_interval[1] if threshold_interval else None,
                    "threshold_ci_split": "development" if threshold_interval else "",
                    "train_case_p10_mm": percentile(case_scores, 0.10),
                    "train_case_p50_mm": percentile(case_scores, 0.50),
                    "train_control_p90_mm": percentile(control_scores, 0.90),
                    "n_cases": sum(record.label == 1 for record in sample),
                    "n_controls": sum(record.label == 0 for record in sample),
                    **metrics,
                }
                for metric, bounds in intervals.items():
                    row[f"{metric}_ci_low"] = bounds[0]
                    row[f"{metric}_ci_high"] = bounds[1]
                rows.append(row)
    return rows


METRIC_COLUMNS = [
    "variant",
    "exposure",
    "split",
    "window_days",
    "threshold_mm",
    "threshold_fitted_on",
    "threshold_ci_low",
    "threshold_ci_high",
    "threshold_ci_split",
    "train_case_p10_mm",
    "train_case_p50_mm",
    "train_control_p90_mm",
    "n_cases",
    "n_controls",
    "auc",
    "auc_ci_low",
    "auc_ci_high",
    "sensitivity",
    "sensitivity_ci_low",
    "sensitivity_ci_high",
    "specificity",
    "specificity_ci_low",
    "specificity_ci_high",
    "precision",
    "precision_ci_low",
    "precision_ci_high",
    "balanced_accuracy",
    "balanced_accuracy_ci_low",
    "balanced_accuracy_ci_high",
    "tp",
    "fp",
    "tn",
    "fn",
]


def _select_development_window(
    rows: Sequence[dict[str, object]], variant: str, exposure: str
) -> dict[str, object] | None:
    """Pick the window with the highest development AUC.

    Ties are broken toward the shorter window so the choice is deterministic and
    never depends on iteration order; the primary 3-day and 5-day development
    AUCs differ by only 0.0003, so the rule has to be stated explicitly.
    """

    development = [
        row
        for row in rows
        if row["variant"] == variant
        and row["exposure"] == exposure
        and row["split"] == "development"
    ]
    if not development:
        return None
    return max(development, key=lambda row: (float(row["auc"]), -int(row["window_days"])))


def _test_row(
    rows: Sequence[dict[str, object]], variant: str, exposure: str, window: object
) -> dict[str, object] | None:
    return next(
        (
            row
            for row in rows
            if row["variant"] == variant
            and row["exposure"] == exposure
            and row["split"] == "temporal_test"
            and row["window_days"] == window
        ),
        None,
    )


def _write_sensitivity_summary(
    path: Path, rows: Sequence[dict[str, object]]
) -> list[dict[str, object]]:
    """Summarize the development-selected window for every variant and exposure."""

    summaries: list[dict[str, object]] = []
    variants = list(dict.fromkeys(str(row["variant"]) for row in rows))
    for variant in variants:
        for exposure in EXPOSURES:
            selected = _select_development_window(rows, variant, exposure)
            if selected is None:
                continue
            test = _test_row(rows, variant, exposure, selected["window_days"])
            if test is None:
                continue
            summaries.append(
                {
                    "variant": variant,
                    "exposure": exposure,
                    "selected_window_days": selected["window_days"],
                    "threshold_mm": test["threshold_mm"],
                    "threshold_ci_low": test.get("threshold_ci_low"),
                    "threshold_ci_high": test.get("threshold_ci_high"),
                    "development_auc": selected["auc"],
                    "test_cases": test["n_cases"],
                    "test_controls": test["n_controls"],
                    "test_auc": test["auc"],
                    "test_auc_ci_low": test.get("auc_ci_low"),
                    "test_auc_ci_high": test.get("auc_ci_high"),
                    "test_sensitivity": test["sensitivity"],
                    "test_specificity": test["specificity"],
                    "test_balanced_accuracy": test["balanced_accuracy"],
                    "test_minus_development_auc": float(test["auc"]) - float(selected["auc"]),
                }
            )
    columns = list(summaries[0]) if summaries else ["variant"]
    _write_rows(path, summaries, columns)
    return summaries


def _write_primary_test_roc(
    path: Path,
    cases: Sequence[RainRecord],
    controls: Sequence[RainRecord],
    windows: Sequence[int],
    train_end: date,
) -> None:
    test = [record for record in [*cases, *controls] if record.event_date > train_end]
    columns = [
        "exposure",
        "window_days",
        "threshold_mm",
        "false_positive_rate",
        "true_positive_rate",
    ]
    rows: list[dict[str, object]] = []
    for exposure in EXPOSURES:
        for window in windows:
            if not _has_exposure(test, exposure, window):
                continue
            getter = _exposure_getter(exposure, window)
            labels = [record.label for record in test]
            scores = [getter(record) for record in test]
            for threshold, false_positive_rate, true_positive_rate in roc_curve(labels, scores):
                rows.append(
                    {
                        "exposure": exposure,
                        "window_days": window,
                        "threshold_mm": "inf" if math.isinf(threshold) else threshold,
                        "false_positive_rate": false_positive_rate,
                        "true_positive_rate": true_positive_rate,
                    }
                )
    _write_rows(path, rows, columns)


def _conditional_models(
    path: Path,
    sets: Sequence[MatchedSet],
    windows: Sequence[int],
    train_end: date,
    bootstrap_iterations: int,
    seed: int,
) -> list[dict[str, object]]:
    """Fit the design-faithful within-matched-set association.

    Conditional logistic regression conditions the stratum intercepts away, so
    district, calendar month and year -- the matching variables -- are removed by
    construction rather than by adjustment.  Standard errors are clustered on
    district, matching the bootstrap used for the threshold metrics.  The odds
    ratio is reported per 10 mm; no absolute risk is reported because a matched
    case-control sample cannot identify one.
    """

    rows: list[dict[str, object]] = []
    splits: list[tuple[str, Sequence[MatchedSet]]] = [
        ("all_years", list(sets)),
        ("development", [item for item in sets if item.case.event_date <= train_end]),
        ("temporal_test", [item for item in sets if item.case.event_date > train_end]),
    ]
    for split, subset in splits:
        members = [item.case for item in subset if item.is_complete]
        if not members:
            continue
        for exposure in EXPOSURES:
            for window in windows:
                if not _has_exposure(members, exposure, window):
                    continue
                getter = _exposure_getter(exposure, window)
                fit = conditional_logistic(
                    subset,
                    [(f"r{window}_{exposure}", getter)],
                    scale=ODDS_RATIO_SCALE_MM,
                )
                if fit is None:
                    continue
                concordance, pairs = within_stratum_concordance(subset, getter)
                interval = (
                    bootstrap_concordance_interval(
                        subset,
                        getter,
                        iterations=bootstrap_iterations,
                        seed=seed + window,
                    )
                    if split == "temporal_test" and bootstrap_iterations
                    else None
                )
                low, high = fit.odds_ratio_interval()
                rows.append(
                    {
                        "split": split,
                        "exposure": exposure,
                        "window_days": window,
                        "strata_used": fit.strata,
                        "district_clusters": fit.clusters,
                        "beta_per_mm": fit.coefficients[0],
                        "odds_ratio_per_10mm": fit.odds_ratio(),
                        "odds_ratio_ci_low": low,
                        "odds_ratio_ci_high": high,
                        "robust_se": fit.robust_standard_errors[0],
                        "model_se": fit.model_standard_errors[0],
                        "wald_z": fit.wald_z(),
                        "wald_p": fit.wald_p_value(),
                        "log_likelihood": fit.log_likelihood,
                        "converged": fit.converged,
                        "within_stratum_concordance": concordance,
                        "concordance_ci_low": interval[0] if interval else None,
                        "concordance_ci_high": interval[1] if interval else None,
                        "comparable_pairs": pairs,
                    }
                )
    columns = [
        "split",
        "exposure",
        "window_days",
        "strata_used",
        "district_clusters",
        "beta_per_mm",
        "odds_ratio_per_10mm",
        "odds_ratio_ci_low",
        "odds_ratio_ci_high",
        "robust_se",
        "model_se",
        "wald_z",
        "wald_p",
        "log_likelihood",
        "converged",
        "within_stratum_concordance",
        "concordance_ci_low",
        "concordance_ci_high",
        "comparable_pairs",
    ]
    _write_rows(path, rows, columns)
    return rows


def _resampled_validation(
    path: Path,
    records: Sequence[RainRecord],
    selected: dict[str, int],
) -> dict[str, object]:
    """Leave-one-year-out and spatially held-out refits of the cutpoint.

    A single development/test split yields one number with no indication of its
    variability.  Refitting without each year, and without each district group,
    shows the range of held-out performance the same data can produce.  These
    are reported beside the prespecified temporal holdout, never in place of it,
    and no method choice is made on the basis of them.
    """

    rows: list[dict[str, object]] = []
    summary: dict[str, object] = {}
    for exposure in EXPOSURES:
        window = selected.get(exposure)
        if window is None or not _has_exposure(records, exposure, window):
            continue
        getter = _exposure_getter(exposure, window)
        yearly = leave_one_year_out(records, getter)
        spatial = spatial_holdout(records, getter, folds=SPATIAL_FOLDS)
        for scheme, results in (("leave_one_year_out", yearly), ("spatial_holdout", spatial)):
            for result in results:
                rows.append(
                    {
                        "scheme": scheme,
                        "exposure": exposure,
                        "window_days": window,
                        **result.as_row(),
                    }
                )
            summary[f"{scheme}:{exposure}"] = {
                "window_days": window,
                **summarize_folds(results),
            }
    columns = [
        "scheme",
        "exposure",
        "window_days",
        "fold",
        "n_cases",
        "n_controls",
        "threshold_mm",
        "auc",
        "sensitivity",
        "specificity",
        "balanced_accuracy",
    ]
    _write_rows(path, rows, columns)
    return summary


def _season_stratified(
    path: Path,
    records: Sequence[RainRecord],
    windows: Sequence[int],
    train_end: date,
) -> list[dict[str, object]]:
    """Fit and evaluate separately inside and outside the summer monsoon.

    Matching on calendar month already balances season between cases and
    controls, so this is not a confounding adjustment.  It answers a different
    question: whether one national cutpoint is meaningful year-round.  It is not,
    and that has to be visible rather than hidden inside a pooled number.
    """

    rows: list[dict[str, object]] = []
    seasons = (
        ("monsoon_JJAS", lambda record: record.event_date.month in MONSOON_MONTHS),
        ("non_monsoon", lambda record: record.event_date.month not in MONSOON_MONTHS),
    )
    for season, predicate in seasons:
        subset = [record for record in records if predicate(record)]
        train = [record for record in subset if record.event_date <= train_end]
        test = [record for record in subset if record.event_date > train_end]
        for exposure in EXPOSURES:
            for window in windows:
                if not _has_exposure(subset, exposure, window):
                    continue
                getter = _exposure_getter(exposure, window)
                train_labels = [record.label for record in train]
                test_labels = [record.label for record in test]
                if len(set(train_labels)) < 2 or len(set(test_labels)) < 2:
                    continue
                train_scores = [getter(record) for record in train]
                threshold = youden_threshold(train_labels, train_scores)
                test_scores = [getter(record) for record in test]
                metrics = binary_metrics(test_labels, test_scores, threshold)
                rows.append(
                    {
                        "season": season,
                        "exposure": exposure,
                        "window_days": window,
                        "development_cases": sum(value == 1 for value in train_labels),
                        "development_controls": sum(value == 0 for value in train_labels),
                        "test_cases": sum(value == 1 for value in test_labels),
                        "test_controls": sum(value == 0 for value in test_labels),
                        "threshold_mm": threshold,
                        "development_auc": auc(train_labels, train_scores),
                        "test_auc": auc(test_labels, test_scores),
                        "test_sensitivity": metrics["sensitivity"],
                        "test_specificity": metrics["specificity"],
                    }
                )
    columns = [
        "season",
        "exposure",
        "window_days",
        "development_cases",
        "development_controls",
        "test_cases",
        "test_controls",
        "threshold_mm",
        "development_auc",
        "test_auc",
        "test_sensitivity",
        "test_specificity",
    ]
    _write_rows(path, rows, columns)
    return rows


def _monthly_association(
    path: Path,
    rainfall,
    cases: Sequence[RainRecord],
    expected_districts: Sequence[str],
) -> dict[str, object]:
    """District-month Spearman association, retained as a secondary result.

    This aggregate coefficient mixes rainfall with reporting effort and with
    zero-event district-months, so it is reported as an association only and is
    never described as a threshold or as a physical landslide trend.
    """

    rainfall_month: dict[tuple[str, int, int], float] = defaultdict(float)
    rainfall_days: Counter[tuple[str, int, int]] = Counter()
    for (district, day), value in rainfall.values.items():
        key = (district, day.year, day.month)
        rainfall_month[key] += value
        rainfall_days[key] += 1
    event_counts = Counter(
        (case.district, case.event_date.year, case.event_date.month) for case in cases
    )
    rows: list[dict[str, object]] = []
    districts = [normalize_district(item) for item in expected_districts]
    cursor = date(rainfall.start.year, rainfall.start.month, 1)
    last_month = date(rainfall.end.year, rainfall.end.month, 1)
    while cursor <= last_month:
        expected_days = monthrange(cursor.year, cursor.month)[1]
        for district in districts:
            key = (district, cursor.year, cursor.month)
            if rainfall_days[key] != expected_days:
                continue
            rows.append(
                {
                    "district": district,
                    "year": cursor.year,
                    "month": cursor.month,
                    "event_count": event_counts[key],
                    "rainfall_total_mm": rainfall_month[key],
                }
            )
        if cursor.month == 12:
            cursor = date(cursor.year + 1, 1, 1)
        else:
            cursor = date(cursor.year, cursor.month + 1, 1)
    _write_rows(path, rows, ["district", "year", "month", "event_count", "rainfall_total_mm"])
    rho = spearman(
        [float(row["event_count"]) for row in rows],
        [float(row["rainfall_total_mm"]) for row in rows],
    )
    monsoon = [row for row in rows if int(row["month"]) in MONSOON_MONTHS]
    rho_monsoon = spearman(
        [float(row["event_count"]) for row in monsoon],
        [float(row["rainfall_total_mm"]) for row in monsoon],
    )
    return {
        "rows": len(rows),
        "spearman_rho": rho,
        "monsoon_rows": len(monsoon),
        "spearman_rho_monsoon_only": rho_monsoon,
        "interpretation": (
            "Aggregate association only. Confounded by reporting effort and by "
            "zero-event district-months; not a threshold and not a landslide trend."
        ),
    }


def _reporting_composition(
    path: Path, events: Sequence[Event], train_end: date
) -> dict[str, object]:
    """Describe how the reporting instrument itself changes over the study period.

    The development and temporal-test periods are not only different times; they
    are drawn from partly different publishers.  Quantifying that turnover is a
    precondition for interpreting any temporal comparison, and it is the reason
    the balanced-panel sensitivity analysis exists.
    """

    years = sorted({event.event_date.year for event in events})
    counts: dict[tuple[str, int], int] = defaultdict(int)
    before: dict[str, int] = defaultdict(int)
    after: dict[str, int] = defaultdict(int)
    for event in events:
        source = event.source or "unknown"
        counts[(source, event.event_date.year)] += 1
        (before if event.event_date <= train_end else after)[source] += 1
    sources = sorted({event.source or "unknown" for event in events})
    rows = [
        {
            "source": source,
            "development_events": before[source],
            "temporal_test_events": after[source],
            "development_only": before[source] > 0 and after[source] == 0,
            "temporal_test_only": after[source] > 0 and before[source] == 0,
            **{str(year): counts[(source, year)] for year in years},
        }
        for source in sources
    ]
    columns = [
        "source",
        "development_events",
        "temporal_test_events",
        "development_only",
        "temporal_test_only",
        *[str(year) for year in years],
    ]
    _write_rows(path, rows, columns)
    development_total = sum(before.values())
    test_total = sum(after.values())
    dropped = sum(before[name] for name in sources if before[name] > 0 and after[name] == 0)
    added = sum(after[name] for name in sources if after[name] > 0 and before[name] == 0)
    return {
        "sources": len(sources),
        "development_events": development_total,
        "temporal_test_events": test_total,
        "sources_absent_from_temporal_test": sorted(
            name for name in sources if before[name] > 0 and after[name] == 0
        ),
        "sources_absent_from_development": sorted(
            name for name in sources if after[name] > 0 and before[name] == 0
        ),
        "development_events_from_discontinued_sources_fraction": (
            dropped / development_total if development_total else 0.0
        ),
        "temporal_test_events_from_new_sources_fraction": (
            added / test_total if test_total else 0.0
        ),
        "interpretation": (
            "The development/temporal-test contrast is confounded with publisher "
            "turnover. Compare against the balanced_source_panel variant before "
            "attributing any difference to time."
        ),
    }


def _descriptive_summary(
    output_dir: Path,
    events: Sequence[Event],
    cases: Sequence[RainRecord],
    controls: Sequence[RainRecord],
    provinces: dict[str, str],
    windows: Sequence[int],
    train_end: date,
) -> dict[str, object]:
    """Write district, province, month and case/control distribution summaries."""

    by_district: dict[str, list[Event]] = defaultdict(list)
    for event in events:
        by_district[event.district].append(event)
    case_by_district: Counter[str] = Counter(case.district for case in cases)
    district_rows: list[dict[str, object]] = []
    for district in sorted(set(provinces) | set(by_district)):
        members = by_district.get(district, [])
        district_rows.append(
            {
                "district": district,
                "province": provinces.get(district, ""),
                "canonical_events": len(members),
                "primary_case_days": case_by_district.get(district, 0),
                "road_obstruction_events": sum(
                    1 for item in members if item.event_type == "road_obstruction"
                ),
                "rainfall_trigger_events": sum(
                    1 for item in members if item.trigger == "rainfall"
                ),
                "earthquake_trigger_events": sum(
                    1 for item in members if item.trigger == "earthquake"
                ),
                "anthropogenic_trigger_events": sum(
                    1 for item in members if item.trigger == "anthropogenic"
                ),
                "unknown_trigger_events": sum(1 for item in members if item.trigger == "unknown"),
                "distinct_sources": len({item.source for item in members if item.source}),
                "first_event": min((item.event_date for item in members), default=None),
                "last_event": max((item.event_date for item in members), default=None),
            }
        )
    _write_rows(
        output_dir / "inventory_district_summary.csv",
        [
            {
                **row,
                "first_event": row["first_event"].isoformat() if row["first_event"] else "",
                "last_event": row["last_event"].isoformat() if row["last_event"] else "",
            }
            for row in district_rows
        ],
        [
            "district",
            "province",
            "canonical_events",
            "primary_case_days",
            "road_obstruction_events",
            "rainfall_trigger_events",
            "earthquake_trigger_events",
            "anthropogenic_trigger_events",
            "unknown_trigger_events",
            "distinct_sources",
            "first_event",
            "last_event",
        ],
    )

    province_totals: dict[str, Counter[str]] = defaultdict(Counter)
    for row in district_rows:
        province = str(row["province"]) or "unknown"
        province_totals[province]["districts"] += 1
        province_totals[province]["canonical_events"] += int(row["canonical_events"])
        province_totals[province]["primary_case_days"] += int(row["primary_case_days"])
        province_totals[province]["road_obstruction_events"] += int(row["road_obstruction_events"])
    _write_rows(
        output_dir / "inventory_province_summary.csv",
        [
            {"province": province, **dict(values)}
            for province, values in sorted(province_totals.items())
        ],
        [
            "province",
            "districts",
            "canonical_events",
            "primary_case_days",
            "road_obstruction_events",
        ],
    )

    month_rows: list[dict[str, object]] = []
    for month in range(1, 13):
        members = [item for item in events if item.event_date.month == month]
        month_rows.append(
            {
                "month": month,
                "monsoon": month in MONSOON_MONTHS,
                "canonical_events": len(members),
                "share_of_events": len(members) / len(events) if events else 0.0,
                "primary_case_days": sum(1 for case in cases if case.event_date.month == month),
                "road_obstruction_events": sum(
                    1 for item in members if item.event_type == "road_obstruction"
                ),
            }
        )
    _write_rows(
        output_dir / "inventory_month_summary.csv",
        month_rows,
        [
            "month",
            "monsoon",
            "canonical_events",
            "share_of_events",
            "primary_case_days",
            "road_obstruction_events",
        ],
    )

    # Split by period as well as overall: the development and temporal-test
    # case-days sit in district-months with different baseline wetness, which is
    # the observable explanation for the test period discriminating more sharply.
    periods: list[tuple[str, Callable[[RainRecord], bool]]] = [
        ("all_years", lambda record: True),
        ("development", lambda record: record.event_date <= train_end),
        ("temporal_test", lambda record: record.event_date > train_end),
    ]
    distribution_rows: list[dict[str, object]] = []
    for period, in_period in periods:
        for exposure in EXPOSURES:
            for window in windows:
                for group_name, group in (("case", cases), ("control", controls)):
                    members = [record for record in group if in_period(record)]
                    if not members or not _has_exposure(members, exposure, window):
                        continue
                    getter = _exposure_getter(exposure, window)
                    values = sorted(getter(record) for record in members)
                    distribution_rows.append(
                        {
                            "period": period,
                            "exposure": exposure,
                            "window_days": window,
                            "group": group_name,
                            "n": len(values),
                            "zero_rain_fraction": sum(1 for value in values if value == 0.0)
                            / len(values),
                            "p10_mm": percentile(values, 0.10),
                            "p25_mm": percentile(values, 0.25),
                            "median_mm": percentile(values, 0.50),
                            "p75_mm": percentile(values, 0.75),
                            "p90_mm": percentile(values, 0.90),
                            "mean_mm": statistics.fmean(values),
                            "max_mm": values[-1],
                        }
                    )
    _write_rows(
        output_dir / "rainfall_case_control_distributions.csv",
        distribution_rows,
        [
            "period",
            "exposure",
            "window_days",
            "group",
            "n",
            "zero_rain_fraction",
            "p10_mm",
            "p25_mm",
            "median_mm",
            "p75_mm",
            "p90_mm",
            "mean_mm",
            "max_mm",
        ],
    )

    district_days = {(item.district, item.event_date) for item in events}
    return {
        "districts_with_events": sum(1 for row in district_rows if row["canonical_events"]),
        "provinces_with_events": sum(
            1 for values in province_totals.values() if values["canonical_events"]
        ),
        "monsoon_event_share": (
            sum(1 for item in events if item.event_date.month in MONSOON_MONTHS) / len(events)
            if events
            else 0.0
        ),
        "canonical_events": len(events),
        "distinct_district_days_in_inventory": len(district_days),
        "events_sharing_a_district_day": len(events) - len(district_days),
        "district_day_collapse_note": (
            "Canonical records are deduplicated report clusters, not verified "
            "distinct physical failures. Records sharing a district-day are "
            "collapsed to one case-day in the rainfall analysis."
        ),
    }


def run_rainfall_analysis_stage(config: AppConfig) -> None:
    """Run daily antecedent-rainfall threshold analysis and write auditable outputs."""

    root = config.config_path.parent
    settings = dict(config.raw.get("analysis", {}))
    daily_path = _resolve(
        config,
        str(settings.get("chirps_daily_district_path", "data/external/chirps_daily_districts.csv")),
    )
    canonical_path = _resolve(
        config,
        str(settings.get("canonical_events_path", "data/outputs/canonical_events_final.csv")),
    )
    output_dir = config.resolve_path("outputs_dir")
    output_dir.mkdir(parents=True, exist_ok=True)
    windows = tuple(int(value) for value in settings.get("antecedent_windows_days", [1, 3, 5, 7]))
    min_confidence = float(settings.get("min_date_confidence", 0.78))
    high_confidence = float(settings.get("high_date_confidence", 0.80))
    very_high_confidence = float(settings.get("very_high_date_confidence", 0.90))
    controls_per_event = int(settings.get("controls_per_event", 5))
    exclusion_buffer = int(settings.get("control_exclusion_buffer_days", 7))
    seed = int(settings.get("random_seed", 20260813))
    bootstrap_iterations = int(settings.get("bootstrap_iterations", 1000))
    train_end = date.fromisoformat(str(settings.get("development_end", "2022-12-31")))
    panel_minimum = int(settings.get("balanced_panel_min_events", BALANCED_PANEL_MIN_EVENTS))

    rainfall = read_daily_rainfall(daily_path)
    events = read_events(canonical_path)
    expected_districts = _expected_districts(config)
    provinces = _district_provinces(config)
    quality = rainfall_quality(rainfall, expected_districts)
    if quality["missing_districts"] or quality["unexpected_districts"]:
        raise ValueError(
            "Rainfall districts do not match the canonical 77-district vocabulary: "
            f"missing={quality['missing_districts']} unexpected={quality['unexpected_districts']}"
        )

    non_rainfall_triggers = frozenset({"earthquake", "anthropogenic"})
    panel = balanced_panel_sources(events, train_end, minimum_per_period=panel_minimum)
    variants: list[
        tuple[str, float, int, frozenset[str], frozenset[str], frozenset[str] | None]
    ] = [
        (PRIMARY_VARIANT, min_confidence, 0, non_rainfall_triggers, frozenset(), None),
        ("all_dated_events", 0.0, 0, non_rainfall_triggers, frozenset(), None),
        ("high_conf_ge_0.80", high_confidence, 0, non_rainfall_triggers, frozenset(), None),
        (
            "very_high_conf_ge_0.90",
            very_high_confidence,
            0,
            non_rainfall_triggers,
            frozenset(),
            None,
        ),
        ("primary_date_minus_1d", min_confidence, -1, non_rainfall_triggers, frozenset(), None),
        ("primary_date_plus_1d", min_confidence, 1, non_rainfall_triggers, frozenset(), None),
        ("primary_date_minus_3d", min_confidence, -3, non_rainfall_triggers, frozenset(), None),
        ("primary_date_plus_3d", min_confidence, 3, non_rainfall_triggers, frozenset(), None),
        ("include_known_nonrain_triggers", min_confidence, 0, frozenset(), frozenset(), None),
        (
            "exclude_road_obstructions",
            min_confidence,
            0,
            non_rainfall_triggers,
            frozenset({"road_obstruction"}),
            None,
        ),
        (
            "balanced_source_panel",
            min_confidence,
            0,
            non_rainfall_triggers,
            frozenset(),
            frozenset(panel),
        ),
    ]
    all_metrics: list[dict[str, object]] = []
    variant_summary: dict[str, object] = {}
    primary_cases: list[RainRecord] = []
    primary_controls: list[RainRecord] = []
    for index, (name, confidence, shift, excluded_triggers, excluded_types, sources) in enumerate(
        variants
    ):
        cases = build_cases(
            events,
            rainfall,
            windows,
            confidence,
            shift,
            excluded_triggers,
            excluded_types,
            sources,
        )
        controls = build_matched_controls(
            cases,
            events,
            rainfall,
            windows,
            controls_per_event,
            exclusion_buffer,
            seed + index,
        )
        metrics = _evaluate_variant(
            name,
            cases,
            controls,
            windows,
            train_end,
            bootstrap_iterations,
            seed + index * 100,
        )
        all_metrics.extend(metrics)
        variant_summary[name] = {
            "cases": len(cases),
            "controls": len(controls),
            "date_shift_days": shift,
            "minimum_date_confidence": confidence,
            "excluded_triggers": sorted(excluded_triggers),
            "excluded_event_types": sorted(excluded_types),
            "included_sources": sorted(sources) if sources is not None else "all",
        }
        if index == 0:
            primary_cases = cases
            primary_controls = controls

    primary_records = [*primary_cases, *primary_controls]
    matched_sets = build_matched_sets(primary_cases, primary_controls)
    diagnostics = matching_diagnostics(matched_sets)

    strict_sets = strict_matched_sets(matched_sets, seed=seed + 999)
    strict_cases = [item.case for item in strict_sets]
    strict_controls = [control for item in strict_sets for control in item.controls]
    all_metrics.extend(
        _evaluate_variant(
            "strict_matched_sets",
            strict_cases,
            strict_controls,
            windows,
            train_end,
            0,
            seed + 900,
        )
    )
    variant_summary["strict_matched_sets"] = {
        "cases": len(strict_cases),
        "controls": len(strict_controls),
        "date_shift_days": 0,
        "minimum_date_confidence": min_confidence,
        "excluded_triggers": sorted(non_rainfall_triggers),
        "excluded_event_types": [],
        "included_sources": "all",
        "note": "complete matched sets only; each control district-day used at most once",
    }

    _write_records(output_dir / "event_antecedent_rainfall.csv", primary_cases, windows)
    _write_records(output_dir / "rainfall_controls.csv", primary_controls, windows)
    _write_rows(output_dir / "rainfall_threshold_metrics.csv", all_metrics, METRIC_COLUMNS)
    sensitivity_summary = _write_sensitivity_summary(
        output_dir / "rainfall_sensitivity_summary.csv", all_metrics
    )
    _write_primary_test_roc(
        output_dir / "rainfall_primary_test_roc.csv",
        primary_cases,
        primary_controls,
        windows,
        train_end,
    )
    conditional_rows = _conditional_models(
        output_dir / "rainfall_conditional_models.csv",
        matched_sets,
        windows,
        train_end,
        bootstrap_iterations,
        seed + 500,
    )
    selected_windows: dict[str, int] = {}
    primary_selected: dict[str, object] = {}
    for exposure in EXPOSURES:
        chosen = _select_development_window(all_metrics, PRIMARY_VARIANT, exposure)
        if chosen is None:
            continue
        selected_windows[exposure] = int(chosen["window_days"])
        test = _test_row(all_metrics, PRIMARY_VARIANT, exposure, chosen["window_days"])
        primary_selected[exposure] = {
            "development": chosen,
            "temporal_test": test,
            "test_minus_development_auc": (
                float(test["auc"]) - float(chosen["auc"]) if test else None
            ),
        }
    resampled = _resampled_validation(
        output_dir / "rainfall_resampled_validation.csv",
        primary_records,
        selected_windows,
    )
    season_rows = _season_stratified(
        output_dir / "rainfall_season_stratified.csv",
        primary_records,
        windows,
        train_end,
    )
    composition = _reporting_composition(
        output_dir / "inventory_reporting_composition.csv", events, train_end
    )
    descriptive = _descriptive_summary(
        output_dir, events, primary_cases, primary_controls, provinces, windows, train_end
    )
    monthly = _monthly_association(
        output_dir / "district_month_rainfall_association.csv",
        rainfall,
        primary_cases,
        expected_districts,
    )
    (output_dir / "rainfall_daily_quality.json").write_text(
        json.dumps(_json_value(quality), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "rainfall_matching_diagnostics.json").write_text(
        json.dumps(_json_value(diagnostics), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    primary_eligible_events = [
        event
        for event in events
        if event.confidence >= min_confidence and event.trigger not in non_rainfall_triggers
    ]
    primary_after_rainfall = [
        event for event in primary_eligible_events if event.event_date > rainfall.end
    ]
    concurrent_entry = primary_selected.get(CONCURRENT) or {}
    selected_development = concurrent_entry.get("development")
    selected_test = concurrent_entry.get("temporal_test")

    report = {
        "study_design": "district-day matched case-control with temporal holdout",
        "analysis_roles": {
            "primary": (
                "concurrent accumulation including the reported event day, "
                f"variant {PRIMARY_VARIANT}, window chosen by development AUC"
            ),
            "co_primary": (
                "strictly antecedent accumulation ending the day before the "
                "reported event; bounds what could be known before failure"
            ),
            "secondary": (
                "conditional within-matched-set association, leave-one-year-out "
                "and spatial validation, season stratification, district-month "
                "aggregate correlation"
            ),
            "sensitivity": (
                "date confidence, date shifts, trigger inclusion, road "
                "obstructions, balanced source panel, strict matched sets"
            ),
            "not_reported": (
                "absolute risk, probability calibration and decision-curve net "
                "benefit are not identifiable from a matched case-control sample "
                "drawn from an inventory with unknown detection probability"
            ),
        },
        "rainfall_product": settings.get("rainfall_product", "UCSB CHIRPS v2.0 Final"),
        "rainfall_input": _relative(root, daily_path),
        "rainfall_input_sha256": _sha256(daily_path),
        "canonical_input": _relative(root, canonical_path),
        "canonical_input_sha256": _sha256(canonical_path),
        "window_definition": {
            CONCURRENT: "sums end on and include the reported event day",
            ANTECEDENT: "sums end on the day before the reported event day",
        },
        "development_end": train_end.isoformat(),
        "temporal_test_start": (train_end + timedelta(days=1)).isoformat(),
        "controls_per_event": controls_per_event,
        "control_matching": "same district, calendar month, and year",
        "control_exclusion_buffer_days": exclusion_buffer,
        "primary_excluded_triggers": sorted(non_rainfall_triggers),
        "bootstrap": f"district-clustered, {bootstrap_iterations} iterations",
        "odds_ratio_scale_mm": ODDS_RATIO_SCALE_MM,
        "balanced_panel_rule": (
            f"publishers with at least {panel_minimum} canonical events on both "
            "sides of the development cut-off"
        ),
        "balanced_panel_sources": list(panel),
        "quality": quality,
        "canonical_events_read": len(events),
        "primary_events_before_rainfall_join": len(primary_eligible_events),
        "primary_events_after_available_rainfall_end": len(primary_after_rainfall),
        "available_rainfall_end": rainfall.end.isoformat(),
        "variants": variant_summary,
        "matching_diagnostics": diagnostics,
        "sensitivity_summary": sensitivity_summary,
        "primary_selected_by_exposure": primary_selected,
        "primary_window_selected_in_development": selected_development,
        "primary_temporal_test_result": selected_test,
        "conditional_models": conditional_rows,
        "resampled_validation": resampled,
        "season_stratified": season_rows,
        "reporting_composition": composition,
        "inventory_descriptive": descriptive,
        "secondary_district_month_association": monthly,
        "limitations": [
            "Event dates are media-derived; accuracy was not reportable in the locked test set.",
            "CHIRPS represents gridded precipitation, not a slope-level rain gauge measurement.",
            "District means smooth local rainfall extremes and are not warning thresholds.",
            "Media reporting and road-obstruction events can affect the case distribution.",
            "Precision reflects the matched 1:5 sample, not population event prevalence.",
            "The development and temporal-test periods draw on partly different publishers, so "
            "the temporal comparison is confounded with a change in the reporting instrument; "
            "see the balanced_source_panel variant and inventory_reporting_composition.csv.",
            "Concurrent windows include the reported event day and may contain rain that fell "
            "after failure; the strictly antecedent co-primary result bounds the usable signal.",
            "Some cases have no eligible matched control and some control district-days support "
            "more than one case; see rainfall_matching_diagnostics.json and the "
            "strict_matched_sets variant.",
            "Control days may include unreported landslides, which biases discrimination toward "
            "the null.",
            "Canonical records are deduplicated report clusters rather than verified distinct "
            "physical failures.",
        ],
    }
    (output_dir / "rainfall_analysis_report.json").write_text(
        json.dumps(_json_value(report), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    def _describe(exposure: str) -> str:
        entry = primary_selected.get(exposure) or {}
        test = entry.get("temporal_test")
        if not test:
            return "not estimable"
        return (
            f"R{test['window_days']} threshold {float(test['threshold_mm']):.1f} mm; "
            f"temporal-test AUC {float(test['auc']):.3f}, sensitivity "
            f"{float(test['sensitivity']):.3f}, specificity {float(test['specificity']):.3f}"
        )

    loyo = resampled.get(f"leave_one_year_out:{CONCURRENT}") or {}
    loyo_text = (
        f"median {float(loyo['auc_median']):.3f} "
        f"(range {float(loyo['auc_min']):.3f}-{float(loyo['auc_max']):.3f}, "
        f"SD {float(loyo['auc_sd']):.3f})"
        if loyo
        else "not estimable"
    )
    markdown = f"""# Rainfall threshold analysis

Primary design: district-day matched case-control analysis. Cases require
`conf_date >= {min_confidence}`. Controls are sampled in the same district,
calendar month, and year and are at least {exclusion_buffer} days from every
reported event. Thresholds are selected only in data through {train_end};
performance after that date is held out.

- Canonical events read: {len(events)}
- Primary cases with complete rainfall windows: {len(primary_cases)}
- Primary matched controls: {len(primary_controls)}
- Cases without any eligible control: {diagnostics['strata_without_controls']} \
({float(diagnostics['strata_without_controls_fraction']):.1%})
- Control rows repeating a district-day: {diagnostics['duplicate_control_rows']} \
({float(diagnostics['duplicate_control_row_fraction']):.1%})
- Daily rainfall coverage: {float(quality['coverage_fraction']):.3%}
- Primary (concurrent, includes event day): {_describe(CONCURRENT)}
- Co-primary (strictly antecedent, excludes event day): {_describe(ANTECEDENT)}
- Leave-one-year-out AUC, primary exposure: {loyo_text}
- Secondary district-month Spearman rho: {monthly['spearman_rho']}

Read the single temporal-test AUC against the leave-one-year-out distribution,
and read the development/test contrast against
`inventory_reporting_composition.csv`, because the two periods draw on partly
different publishers. The threshold is an empirical research result, not an
operational warning threshold. See `rainfall_analysis_report.json` for design
details and caveats.
"""
    (output_dir / "rainfall_analysis_report.md").write_text(markdown, encoding="utf-8")
    LOGGER.info(
        "Rainfall analysis complete: %s primary cases, %s controls; primary %s; co-primary %s",
        len(primary_cases),
        len(primary_controls),
        _describe(CONCURRENT),
        _describe(ANTECEDENT),
    )
