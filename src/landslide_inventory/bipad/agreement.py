"""Cross-inventory agreement between the news inventory and BIPAD.

This replaces the framing in ``bipad/validation.py``, which computed

    precision = matches / canonical_count
    recall    = matches / bipad_count

That asserts BIPAD is ground truth and any news event absent from it is a false
positive. BIPAD is an independent, incomplete, differently-defined
administrative reporting system with its own under-reporting and its own
coverage discontinuities. Reviewers reject that framing on sight, and it also
**undersells the work**: a real landslide BIPAD missed is a contribution, not an
error (review §6.1a).

So: never precision and recall against BIPAD. Instead **overlap**,
**chance-corrected agreement**, **capture-recapture completeness** and **rank
correlation** — two incomplete observers of the same underlying process.

The six layers (review §6.2)
----------------------------
1. **Harmonise units.** BIPAD often records per-household or per-ward incidents
   while news aggregates them to one event. Collapse BIPAD to incident clusters
   (district x date-window) before comparing, and report how much collapsing
   was needed — that ratio is itself a finding about the two systems.
2. **Tiered matching**, many-to-many, each tier reported separately. The 1:1
   greedy assignment in the old code contradicts how the two systems actually
   record events.
3. **Chance-corrected agreement.** In a monsoon week a district has many BIPAD
   landslide rows, so a +-7-day district-level match is substantially chance.
   Permuting event dates within district gives the null; observed minus expected
   is the defensible statistic, and almost no news-inventory paper reports it.
4. **Capture-recapture.** Treat the two as independent samplers and estimate how
   many events *both* missed. This converts "BIPAD found 60% of ours" into a
   completeness estimate, which is the strongest available use of BIPAD.
5. **Aggregate agreement.** Two inventories can disagree on individual events
   and still agree on district-year structure — and that agreement is what
   licenses the downstream rainfall analysis.
6. **Directional error analysis.** Stratified samples of both unmatched sets,
   for the discussion section.

Three correctness bugs from the old implementation are fixed here and covered by
tests: the hazard filter no longer fails open, Bikram Sambat dates hard-fail
instead of silently parsing ~57 years off, and rows outside the study window are
excluded from the denominator.
"""

from __future__ import annotations

import csv
import logging
import math
import random
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

LOGGER = logging.getLogger(__name__)

# Bikram Sambat years run ~56.7 ahead of Gregorian. A BS date like 2081-03-25
# parses cleanly as an AD date and lands 57 years in the future, silently. Any
# 4-digit year in this band is BS and must be rejected, not guessed at.
BS_YEAR_MIN, BS_YEAR_MAX = 2070, 2090

MATCH_TIERS = ('A', 'B', 'C')


@dataclass(frozen=True)
class InventoryEvent:
    """One event from either inventory, in a common shape."""

    event_id: str
    district: str
    event_date: date
    municipality: str | None = None
    deaths: int | None = None
    source: str = 'news'
    member_ids: tuple[str, ...] = ()


class BikramSambatDateError(ValueError):
    """Raised when a date is in BS rather than AD.

    Deliberately an exception rather than a silent None: a BS date that parses
    as AD is off by ~57 years, which would corrupt every temporal comparison
    while looking like clean data.
    """


def parse_ad_date(value: str | None) -> date | None:
    """Parse an unambiguous AD date, refusing anything guessable.

    Two behaviours differ from the old ``parse_date``:

    - **BS years hard-fail.** ``date_bs`` is in the BIPAD export's column list
      and 2081-03-25 is a perfectly valid-looking AD string.
    - **Ambiguous day/month orders are refused.** The old code tried
      ``%d-%m-%Y`` before ``%m-%d-%Y``, so ``05-07-2024`` resolved silently and
      possibly wrongly. Here it returns None, and the caller reports how many
      dates were unparseable rather than absorbing a coin flip.
    """

    if value is None:
        return None
    cleaned = str(value).strip()
    if not cleaned:
        return None
    cleaned = cleaned.replace('T', ' ').split()[0].replace('.', '-').replace('/', '-')

    parts = cleaned.split('-')
    if parts and parts[0].isdigit() and len(parts[0]) == 4:
        year = int(parts[0])
        if BS_YEAR_MIN <= year <= BS_YEAR_MAX:
            raise BikramSambatDateError(
                f'{value!r} has year {year}, which is Bikram Sambat. Convert to AD '
                'before loading; parsing it as AD would shift the date by ~57 years.'
            )

    # ISO only. Anything else is ambiguous and is reported, not guessed.
    for fmt in ('%Y-%m-%d', '%Y-%m'):
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    return None


def is_landslide_hazard(hazard_value: str | None, landslide_terms: Sequence[str]) -> bool:
    """Whether a BIPAD row is a landslide. **Fails closed.**

    The old ``_is_landslide_row`` returned True when the hazard column was
    absent or empty::

        if not disaster_value:
            return True

    If the export's hazard column was not among the expected names, *every* row
    — floods, fires, epidemics — counted as a landslide, silently, and would
    have produced a plausible-looking recall number. An unknown hazard is not a
    landslide.
    """

    if not hazard_value or not str(hazard_value).strip():
        return False
    normalized = str(hazard_value).casefold()
    return any(term.casefold() in normalized for term in landslide_terms)


# --- Layer 1: harmonise units ------------------------------------------------

def collapse_to_incidents(
    events: Sequence[InventoryEvent],
    window_days: int = 1,
) -> tuple[list[InventoryEvent], dict[str, Any]]:
    """Collapse per-household/per-ward rows into incident clusters.

    BIPAD frequently records one row per affected household; news reports the
    whole slope failure as one event. Comparing them un-harmonised counts the
    same landslide once on one side and eleven times on the other.

    Returns the collapsed events and a summary of how much collapsing was
    needed — that ratio is a finding about the two systems' units, and belongs
    in the paper rather than in a footnote.
    """

    buckets: dict[tuple[str, str, date], list[InventoryEvent]] = defaultdict(list)
    for event in sorted(events, key=lambda e: (e.district, e.event_date, e.event_id)):
        anchor = event.event_date
        placed = False
        for (district, municipality, key_date), members in buckets.items():
            if district != event.district:
                continue
            if (municipality or '') != (event.municipality or ''):
                continue
            if abs((key_date - anchor).days) <= window_days:
                members.append(event)
                placed = True
                break
        if not placed:
            buckets[(event.district, event.municipality or '', anchor)] = [event]

    collapsed: list[InventoryEvent] = []
    for (district, municipality, key_date), members in sorted(buckets.items()):
        deaths = [m.deaths for m in members if m.deaths is not None]
        collapsed.append(InventoryEvent(
            event_id=members[0].event_id,
            district=district,
            event_date=min(m.event_date for m in members),
            municipality=municipality or None,
            deaths=sum(deaths) if deaths else None,
            source=members[0].source,
            member_ids=tuple(m.event_id for m in members),
        ))
    sizes = [len(m) for m in buckets.values()]
    return collapsed, {
        'input_rows': len(events),
        'incident_clusters': len(collapsed),
        'collapse_ratio': round(len(events) / len(collapsed), 3) if collapsed else None,
        'largest_cluster': max(sizes) if sizes else 0,
        'clusters_with_multiple_rows': sum(1 for s in sizes if s > 1),
    }


# --- Layer 2: tiered many-to-many matching -----------------------------------

@dataclass(frozen=True)
class Match:
    news_id: str
    bipad_id: str
    tier: str
    day_gap: int
    death_gap: int | None


def match_tier(news: InventoryEvent, bipad: InventoryEvent) -> str | None:
    """Strictest tier a pair satisfies, or None.

    Tiers are reported separately rather than pooled, because a Tier-C match
    (same district, within a week) is far weaker evidence than Tier A and the
    reader should see the mix.
    """

    if news.district != bipad.district:
        return None
    gap = abs((news.event_date - bipad.event_date).days)
    same_municipality = (
        news.municipality and bipad.municipality
        and news.municipality.casefold() == bipad.municipality.casefold()
    )
    if same_municipality and gap <= 1:
        return 'A'
    deaths_close = (
        news.deaths is not None and bipad.deaths is not None
        and abs(news.deaths - bipad.deaths) <= 1
    )
    if gap <= 3 and deaths_close:
        return 'B'
    if gap <= 7:
        return 'C'
    return None


def match_inventories(
    news: Sequence[InventoryEvent],
    bipad: Sequence[InventoryEvent],
) -> tuple[list[Match], dict[str, Any]]:
    """Many-to-many matching. Deliberately not a 1:1 assignment.

    The old code took a greedy 1:1 pairing, which contradicts how the systems
    record: BIPAD may hold several ward-level rows for one news event, and one
    BIPAD incident may appear in several news follow-ups. Forcing 1:1 discards
    that structure; the multiplicity distribution is reported instead.
    """

    by_district: dict[str, list[InventoryEvent]] = defaultdict(list)
    for event in bipad:
        by_district[event.district].append(event)

    matches: list[Match] = []
    for news_event in sorted(news, key=lambda e: (e.district, e.event_date, e.event_id)):
        for bipad_event in sorted(by_district.get(news_event.district, []),
                                  key=lambda e: (e.event_date, e.event_id)):
            tier = match_tier(news_event, bipad_event)
            if tier is None:
                continue
            death_gap = (
                abs(news_event.deaths - bipad_event.deaths)
                if news_event.deaths is not None and bipad_event.deaths is not None else None
            )
            matches.append(Match(
                news_id=news_event.event_id, bipad_id=bipad_event.event_id, tier=tier,
                day_gap=abs((news_event.event_date - bipad_event.event_date).days),
                death_gap=death_gap,
            ))

    per_news: dict[str, int] = defaultdict(int)
    per_bipad: dict[str, int] = defaultdict(int)
    for m in matches:
        per_news[m.news_id] += 1
        per_bipad[m.bipad_id] += 1
    tier_counts = {t: sum(1 for m in matches if m.tier == t) for t in MATCH_TIERS}
    return matches, {
        'matches': len(matches),
        'by_tier': tier_counts,
        'news_matched': len(per_news),
        'bipad_matched': len(per_bipad),
        'news_total': len(news),
        'bipad_total': len(bipad),
        'overlap_news_side': round(len(per_news) / len(news), 4) if news else None,
        'overlap_bipad_side': round(len(per_bipad) / len(bipad), 4) if bipad else None,
        'multiplicity_max_per_news': max(per_news.values()) if per_news else 0,
        'multiplicity_max_per_bipad': max(per_bipad.values()) if per_bipad else 0,
    }


# --- Layer 3: chance-corrected agreement -------------------------------------

def chance_corrected_agreement(
    news: Sequence[InventoryEvent],
    bipad: Sequence[InventoryEvent],
    permutations: int = 200,
    seed: int = 20260807,
    tier: str | None = None,
) -> dict[str, Any]:
    """Observed overlap minus overlap expected by chance.

    In a monsoon week one district holds many BIPAD landslide rows, so a
    +-7-day district-level match happens readily by coincidence. Without this
    correction the raw match rate is close to meaningless; with it there is a
    defensible statistic.

    The null shuffles event dates **within district**, which preserves each
    district's event count and seasonality while destroying the day-level
    correspondence. Seeded, so the figure is reproducible.
    """

    def _rate(a: Sequence[InventoryEvent], b: Sequence[InventoryEvent]) -> float:
        matches, summary = match_inventories(a, b)
        if tier is None:
            return summary['overlap_news_side'] or 0.0
        # Restrict to one tier: pooling them lets the loosest tier dominate.
        matched = {m.news_id for m in matches if m.tier == tier}
        return len(matched) / len(a) if a else 0.0

    observed_rate = _rate(news, bipad)

    by_district: dict[str, list[date]] = defaultdict(list)
    for event in bipad:
        by_district[event.district].append(event.event_date)

    rng = random.Random(seed)
    null_rates: list[float] = []
    for _ in range(permutations):
        shuffled: list[InventoryEvent] = []
        for district, dates in by_district.items():
            pool = list(dates)
            rng.shuffle(pool)
            for event, new_date in zip(
                [e for e in bipad if e.district == district], pool
            ):
                shuffled.append(InventoryEvent(
                    event_id=event.event_id, district=district, event_date=new_date,
                    municipality=event.municipality, deaths=event.deaths, source=event.source,
                ))
        null_rates.append(_rate(news, shuffled))

    expected = statistics.fmean(null_rates) if null_rates else 0.0
    spread = statistics.pstdev(null_rates) if len(null_rates) > 1 else 0.0
    # Share of permutations reaching the observed value: an empirical p-value.
    at_least = sum(1 for r in null_rates if r >= observed_rate)
    return {
        'observed_overlap': round(observed_rate, 4),
        'expected_by_chance': round(expected, 4),
        'chance_corrected': round(observed_rate - expected, 4),
        'null_sd': round(spread, 4),
        'z': round((observed_rate - expected) / spread, 2) if spread > 0 else None,
        'empirical_p': round((at_least + 1) / (len(null_rates) + 1), 4) if null_rates else None,
        'permutations': permutations,
        'seed': seed,
        'tier': tier or 'any',
    }


# --- Layer 4: capture-recapture ----------------------------------------------

def capture_recapture(news_total: int, bipad_total: int, matched: int) -> dict[str, Any]:
    """Estimate how many events BOTH inventories missed.

    Chapman's bias-corrected Lincoln-Petersen estimator, which behaves at small
    overlap where the plain estimator does not.

    **The independence assumption is the weak point and must be stated.** BIPAD
    reporting is partly media-triggered, so the two samplers are positively
    correlated; that biases the population estimate *downward*, making this a
    lower bound on the true event count. Stratifying by casualty severity bounds
    the bias, since severe events are near-certain to appear in both.
    """

    if matched <= 0:
        return {'estimate': None, 'note': 'no overlap; capture-recapture undefined'}
    n1, n2, m = news_total, bipad_total, matched
    estimate = ((n1 + 1) * (n2 + 1) / (m + 1)) - 1
    variance = ((n1 + 1) * (n2 + 1) * (n1 - m) * (n2 - m)) / (((m + 1) ** 2) * (m + 2))
    se = math.sqrt(variance) if variance > 0 else 0.0
    return {
        'estimator': 'Chapman (bias-corrected Lincoln-Petersen)',
        'news_total': n1, 'bipad_total': n2, 'matched': m,
        'estimated_population': round(estimate, 1),
        'se': round(se, 1),
        'ci95': [round(estimate - 1.96 * se, 1), round(estimate + 1.96 * se, 1)],
        'news_completeness': round(n1 / estimate, 4) if estimate > 0 else None,
        'bipad_completeness': round(n2 / estimate, 4) if estimate > 0 else None,
        'assumption': (
            'Independent samplers. BIPAD reporting is partly media-triggered, which '
            'violates this and biases the population estimate downward — treat as a '
            'lower bound. Stratify by casualty severity to bound the bias.'
        ),
    }


# --- Layer 5: aggregate-scale agreement --------------------------------------

def _spearman(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    """Spearman rho with average ranks for ties. Hand-rolled to avoid scipy."""

    if len(xs) < 3:
        return None

    def _ranks(values: Sequence[float]) -> list[float]:
        order = sorted(range(len(values)), key=lambda i: values[i])
        ranks = [0.0] * len(values)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
                j += 1
            average = (i + j) / 2 + 1
            for k in range(i, j + 1):
                ranks[order[k]] = average
            i = j + 1
        return ranks

    rx, ry = _ranks(xs), _ranks(ys)
    mx, my = statistics.fmean(rx), statistics.fmean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return round(num / den, 4) if den else None


def aggregate_agreement(
    news: Sequence[InventoryEvent],
    bipad: Sequence[InventoryEvent],
    by: str = 'district_year',
) -> dict[str, Any]:
    """Compare district-year (or district-month) counts.

    Two inventories can disagree wildly on individual events and still agree on
    spatial-temporal structure — and it is that agreement, not event-level
    matching, which licenses the downstream rainfall analysis.

    Also returns Bland-Altman terms (mean difference and limits of agreement),
    which show *systematic* bias that a correlation hides.
    """

    def key(event: InventoryEvent) -> tuple[str, str]:
        stamp = (event.event_date.strftime('%Y') if by == 'district_year'
                 else event.event_date.strftime('%Y-%m'))
        return (event.district, stamp)

    news_counts: dict[tuple[str, str], int] = defaultdict(int)
    bipad_counts: dict[tuple[str, str], int] = defaultdict(int)
    for event in news:
        news_counts[key(event)] += 1
    for event in bipad:
        bipad_counts[key(event)] += 1

    cells = sorted(set(news_counts) | set(bipad_counts))
    xs = [float(news_counts.get(c, 0)) for c in cells]
    ys = [float(bipad_counts.get(c, 0)) for c in cells]
    diffs = [a - b for a, b in zip(xs, ys)]
    mean_diff = statistics.fmean(diffs) if diffs else 0.0
    sd_diff = statistics.pstdev(diffs) if len(diffs) > 1 else 0.0
    return {
        'aggregation': by,
        'cells': len(cells),
        'spearman_rho': _spearman(xs, ys),
        'bland_altman_mean_difference': round(mean_diff, 3),
        'bland_altman_limits': [round(mean_diff - 1.96 * sd_diff, 3),
                                round(mean_diff + 1.96 * sd_diff, 3)],
        'news_total': int(sum(xs)), 'bipad_total': int(sum(ys)),
    }


# --- Layer 6: directional error analysis -------------------------------------

def unmatched_samples(
    news: Sequence[InventoryEvent],
    bipad: Sequence[InventoryEvent],
    matches: Sequence[Match],
    per_stratum: int = 15,
    seed: int = 20260807,
) -> dict[str, list[dict[str, Any]]]:
    """Stratified samples of both unmatched sets, for manual review.

    The two questions are different and both belong in the discussion:
    a news event BIPAD missed is either a genuine gap in BIPAD or one of our
    false positives; a BIPAD incident the news missed is either a coverage gap
    or a granularity artefact. Sampling both, stratified by district, is the
    table that answers them.
    """

    matched_news = {m.news_id for m in matches}
    matched_bipad = {m.bipad_id for m in matches}
    rng = random.Random(seed)

    def _sample(events: Sequence[InventoryEvent], exclude: set[str]) -> list[dict[str, Any]]:
        remaining = [e for e in events if e.event_id not in exclude]
        by_district: dict[str, list[InventoryEvent]] = defaultdict(list)
        for event in remaining:
            by_district[event.district].append(event)
        picked: list[InventoryEvent] = []
        for district in sorted(by_district):
            pool = sorted(by_district[district], key=lambda e: e.event_id)
            rng.shuffle(pool)
            picked.extend(pool[:max(1, per_stratum // max(len(by_district), 1))])
        return [{
            'event_id': e.event_id, 'district': e.district,
            'event_date': e.event_date.isoformat(), 'municipality': e.municipality,
            'deaths': e.deaths, 'source': e.source,
        } for e in sorted(picked, key=lambda e: (e.district, e.event_date))]

    return {
        'unmatched_news': _sample(news, matched_news),
        'unmatched_bipad': _sample(bipad, matched_bipad),
    }


def full_agreement_report(
    news: Sequence[InventoryEvent],
    bipad: Sequence[InventoryEvent],
    *,
    permutations: int = 200,
) -> dict[str, Any]:
    """Run all six layers. Reports overlap and agreement, never precision/recall."""

    bipad_collapsed, harmonisation = collapse_to_incidents(bipad)
    matches, overlap = match_inventories(news, bipad_collapsed)
    return {
        'layer1_harmonisation': harmonisation,
        'layer2_overlap': overlap,
        # Per tier, not pooled. A synthetic run with 60% true overlap gave
        # observed 0.742 / expected 0.742 / corrected 0.000 when tiers were
        # pooled: with ~870 BIPAD incidents across 77 districts and
        # monsoon-clustered dates, almost any news event finds SOME BIPAD row
        # within a week in the same district, so Tier C alone is noise. The
        # tiering only earns its keep if each tier is corrected separately.
        'layer3_chance_corrected': {
            'pooled': chance_corrected_agreement(
                news, bipad_collapsed, permutations=permutations),
            **{f'tier_{t}': chance_corrected_agreement(
                news, bipad_collapsed, permutations=permutations, tier=t)
               for t in MATCH_TIERS},
        },
        'layer4_capture_recapture': capture_recapture(
            len(news), len(bipad_collapsed), overlap['news_matched']),
        'layer5_aggregate': {
            'district_year': aggregate_agreement(news, bipad_collapsed, 'district_year'),
            'district_month': aggregate_agreement(news, bipad_collapsed, 'district_month'),
        },
        'layer6_unmatched_samples': unmatched_samples(news, bipad_collapsed, matches),
        'framing_note': (
            'These are overlap and agreement statistics between two independent, '
            'incomplete observation systems. Precision and recall against BIPAD are '
            'not reported and must not be derived from these numbers: BIPAD is not '
            'ground truth, and a news event it missed is a contribution rather than '
            'an error.'
        ),
    }


# --- loading, with the study-window filter the old code lacked ---------------

def load_bipad_rows(
    path: Path,
    landslide_terms: Sequence[str],
    study_start: date,
    study_end: date,
    hazard_columns: Sequence[str],
    date_columns: Sequence[str],
    district_columns: Sequence[str],
) -> tuple[list[InventoryEvent], dict[str, Any]]:
    """Load a BIPAD export, keeping only in-window landslide rows.

    Every exclusion is counted and reported rather than silently applied -- the
    denominator of any completeness statistic depends on these decisions, so a
    reader has to be able to see them.

    ``_first_date`` in the old code fell back to scanning *every* column value
    for anything date-shaped, in dict order, so it could return ``created_at``
    instead of the incident date. Here the date columns are consulted in an
    explicit priority order and nothing else.
    """

    counts = {
        'rows_read': 0, 'not_landslide': 0, 'no_date': 0, 'bs_date': 0,
        'out_of_window': 0, 'no_district': 0, 'kept': 0,
    }
    events: list[InventoryEvent] = []
    with Path(path).open(encoding='utf-8-sig', newline='') as handle:
        for index, row in enumerate(csv.DictReader(handle)):
            counts['rows_read'] += 1
            hazard = next((row[c] for c in hazard_columns if row.get(c)), None)
            if not is_landslide_hazard(hazard, landslide_terms):
                counts['not_landslide'] += 1
                continue
            raw_date = next((row[c] for c in date_columns if row.get(c)), None)
            try:
                parsed = parse_ad_date(raw_date)
            except BikramSambatDateError as exc:
                LOGGER.warning('Row %d: %s', index, exc)
                counts['bs_date'] += 1
                continue
            if parsed is None:
                counts['no_date'] += 1
                continue
            if not (study_start <= parsed <= study_end):
                counts['out_of_window'] += 1
                continue
            district = next((row[c] for c in district_columns if row.get(c)), None)
            if not district:
                counts['no_district'] += 1
                continue
            deaths = None
            for column in ('deaths', 'death', 'people_death_count', 'death_count'):
                value = (row.get(column) or '').strip()
                if value.isdigit():
                    deaths = int(value)
                    break
            counts['kept'] += 1
            events.append(InventoryEvent(
                event_id=str(row.get('id') or row.get('incident_id') or f'bipad-{index}'),
                district=str(district).strip(), event_date=parsed,
                municipality=(row.get('municipality') or '').strip() or None,
                deaths=deaths, source='bipad',
            ))
    return events, counts
