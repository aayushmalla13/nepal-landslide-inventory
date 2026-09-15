"""Daily rainfall inputs and threshold-analysis primitives.

The primary unit is a district-day.  Rainfall windows end on the reported
event day (R1, R3, R5 and R7); lagged windows ending one day earlier are also
kept for date-uncertainty sensitivity checks.
"""

from __future__ import annotations

import csv
import hashlib
import math
import random
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

DISTRICT_ALIASES = {
    "chitawan": "Chitwan",
    "eastern rukum": "Eastern Rukum",
    "kabhrepalanchok": "Kavrepalanchok",
    "kapilbastu": "Kapilvastu",
    "makawanpur": "Makwanpur",
    "nawalparasi e": "Nawalpur",
    "nawalparasi east": "Nawalpur",
    # The full official post-2017 names. Nepali sources and human annotators
    # both use these; hyphens and underscores are already stripped by
    # normalize_district, so only the spaced form needs a key.
    "nawalparasi bardaghat susta east": "Nawalpur",
    "nawalparasi bardaghat susta west": "Parasi",
    "nawalparasi w": "Parasi",
    "nawalparasi west": "Parasi",
    # A common English spelling of Tanahu, including in this project's own
    # labelled sets.
    "tanahun": "Tanahu",
    "rukum e": "Eastern Rukum",
    "rukum east": "Eastern Rukum",
    "rukum w": "Western Rukum",
    "rukum west": "Western Rukum",
}


OUTPUT_DECIMALS = 6


def round_output(value: float, decimals: int = OUTPUT_DECIMALS) -> float:
    """Round a value for emission so release checksums reproduce across machines.

    Rainfall accumulations are sums of floats, and summation order differs
    between platforms in the final ulp.  The science is unaffected, but an
    unrounded value makes a byte-level bundle-lock hash machine-specific.
    Rounding at emission keeps the frozen-release integrity model meaningful.
    Non-finite values pass through so that "unknown" is never silently coerced.
    """

    if not isinstance(value, float) or not math.isfinite(value):
        return value
    return round(value, decimals)


def normalize_district(value: str) -> str:
    """Return a canonical English district name."""

    cleaned = " ".join(value.replace("_", " ").replace("-", " ").split())
    key = cleaned.casefold()
    if key in DISTRICT_ALIASES:
        return DISTRICT_ALIASES[key]
    return cleaned.title()


@dataclass(frozen=True)
class DailyRainfall:
    """Validated district-day rainfall lookup."""

    values: Mapping[tuple[str, date], float]
    districts: tuple[str, ...]
    start: date
    end: date
    row_count: int


@dataclass(frozen=True)
class Event:
    event_id: str
    event_date: date
    district: str
    confidence: float
    event_type: str
    trigger: str = "unknown"
    source: str = ""


@dataclass(frozen=True)
class RainRecord:
    record_id: str
    matched_event_id: str
    event_date: date
    district: str
    label: int
    confidence: float
    values: Mapping[int, float]
    lagged_values: Mapping[int, float]
    case_event_count: int = 1


def read_daily_rainfall(path: Path) -> DailyRainfall:
    """Read and strictly validate a district-day rainfall CSV."""

    if not path.exists():
        raise FileNotFoundError(
            f"Daily CHIRPS input not found: {path}. Run scripts/download_chirps_climateserv.py."
        )
    values: dict[tuple[str, date], float] = {}
    districts: set[str] = set()
    first: date | None = None
    last: date | None = None
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"date", "district", "rain_mm"}
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"Rainfall CSV missing columns: {', '.join(sorted(missing))}")
        for line_number, row in enumerate(reader, start=2):
            try:
                day = date.fromisoformat(row["date"].strip())
                district = normalize_district(row["district"])
                rain = float(row["rain_mm"])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Invalid rainfall row at line {line_number}: {row}") from exc
            if not district:
                raise ValueError(f"Blank district at rainfall line {line_number}")
            if not math.isfinite(rain) or rain < 0:
                raise ValueError(f"Invalid rain_mm at line {line_number}: {rain}")
            key = (district, day)
            if key in values:
                raise ValueError(f"Duplicate rainfall district-day: {district} {day}")
            values[key] = rain
            districts.add(district)
            first = day if first is None else min(first, day)
            last = day if last is None else max(last, day)
    if not values or first is None or last is None:
        raise ValueError(f"Rainfall CSV contains no data rows: {path}")
    return DailyRainfall(values, tuple(sorted(districts)), first, last, len(values))


def rainfall_quality(data: DailyRainfall, expected_districts: Iterable[str]) -> dict[str, object]:
    """Summarize completeness without mistaking missing rainfall for zero."""

    expected = {normalize_district(item) for item in expected_districts}
    observed = set(data.districts)
    days = (data.end - data.start).days + 1
    expected_rows = days * len(expected)
    missing_days = 0
    incomplete_examples: list[dict[str, object]] = []
    cursor = data.start
    while cursor <= data.end:
        count = sum((district, cursor) in data.values for district in expected)
        if count != len(expected):
            missing_days += 1
            if len(incomplete_examples) < 10:
                incomplete_examples.append({"date": cursor.isoformat(), "district_rows": count})
        cursor += timedelta(days=1)
    return {
        "start": data.start.isoformat(),
        "end": data.end.isoformat(),
        "days": days,
        "rows": data.row_count,
        "expected_rows": expected_rows,
        "coverage_fraction": data.row_count / expected_rows if expected_rows else 0.0,
        "observed_districts": len(observed),
        "expected_districts": len(expected),
        "missing_districts": sorted(expected - observed),
        "unexpected_districts": sorted(observed - expected),
        "incomplete_days": missing_days,
        "incomplete_day_examples": incomplete_examples,
    }


def read_events(path: Path) -> list[Event]:
    """Read dated, district-resolved single events from the canonical CSV."""

    events: list[Event] = []
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("event_granularity", "single") != "single":
                continue
            raw_date = (row.get("event_date_ad") or "").strip()
            district = normalize_district(row.get("district") or "")
            if not raw_date or not district:
                continue
            try:
                confidence = float(row.get("conf_date") or 0)
            except ValueError:
                confidence = 0.0
            events.append(
                Event(
                    event_id=row["event_id"],
                    event_date=date.fromisoformat(raw_date),
                    district=district,
                    confidence=confidence,
                    event_type=(row.get("event_type") or "landslide").strip(),
                    trigger=(row.get("trigger") or "unknown").strip(),
                    source=(row.get("representative_source") or "").strip(),
                )
            )
    return events


def balanced_panel_sources(
    events: Iterable[Event],
    split_date: date,
    *,
    minimum_per_period: int,
) -> tuple[str, ...]:
    """Return publishers that reported at least ``minimum_per_period`` events on
    both sides of ``split_date``.

    Media inventories change instrument over time: titles start, stop, change
    beat, or switch language.  Restricting to a balanced panel of continuously
    reporting publishers separates a genuine temporal effect from a change in who
    was doing the reporting.  The rule is applied to the data rather than to a
    hard-coded list so it stays correct if the inventory is rebuilt.
    """

    before: dict[str, int] = defaultdict(int)
    after: dict[str, int] = defaultdict(int)
    for event in events:
        if not event.source:
            continue
        bucket = before if event.event_date <= split_date else after
        bucket[event.source] += 1
    return tuple(
        sorted(
            source
            for source in set(before) | set(after)
            if before[source] >= minimum_per_period and after[source] >= minimum_per_period
        )
    )


def accumulation(
    rainfall: DailyRainfall,
    district: str,
    end_day: date,
    window: int,
) -> float | None:
    """Sum a complete rainfall window, returning None if any day is absent."""

    daily: list[float] = []
    for offset in range(window):
        value = rainfall.values.get((district, end_day - timedelta(days=offset)))
        if value is None:
            return None
        daily.append(value)
    return sum(daily)


def make_rain_record(
    rainfall: DailyRainfall,
    *,
    record_id: str,
    matched_event_id: str,
    event_date: date,
    district: str,
    label: int,
    confidence: float,
    windows: Sequence[int],
    case_event_count: int = 1,
) -> RainRecord | None:
    """Join an event/control district-day to complete antecedent windows."""

    values = {window: accumulation(rainfall, district, event_date, window) for window in windows}
    lagged = {
        window: accumulation(rainfall, district, event_date - timedelta(days=1), window)
        for window in windows
    }
    if any(value is None for value in values.values()):
        return None
    return RainRecord(
        record_id=record_id,
        matched_event_id=matched_event_id,
        event_date=event_date,
        district=district,
        label=label,
        confidence=confidence,
        values={key: float(value) for key, value in values.items() if value is not None},
        lagged_values={
            key: float(value) for key, value in lagged.items() if value is not None
        },
        case_event_count=case_event_count,
    )


def build_cases(
    events: Sequence[Event],
    rainfall: DailyRainfall,
    windows: Sequence[int],
    min_confidence: float,
    date_shift_days: int = 0,
    excluded_triggers: frozenset[str] = frozenset(),
    excluded_event_types: frozenset[str] = frozenset(),
    included_sources: frozenset[str] | None = None,
) -> list[RainRecord]:
    """Create rainfall-enriched case records for a confidence/date variant."""

    grouped: dict[tuple[str, date], list[Event]] = defaultdict(list)
    for event in events:
        if event.confidence < min_confidence:
            continue
        if event.trigger in excluded_triggers or event.event_type in excluded_event_types:
            continue
        if included_sources is not None and event.source not in included_sources:
            continue
        shifted = event.event_date + timedelta(days=date_shift_days)
        grouped[(event.district, shifted)].append(event)

    records: list[RainRecord] = []
    for (district, shifted), grouped_events in sorted(grouped.items()):
        event_ids = sorted(event.event_id for event in grouped_events)
        record = make_rain_record(
            rainfall,
            record_id=f"case:{district}:{shifted.isoformat()}",
            matched_event_id="|".join(event_ids),
            event_date=shifted,
            district=district,
            label=1,
            confidence=max(event.confidence for event in grouped_events),
            windows=windows,
            case_event_count=len(grouped_events),
        )
        if record is not None:
            records.append(record)
    return records


def case_rng(seed: int, record_id: str) -> random.Random:
    """A per-case RNG stream that depends on the case and the seed alone.

    Independent of how many other cases exist, what order they are in, and
    whether any of them were added or removed. See ``build_matched_controls``.
    """

    digest = hashlib.sha256(f"{seed}:{record_id}".encode("utf-8")).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def build_matched_controls(
    cases: Sequence[RainRecord],
    all_events: Sequence[Event],
    rainfall: DailyRainfall,
    windows: Sequence[int],
    controls_per_event: int,
    exclusion_buffer_days: int,
    seed: int,
) -> list[RainRecord]:
    """Sample deterministic non-event controls within district/year/month strata.

    Each case draws from its own RNG stream, keyed by the case's record id.

    WHY, AND WHAT THIS FIXES
    ------------------------
    The first implementation used one ``random.Random(seed)`` for all cases and
    shuffled each pool from it in turn. That is deterministic given a fixed
    event list, but it couples every case to every case drawn before it:
    removing one event shifts the stream and redraws the controls for all the
    rest.

    That is not a theoretical concern. Truncating the CHIRPS series to the IMERG
    record for the product-sensitivity analysis dropped 181 events, every one of
    them after 2025-09-30. Those events cannot affect the 2015-2022 development
    split -- different years, different strata, no shared candidate days -- yet
    the development controls came back almost entirely different: 532 of 3,587
    survived, and the development-fitted cutpoint moved from 51.6 mm to 45.3 mm.
    A comparison meant to isolate the rainfall product was partly measuring a
    redrawn control sample.

    Keying each case's stream to its record id makes that case's controls a
    function of the case, its own candidate pool and the seed, and of nothing
    else. A sensitivity analysis that adds or removes events now perturbs only
    the strata it actually touches, which is the entire point of running one.

    SHA-256 rather than ``hash()``: string hashing is salted per process, so
    ``hash()`` would not reproduce across runs at all.
    """

    event_days: dict[str, set[date]] = defaultdict(set)
    for event in all_events:
        event_days[event.district].add(event.event_date)

    valid_by_stratum: dict[tuple[str, int, int], list[date]] = defaultdict(list)
    for district, day in rainfall.values:
        valid_by_stratum[(district, day.year, day.month)].append(day)

    controls: list[RainRecord] = []
    for case in cases:
        pool: list[date] = []
        for candidate in valid_by_stratum[
            (case.district, case.event_date.year, case.event_date.month)
        ]:
            if any(
                abs((candidate - event_day).days) <= exclusion_buffer_days
                for event_day in event_days.get(case.district, ())
            ):
                continue
            if accumulation(rainfall, case.district, candidate, max(windows)) is None:
                continue
            pool.append(candidate)
        case_rng(seed, case.record_id).shuffle(pool)
        for index, control_day in enumerate(pool[:controls_per_event], start=1):
            record = make_rain_record(
                rainfall,
                record_id=f"control:{case.record_id}:{index}",
                matched_event_id=case.record_id,
                event_date=control_day,
                district=case.district,
                label=0,
                confidence=case.confidence,
                windows=windows,
                case_event_count=0,
            )
            if record is not None:
                controls.append(record)
    return controls


def binary_metrics(
    labels: Sequence[int], scores: Sequence[float], threshold: float
) -> dict[str, float]:
    """Calculate threshold classification metrics."""

    pairs = list(zip(labels, scores, strict=False))
    tp = sum(label == 1 and score >= threshold for label, score in pairs)
    fp = sum(label == 0 and score >= threshold for label, score in pairs)
    tn = sum(label == 0 and score < threshold for label, score in pairs)
    fn = sum(label == 1 and score < threshold for label, score in pairs)
    sensitivity = tp / (tp + fn) if tp + fn else math.nan
    specificity = tn / (tn + fp) if tn + fp else math.nan
    precision = tp / (tp + fp) if tp + fp else math.nan
    return {
        "sensitivity": sensitivity,
        "specificity": specificity,
        "precision": precision,
        "balanced_accuracy": (sensitivity + specificity) / 2,
        "tp": float(tp),
        "fp": float(fp),
        "tn": float(tn),
        "fn": float(fn),
    }


def auc(labels: Sequence[int], scores: Sequence[float]) -> float:
    """Compute ROC AUC as the probability a case exceeds a control (ties half)."""

    positive_count = sum(label == 1 for label in labels)
    negative_count = sum(label == 0 for label in labels)
    if not positive_count or not negative_count:
        return math.nan
    ranks = average_ranks(scores)
    positive_rank_sum = sum(rank for rank, label in zip(ranks, labels, strict=False) if label == 1)
    wins = positive_rank_sum - positive_count * (positive_count + 1) / 2
    return wins / (positive_count * negative_count)


def roc_curve(labels: Sequence[int], scores: Sequence[float]) -> list[tuple[float, float, float]]:
    """Return (threshold, false-positive rate, true-positive rate) ROC points."""

    pairs = sorted(zip(scores, labels, strict=False), reverse=True)
    positive_count = sum(label == 1 for label in labels)
    negative_count = sum(label == 0 for label in labels)
    if not positive_count or not negative_count:
        return []
    points = [(math.inf, 0.0, 0.0)]
    true_positives = 0
    false_positives = 0
    cursor = 0
    while cursor < len(pairs):
        threshold = pairs[cursor][0]
        end = cursor
        while end < len(pairs) and pairs[end][0] == threshold:
            if pairs[end][1] == 1:
                true_positives += 1
            else:
                false_positives += 1
            end += 1
        points.append(
            (
                threshold,
                false_positives / negative_count,
                true_positives / positive_count,
            )
        )
        cursor = end
    return points


def youden_threshold(labels: Sequence[int], scores: Sequence[float]) -> float:
    """Choose a threshold using maximum training-set Youden J."""

    pairs = sorted(zip(scores, labels, strict=False), reverse=True)
    if not pairs:
        raise ValueError("Cannot estimate a threshold from no scores")
    positive_count = sum(label == 1 for label in labels)
    negative_count = sum(label == 0 for label in labels)
    if not positive_count or not negative_count:
        raise ValueError("Threshold estimation requires both cases and controls")
    best_threshold = pairs[0][0]
    best_key = (-math.inf, -math.inf)
    true_positives = 0
    false_positives = 0
    cursor = 0
    while cursor < len(pairs):
        threshold = pairs[cursor][0]
        end = cursor
        while end < len(pairs) and pairs[end][0] == threshold:
            if pairs[end][1] == 1:
                true_positives += 1
            else:
                false_positives += 1
            end += 1
        sensitivity = true_positives / positive_count
        specificity = 1 - false_positives / negative_count
        youden = sensitivity + specificity - 1
        balance = -abs(sensitivity - specificity)
        if (youden, balance) > best_key:
            best_key = (youden, balance)
            best_threshold = threshold
        cursor = end
    return best_threshold


def percentile(values: Sequence[float], probability: float) -> float:
    """Return a linearly interpolated empirical percentile."""

    if not values:
        return math.nan
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def bootstrap_metric_intervals(
    records: Sequence[RainRecord],
    window: int,
    threshold: float,
    *,
    iterations: int,
    seed: int,
    value_of: Callable[[RainRecord], float] | None = None,
) -> dict[str, tuple[float, float]]:
    """Bootstrap metrics by resampling district clusters with replacement.

    ``value_of`` selects the exposure definition; it defaults to the
    event-day-inclusive accumulation so existing callers keep their behaviour.
    """

    getter = value_of or (lambda record: record.values[window])
    grouped: dict[str, list[RainRecord]] = defaultdict(list)
    for record in records:
        grouped[record.district].append(record)
    districts = sorted(grouped)
    if len(districts) < 2 or iterations <= 0:
        return {}
    rng = random.Random(seed)
    draws: dict[str, list[float]] = defaultdict(list)
    for _ in range(iterations):
        sample: list[RainRecord] = []
        for district in rng.choices(districts, k=len(districts)):
            sample.extend(grouped[district])
        labels = [record.label for record in sample]
        scores = [getter(record) for record in sample]
        if len(set(labels)) < 2:
            continue
        metrics = binary_metrics(labels, scores, threshold)
        metrics["auc"] = auc(labels, scores)
        for name in ("auc", "sensitivity", "specificity", "precision", "balanced_accuracy"):
            if math.isfinite(metrics[name]):
                draws[name].append(metrics[name])
    return {
        name: (percentile(values, 0.025), percentile(values, 0.975))
        for name, values in draws.items()
        if values
    }


def bootstrap_threshold_interval(
    records: Sequence[RainRecord],
    window: int,
    *,
    iterations: int,
    seed: int,
    value_of: Callable[[RainRecord], float] | None = None,
) -> tuple[float, float] | None:
    """Estimate a district-clustered confidence interval for the cutpoint.

    The interval is estimated in whatever records are passed in; callers are
    responsible for passing the development split, and the emitted metrics
    record which split it came from.
    """

    getter = value_of or (lambda record: record.values[window])
    grouped: dict[str, list[RainRecord]] = defaultdict(list)
    for record in records:
        grouped[record.district].append(record)
    districts = sorted(grouped)
    if len(districts) < 2 or iterations <= 0:
        return None
    rng = random.Random(seed)
    thresholds: list[float] = []
    for _ in range(iterations):
        sample: list[RainRecord] = []
        for district in rng.choices(districts, k=len(districts)):
            sample.extend(grouped[district])
        labels = [record.label for record in sample]
        if len(set(labels)) < 2:
            continue
        scores = [getter(record) for record in sample]
        thresholds.append(youden_threshold(labels, scores))
    if not thresholds:
        return None
    return percentile(thresholds, 0.025), percentile(thresholds, 0.975)


def average_ranks(values: Sequence[float]) -> list[float]:
    """Assign average ranks, including ties."""

    order = sorted(range(len(values)), key=lambda index: values[index])
    ranks = [0.0] * len(values)
    cursor = 0
    while cursor < len(order):
        end = cursor + 1
        while end < len(order) and values[order[end]] == values[order[cursor]]:
            end += 1
        rank = (cursor + 1 + end) / 2
        for index in order[cursor:end]:
            ranks[index] = rank
        cursor = end
    return ranks


def spearman(x_values: Sequence[float], y_values: Sequence[float]) -> float:
    """Calculate Spearman rank correlation without an optional SciPy dependency."""

    if len(x_values) != len(y_values) or len(x_values) < 2:
        return math.nan
    x_ranks = average_ranks(x_values)
    y_ranks = average_ranks(y_values)
    x_mean = sum(x_ranks) / len(x_ranks)
    y_mean = sum(y_ranks) / len(y_ranks)
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_ranks, y_ranks, strict=False))
    x_scale = math.sqrt(sum((x - x_mean) ** 2 for x in x_ranks))
    y_scale = math.sqrt(sum((y - y_mean) ** 2 for y in y_ranks))
    return numerator / (x_scale * y_scale) if x_scale and y_scale else math.nan
