"""Resampled validation schemes for the rainfall threshold analysis.

A single development/temporal-test split gives one number and no sense of how
much that number moves.  These routines refit the cutpoint on all data except a
held-out block and score the held-out block, so the spread of achievable
performance is visible:

* :func:`leave_one_year_out` -- holds out each calendar year in turn.  This is
  the honest description of year-to-year transferability.
* :func:`spatial_holdout` -- holds out deterministic groups of districts, so
  performance is measured in places whose data never informed the cutpoint.

Neither scheme replaces the prespecified temporal holdout, which remains the
primary validation.  They are reported alongside it so that a single favourable
or unfavourable split cannot be mistaken for the whole picture.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from .rainfall import RainRecord, auc, binary_metrics, youden_threshold


@dataclass(frozen=True)
class FoldResult:
    """Performance on one held-out block, with the cutpoint fitted elsewhere."""

    fold: str
    n_cases: int
    n_controls: int
    threshold_mm: float
    auc: float
    sensitivity: float
    specificity: float
    balanced_accuracy: float

    def as_row(self) -> dict[str, object]:
        return {
            "fold": self.fold,
            "n_cases": self.n_cases,
            "n_controls": self.n_controls,
            "threshold_mm": self.threshold_mm,
            "auc": self.auc,
            "sensitivity": self.sensitivity,
            "specificity": self.specificity,
            "balanced_accuracy": self.balanced_accuracy,
        }


def _score_fold(
    label: str,
    train: Sequence[RainRecord],
    test: Sequence[RainRecord],
    value_of: Callable[[RainRecord], float],
) -> FoldResult | None:
    train_labels = [record.label for record in train]
    test_labels = [record.label for record in test]
    if len(set(train_labels)) < 2 or len(set(test_labels)) < 2:
        return None
    threshold = youden_threshold(train_labels, [value_of(record) for record in train])
    scores = [value_of(record) for record in test]
    metrics = binary_metrics(test_labels, scores, threshold)
    return FoldResult(
        fold=label,
        n_cases=sum(label_value == 1 for label_value in test_labels),
        n_controls=sum(label_value == 0 for label_value in test_labels),
        threshold_mm=threshold,
        auc=auc(test_labels, scores),
        sensitivity=metrics["sensitivity"],
        specificity=metrics["specificity"],
        balanced_accuracy=metrics["balanced_accuracy"],
    )


def leave_one_year_out(
    records: Sequence[RainRecord],
    value_of: Callable[[RainRecord], float],
) -> list[FoldResult]:
    """Refit the cutpoint without each calendar year and score that year."""

    years = sorted({record.event_date.year for record in records})
    results: list[FoldResult] = []
    for year in years:
        train = [record for record in records if record.event_date.year != year]
        test = [record for record in records if record.event_date.year == year]
        result = _score_fold(str(year), train, test, value_of)
        if result is not None:
            results.append(result)
    return results


def district_folds(districts: Sequence[str], folds: int) -> dict[str, int]:
    """Assign districts to folds deterministically, round-robin over sorted names.

    Sorting first makes the assignment independent of input order and of any
    random seed, so a spatial holdout reproduces exactly.
    """

    if folds < 2:
        raise ValueError("Spatial holdout needs at least two folds")
    return {name: index % folds for index, name in enumerate(sorted(set(districts)))}


def spatial_holdout(
    records: Sequence[RainRecord],
    value_of: Callable[[RainRecord], float],
    *,
    folds: int = 5,
) -> list[FoldResult]:
    """Refit the cutpoint without each district group and score that group."""

    assignment = district_folds([record.district for record in records], folds)
    results: list[FoldResult] = []
    for fold in range(folds):
        train = [record for record in records if assignment[record.district] != fold]
        test = [record for record in records if assignment[record.district] == fold]
        result = _score_fold(f"district_fold_{fold + 1}", train, test, value_of)
        if result is not None:
            results.append(result)
    return results


def summarize_folds(results: Sequence[FoldResult]) -> dict[str, float]:
    """Median, range and spread of held-out AUC across folds."""

    values = sorted(result.auc for result in results if math.isfinite(result.auc))
    if not values:
        return {}
    count = len(values)
    middle = count // 2
    median = values[middle] if count % 2 else (values[middle - 1] + values[middle]) / 2
    mean = sum(values) / count
    variance = sum((value - mean) ** 2 for value in values) / (count - 1) if count > 1 else 0.0
    thresholds = [result.threshold_mm for result in results if math.isfinite(result.threshold_mm)]
    return {
        "folds": float(count),
        "auc_median": median,
        "auc_min": values[0],
        "auc_max": values[-1],
        "auc_sd": math.sqrt(variance),
        "threshold_min_mm": min(thresholds) if thresholds else math.nan,
        "threshold_max_mm": max(thresholds) if thresholds else math.nan,
    }
