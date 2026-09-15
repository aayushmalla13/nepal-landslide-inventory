"""Design-faithful estimators for the matched district-day case-control sample.

The rainfall study samples up to ``controls_per_event`` non-event district-days
inside each case's district/calendar-month/year stratum.  Pooling every row into
a single ROC ignores that structure.  This module supplies the estimators the
design actually implies:

* :func:`conditional_logistic` -- 1:M conditional (stratified) logistic
  regression.  The stratum intercepts are conditioned out, so the estimate is a
  within-matched-set odds ratio.  Absolute risk is deliberately *not*
  identifiable from a matched case-control sample and is never reported.
* :func:`within_stratum_concordance` -- the probability that a case exceeds a
  control drawn from its own matched set.  This is the matched analogue of AUC.
* :func:`strict_matched_sets` -- complete matched sets with controls used at
  most once, for the pseudo-replication sensitivity analysis.

Everything is pure Python so the analysis keeps its zero-dependency footprint.
"""

from __future__ import annotations

import math
import random
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from .rainfall import RainRecord, percentile

_MAX_NEWTON_STEPS = 100
_CONVERGENCE = 1e-10
_MAX_STEP = 5.0


@dataclass(frozen=True)
class MatchedSet:
    """One case district-day and the control district-days matched to it."""

    stratum_id: str
    district: str
    case: RainRecord
    controls: tuple[RainRecord, ...]

    @property
    def is_complete(self) -> bool:
        """True when at least one control was available for the case."""

        return bool(self.controls)


@dataclass
class ConditionalFit:
    """Result of a 1:M conditional logistic regression."""

    names: tuple[str, ...]
    coefficients: tuple[float, ...]
    model_standard_errors: tuple[float, ...]
    robust_standard_errors: tuple[float, ...]
    log_likelihood: float
    strata: int
    clusters: int
    converged: bool
    iterations: int
    scale: float = 1.0
    diagnostics: dict[str, object] = field(default_factory=dict)

    def odds_ratio(self, index: int = 0) -> float:
        """Odds ratio for a ``scale``-unit increase in covariate ``index``."""

        return math.exp(self.coefficients[index] * self.scale)

    def odds_ratio_interval(self, index: int = 0, *, robust: bool = True) -> tuple[float, float]:
        """Wald 95% interval for the scaled odds ratio."""

        errors = self.robust_standard_errors if robust else self.model_standard_errors
        half = 1.959963984540054 * errors[index] * self.scale
        centre = self.coefficients[index] * self.scale
        return math.exp(centre - half), math.exp(centre + half)

    def wald_z(self, index: int = 0, *, robust: bool = True) -> float:
        """Wald test statistic.

        Reported alongside the p-value because the p-value underflows to
        exactly zero for large effects, which must not be read as certainty.
        """

        errors = self.robust_standard_errors if robust else self.model_standard_errors
        if not errors[index] or not math.isfinite(errors[index]):
            return math.nan
        return self.coefficients[index] / errors[index]

    def wald_p_value(self, index: int = 0, *, robust: bool = True) -> float:
        """Two-sided Wald p-value from the normal approximation."""

        z = self.wald_z(index, robust=robust)
        if not math.isfinite(z):
            return math.nan
        return math.erfc(abs(z) / math.sqrt(2.0))


def build_matched_sets(
    cases: Sequence[RainRecord],
    controls: Sequence[RainRecord],
) -> list[MatchedSet]:
    """Group controls under the case they were sampled for.

    Controls carry the originating case's ``record_id`` in ``matched_event_id``,
    which is what defines a stratum.  Cases without any control are retained and
    flagged rather than silently dropped, because they are not missing at random:
    they arise where reported events were dense enough to consume the eligible
    control pool.
    """

    grouped: dict[str, list[RainRecord]] = defaultdict(list)
    for control in controls:
        grouped[control.matched_event_id].append(control)
    sets: list[MatchedSet] = []
    for case in sorted(cases, key=lambda record: record.record_id):
        members = sorted(grouped.get(case.record_id, ()), key=lambda record: record.record_id)
        sets.append(
            MatchedSet(
                stratum_id=case.record_id,
                district=case.district,
                case=case,
                controls=tuple(members),
            )
        )
    return sets


def matching_diagnostics(sets: Sequence[MatchedSet]) -> dict[str, object]:
    """Quantify incomplete strata and control reuse.

    Both are structural properties of the sampling scheme rather than bugs, but
    both must be reported: incomplete strata contribute unmatched positives to a
    pooled ROC, and reused control days are counted as independent observations
    when they are not.
    """

    sizes: dict[int, int] = defaultdict(int)
    for item in sets:
        sizes[len(item.controls)] += 1
    control_days: dict[tuple[str, str], int] = defaultdict(int)
    control_rows = 0
    for item in sets:
        for control in item.controls:
            control_days[(control.district, control.event_date.isoformat())] += 1
            control_rows += 1
    reused = {key: count for key, count in control_days.items() if count > 1}
    repeats = sum(count - 1 for count in reused.values())
    incomplete = sizes.get(0, 0)
    return {
        "strata": len(sets),
        "strata_without_controls": incomplete,
        "strata_without_controls_fraction": incomplete / len(sets) if sets else 0.0,
        "controls_per_case_distribution": {str(k): v for k, v in sorted(sizes.items())},
        "control_rows": control_rows,
        "distinct_control_district_days": len(control_days),
        "reused_control_district_days": len(reused),
        "duplicate_control_rows": repeats,
        "duplicate_control_row_fraction": repeats / control_rows if control_rows else 0.0,
        "max_control_reuse": max(control_days.values(), default=0),
    }


def strict_matched_sets(sets: Sequence[MatchedSet], *, seed: int) -> list[MatchedSet]:
    """Return complete strata whose controls are used at most once overall.

    Control district-days are assigned greedily in a deterministic order, so a
    given non-event day supports exactly one case.  Strata left without any
    control are dropped.  This removes pseudo-replication at the cost of sample
    size and is used only as a sensitivity analysis.
    """

    rng = random.Random(seed)
    order = sorted(sets, key=lambda item: (len(item.controls), item.stratum_id))
    claimed: set[tuple[str, str]] = set()
    kept: list[MatchedSet] = []
    for item in order:
        available = [
            control
            for control in item.controls
            if (control.district, control.event_date.isoformat()) not in claimed
        ]
        if not available:
            continue
        rng.shuffle(available)
        available.sort(key=lambda record: record.record_id)
        for control in available:
            claimed.add((control.district, control.event_date.isoformat()))
        kept.append(
            MatchedSet(
                stratum_id=item.stratum_id,
                district=item.district,
                case=item.case,
                controls=tuple(available),
            )
        )
    return sorted(kept, key=lambda item: item.stratum_id)


def _invert(matrix: list[list[float]]) -> list[list[float]] | None:
    """Gauss-Jordan inverse; ``None`` when the matrix is singular."""

    size = len(matrix)
    work = [
        list(row) + [1.0 if i == j else 0.0 for j in range(size)]
        for i, row in enumerate(matrix)
    ]
    for column in range(size):
        pivot_row = max(range(column, size), key=lambda r: abs(work[r][column]))
        if abs(work[pivot_row][column]) < 1e-14:
            return None
        work[column], work[pivot_row] = work[pivot_row], work[column]
        pivot = work[column][column]
        work[column] = [value / pivot for value in work[column]]
        for row in range(size):
            if row == column:
                continue
            factor = work[row][column]
            if factor:
                work[row] = [a - factor * b for a, b in zip(work[row], work[column], strict=True)]
    return [row[size:] for row in work]


def conditional_logistic(
    sets: Sequence[MatchedSet],
    covariates: Sequence[tuple[str, Callable[[RainRecord], float]]],
    *,
    scale: float = 1.0,
    cluster: Callable[[MatchedSet], str] | None = None,
) -> ConditionalFit | None:
    """Fit 1:M conditional logistic regression by Newton-Raphson.

    The conditional likelihood for stratum ``s`` with case covariates
    ``x_s0`` and control covariates ``x_s1..x_sM`` is
    ``exp(b'x_s0) / sum_j exp(b'x_sj)``.  Stratum-specific intercepts cancel, so
    district, calendar month and year -- the matching variables -- are removed by
    construction rather than by adjustment.

    ``cluster`` selects the unit for the sandwich variance estimator; the default
    clusters on district, matching the bootstrap used elsewhere in the study.
    Returns ``None`` when no informative stratum survives.
    """

    usable = [item for item in sets if item.is_complete]
    if not usable or not covariates:
        return None
    names = tuple(name for name, _ in covariates)
    getters = [getter for _, getter in covariates]
    width = len(getters)
    cluster_of = cluster or (lambda item: item.district)

    design: list[tuple[list[float], list[list[float]], str]] = []
    for item in usable:
        case_row = [getter(item.case) for getter in getters]
        control_rows = [[getter(control) for getter in getters] for control in item.controls]
        design.append((case_row, control_rows, cluster_of(item)))

    beta = [0.0] * width
    log_likelihood = -math.inf
    converged = False
    separated = False
    iterations = 0
    information: list[list[float]] = [[0.0] * width for _ in range(width)]
    last_usable_inverse: list[list[float]] | None = None
    scores: dict[str, list[float]] = {}

    for step_number in range(1, _MAX_NEWTON_STEPS + 1):
        log_likelihood = 0.0
        gradient = [0.0] * width
        information = [[0.0] * width for _ in range(width)]
        scores = defaultdict(lambda: [0.0] * width)
        for case_row, control_rows, cluster_id in design:
            rows = [case_row, *control_rows]
            linear = [sum(b * x for b, x in zip(beta, row, strict=True)) for row in rows]
            peak = max(linear)
            weights = [math.exp(value - peak) for value in linear]
            total = sum(weights)
            probabilities = [weight / total for weight in weights]
            log_likelihood += linear[0] - (peak + math.log(total))
            mean = [
                sum(p * row[k] for p, row in zip(probabilities, rows, strict=True))
                for k in range(width)
            ]
            stratum_score = [case_row[k] - mean[k] for k in range(width)]
            for k in range(width):
                gradient[k] += stratum_score[k]
                scores[cluster_id][k] += stratum_score[k]
            for k in range(width):
                for m in range(width):
                    second = sum(
                        p * row[k] * row[m]
                        for p, row in zip(probabilities, rows, strict=True)
                    )
                    information[k][m] += second - mean[k] * mean[m]
        inverse = _invert(information)
        iterations = step_number
        if inverse is None:
            # The information matrix collapses when the exposure separates cases
            # from their own controls perfectly: the conditional likelihood is
            # then monotone and has no interior maximum.  Report the last
            # finite state, flagged, rather than a spurious finite optimum.
            separated = True
            break
        last_usable_inverse = inverse
        step = [sum(inverse[k][m] * gradient[m] for m in range(width)) for k in range(width)]
        largest = max(abs(value) for value in step)
        if largest > _MAX_STEP:
            step = [value * _MAX_STEP / largest for value in step]
        beta = [b + s for b, s in zip(beta, step, strict=True)]
        if largest < _CONVERGENCE:
            converged = True
            break

    inverse = _invert(information) or last_usable_inverse
    if inverse is None:
        return None
    model_errors = tuple(
        math.sqrt(inverse[k][k]) if inverse[k][k] > 0 else math.nan for k in range(width)
    )

    meat = [[0.0] * width for _ in range(width)]
    for vector in scores.values():
        for k in range(width):
            for m in range(width):
                meat[k][m] += vector[k] * vector[m]
    sandwich = [
        [
            sum(
                inverse[k][a] * meat[a][b] * inverse[b][m]
                for a in range(width)
                for b in range(width)
            )
            for m in range(width)
        ]
        for k in range(width)
    ]
    cluster_count = len(scores)
    correction = (
        cluster_count / (cluster_count - 1) if cluster_count > 1 else 1.0
    )
    robust_errors = tuple(
        math.sqrt(sandwich[k][k] * correction) if sandwich[k][k] > 0 else math.nan
        for k in range(width)
    )
    return ConditionalFit(
        names=names,
        coefficients=tuple(beta),
        model_standard_errors=model_errors,
        robust_standard_errors=robust_errors,
        log_likelihood=log_likelihood,
        strata=len(usable),
        clusters=cluster_count,
        converged=converged,
        iterations=iterations,
        scale=scale,
        diagnostics={
            "separated": separated,
            "max_iterations_reached": iterations >= _MAX_NEWTON_STEPS and not converged,
        },
    )


def within_stratum_concordance(
    sets: Sequence[MatchedSet],
    value_of: Callable[[RainRecord], float],
) -> tuple[float, int]:
    """Probability a case exceeds a control from its own matched set.

    Ties count one half, matching the convention used by :func:`~.rainfall.auc`.
    Returns ``(concordance, comparable_pairs)``; ``nan`` when no stratum has a
    control.
    """

    wins = 0.0
    pairs = 0
    for item in sets:
        if not item.controls:
            continue
        case_value = value_of(item.case)
        for control in item.controls:
            control_value = value_of(control)
            pairs += 1
            if case_value > control_value:
                wins += 1.0
            elif case_value == control_value:
                wins += 0.5
    if not pairs:
        return math.nan, 0
    return wins / pairs, pairs


def bootstrap_concordance_interval(
    sets: Sequence[MatchedSet],
    value_of: Callable[[RainRecord], float],
    *,
    iterations: int,
    seed: int,
) -> tuple[float, float] | None:
    """District-clustered bootstrap interval for within-stratum concordance."""

    grouped: dict[str, list[MatchedSet]] = defaultdict(list)
    for item in sets:
        if item.is_complete:
            grouped[item.district].append(item)
    districts = sorted(grouped)
    if len(districts) < 2 or iterations <= 0:
        return None
    rng = random.Random(seed)
    draws: list[float] = []
    for _ in range(iterations):
        sample: list[MatchedSet] = []
        for district in rng.choices(districts, k=len(districts)):
            sample.extend(grouped[district])
        value, pairs = within_stratum_concordance(sample, value_of)
        if pairs and math.isfinite(value):
            draws.append(value)
    if not draws:
        return None
    return percentile(draws, 0.025), percentile(draws, 0.975)
