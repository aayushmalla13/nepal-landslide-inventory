"""Locked, decision-stratified test set drawn from ``raw_articles``.

Why this module exists
----------------------
The pre-existing evaluation sample (``manual_pack.py``) is drawn from

    WHERE COALESCE(in_nepal, 1) = 1 AND COALESCE(class, 3) IN (1, 2)

i.e. only from rows the pipeline decided to keep.  No excluded article is ever
reviewed, so the false-negative rate of ``scope_filter`` and
``event_specificity`` is *structurally unmeasurable*, and the reported "recall"
is recall-within-the-retained-set, which is not the quantity a paper needs.
See ``docs/TECHNICAL_REVIEW.md`` section 5.1.

This module draws instead from **every article that passed keyword collection**,
stratified by the pipeline's own decision, so that dropped articles are
reviewable and false negatives become measurable.

Design
------
1. **Sampling frame** = ``raw_articles`` (all 4,453 rows), left-joined to
   ``article_events`` for the decision label.  Articles with no event row are
   still eligible and are labelled ``no_extraction``.

2. **Strata** = ``pipeline_decision`` x ``route_lang``.  Decision is the axis
   that carries the scientific question (what did we wrongly throw away?);
   language is the axis along which the extractors differ.

3. **Unequal-probability allocation.**  Dropped strata are deliberately
   *oversampled* relative to their population share, because measuring the
   drop rate is the whole point.  Every row therefore carries an
   ``inclusion_weight = stratum_N / stratum_n`` so that population-level
   estimates can be recovered by weighting.  **Any metric computed from this
   sample must be weighted.**  Unweighted numbers describe the sample, not the
   inventory.

4. **Systematic within-stratum draw** over a ``(source, year, stable_hash)``
   ordering, which spreads the draw across outlets and years deterministically
   without a second allocation layer.

5. **Blind by construction.**  Two files are written:
   ``*_labels.csv`` (url/source/title/snippet + empty truth columns) is what the
   annotator sees; ``*_predictions.csv`` is joined only at scoring time.  This
   removes the anchoring path described in review section 5.3.

6. **Hash-locked.**  ``*_manifest.json`` records the seed, the allocation, and a
   SHA-256 over the ordered URL list.  ``verify_locked_manifest`` re-derives it.
   The manifest is committed to git; the test set is never re-drawn and never
   re-labelled.  If you find yourself wanting to change it, you want a *new*
   test set with a new name, not an edit to this one.

Usage
-----
    python -m landslide_inventory.run --stage locked_test_set
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import json
import logging
from typing import Any, Iterable, Sequence

from ..config import AppConfig
from ..db import connect_sqlite
from ..utils import ensure_directory, stable_hash
from .common import derive_year, iso_now, normalize_whitespace, write_csv

LOGGER = logging.getLogger(__name__)

# Bump this (and the output name) if the design ever changes. Never edit a
# frozen set in place -- draw a new one.
DESIGN_VERSION = 'v1'
DEFAULT_SEED = 20260806
DEFAULT_TARGET_SIZE = 400
OUTPUT_STEM = f'locked_test_set_{DESIGN_VERSION}'

# Deliberately non-proportional. Dropped strata are oversampled so that the
# false-negative rate is estimable; inclusion_weight restores population scale.
DECISION_ALLOCATION: dict[str, int] = {
    'kept_class1': 130,
    'kept_class2': 50,
    'dropped_specificity': 130,
    'dropped_scope': 70,
    'dropped_other': 15,
    'no_extraction': 5,
}

LABEL_COLUMNS = [
    'row_id', 'url', 'source', 'year', 'route_lang', 'title', 'snippet',
    # --- annotator fills these; nothing above is a prediction ---
    'is_landslide_event_true',
    'in_nepal_true',
    'hazard_type_true',
    'event_granularity_true',
    'article_role_true',
    'district_true',
    'municipality_true',
    'date_true',
    'deaths_true',
    'trigger_true',
    'annotator',
    'notes',
]

PREDICTION_COLUMNS = [
    'row_id', 'url', 'stratum', 'pipeline_decision', 'inclusion_weight',
    'class_pred', 'in_nepal_pred', 'district_pred', 'municipality_pred',
    'event_date_pred', 'deaths_pred', 'missing_pred', 'injured_pred', 'trigger_pred',
    'specificity_ok', 'specificity_reason', 'specificity_score',
    'scope_reason', 'location_consistent', 'location_reason',
]

# Controlled vocabularies. ``manual_score`` historically accepted anything,
# which is how a literal ``unkown`` typo became a truth class with 17 rows
# (review section 5.4). Scoring must hard-fail on values outside these sets.
TRUTH_VOCABULARIES: dict[str, tuple[str, ...]] = {
    'is_landslide_event_true': ('yes', 'no', 'unclear'),
    'in_nepal_true': ('yes', 'no', 'unclear'),
    'hazard_type_true': (
        'landslide', 'debris_flow', 'rockfall', 'avalanche', 'flood',
        'other_hazard', 'not_a_hazard', 'unclear',
    ),
    'event_granularity_true': ('single', 'multi', 'roundup', 'not_applicable', 'unclear'),
    'article_role_true': (
        'first_report', 'follow_up', 'retrospective', 'forecast_or_risk',
        'metaphor_or_nonevent', 'unclear',
    ),
}


@dataclass(frozen=True)
class FrameRow:
    """One article in the sampling frame, with its pipeline decision."""

    url: str
    source: str
    year: str
    route_lang: str
    title: str
    snippet: str
    pipeline_decision: str
    predictions: dict[str, Any] = field(default_factory=dict)

    @property
    def stratum(self) -> str:
        return f'{self.pipeline_decision}|{self.route_lang or "unknown"}'


def classify_decision(
    has_event_row: bool,
    event_class: int | None,
    in_nepal: int | None,
    specificity_ok: int | None,
) -> str:
    """Return the pipeline's own disposition for an article.

    Mutually exclusive and exhaustive over the sampling frame. Order matters:
    scope is evaluated before specificity because an out-of-country article is
    dropped for scope reasons regardless of what specificity said about it.
    """

    if not has_event_row:
        return 'no_extraction'
    if in_nepal == 0:
        return 'dropped_scope'
    if specificity_ok == 0:
        return 'dropped_specificity'
    if event_class == 1:
        return 'kept_class1'
    if event_class == 2:
        return 'kept_class2'
    return 'dropped_other'


def load_frame(connection) -> list[FrameRow]:
    """Load every collected article with its pipeline decision attached.

    LEFT JOIN, not INNER: articles that never produced an event row are part of
    the frame. Excluding them would reintroduce the survivorship bias this
    module exists to remove.
    """

    query = """
        SELECT
            r.url               AS url,
            r.source            AS source,
            r.title             AS title,
            r.text              AS text,
            r.published_date_ad AS published_date_ad,
            r.published_date_raw AS published_date_raw,
            e.url               AS event_url,
            e.route_lang        AS route_lang,
            e.class             AS class_pred,
            e.in_nepal          AS in_nepal_pred,
            e.district          AS district_pred,
            e.municipality      AS municipality_pred,
            e.event_date_ad     AS event_date_pred,
            e.deaths            AS deaths_pred,
            e.missing           AS missing_pred,
            e.injured           AS injured_pred,
            e.trigger           AS trigger_pred,
            e.specificity_ok    AS specificity_ok,
            e.specificity_reason AS specificity_reason,
            e.specificity_score AS specificity_score,
            e.scope_reason      AS scope_reason,
            e.location_consistent AS location_consistent,
            e.location_reason   AS location_reason
        FROM raw_articles AS r
        LEFT JOIN article_events AS e ON e.url = r.url
        ORDER BY r.url
    """
    rows: list[FrameRow] = []
    for record in connection.execute(query):
        item = dict(record)
        decision = classify_decision(
            has_event_row=item['event_url'] is not None,
            event_class=item['class_pred'],
            in_nepal=item['in_nepal_pred'],
            specificity_ok=item['specificity_ok'],
        )
        rows.append(
            FrameRow(
                url=item['url'],
                source=item['source'] or '',
                year=derive_year(item['published_date_ad'], item['published_date_raw']),
                route_lang=item['route_lang'] or '',
                title=normalize_whitespace(item['title'])[:300],
                snippet=normalize_whitespace(item['text'])[:400],
                pipeline_decision=decision,
                predictions={key: item.get(key) for key in (
                    'class_pred', 'in_nepal_pred', 'district_pred', 'municipality_pred',
                    'event_date_pred', 'deaths_pred', 'missing_pred', 'injured_pred',
                    'trigger_pred', 'specificity_ok', 'specificity_reason',
                    'specificity_score', 'scope_reason', 'location_consistent',
                    'location_reason',
                )},
            )
        )
    return rows


def allocate_within_decision(
    strata_sizes: dict[str, int],
    decision_quota: int,
) -> dict[str, int]:
    """Split a decision's quota across its language strata, proportionally.

    Uses largest-remainder so the parts sum exactly to the quota, and gives
    every non-empty stratum at least one row -- a language stratum with zero
    sampled rows is an unmeasurable stratum.
    """

    total = sum(strata_sizes.values())
    if total == 0:
        return {}
    quota = min(decision_quota, total)
    exact = {key: quota * size / total for key, size in strata_sizes.items()}
    allocation = {key: min(int(value), strata_sizes[key]) for key, value in exact.items()}
    # Floor of 1 for any non-empty stratum.
    for key, size in strata_sizes.items():
        if size > 0 and allocation[key] == 0:
            allocation[key] = 1
    # Largest-remainder reconciliation, deterministic on ties via key order.
    def _drift() -> int:
        return quota - sum(allocation.values())

    remainders = sorted(
        strata_sizes,
        key=lambda key: (-(exact[key] - int(exact[key])), key),
    )
    index = 0
    while _drift() > 0 and remainders:
        key = remainders[index % len(remainders)]
        if allocation[key] < strata_sizes[key]:
            allocation[key] += 1
        elif all(allocation[k] >= strata_sizes[k] for k in strata_sizes):
            break
        index += 1
    shrinkable = sorted(strata_sizes, key=lambda key: (-allocation[key], key))
    index = 0
    while _drift() < 0 and shrinkable:
        key = shrinkable[index % len(shrinkable)]
        if allocation[key] > 1:
            allocation[key] -= 1
        elif all(allocation[k] <= 1 for k in shrinkable):
            break
        index += 1
    return allocation


def systematic_draw(rows: Sequence[FrameRow], count: int, seed: int) -> list[FrameRow]:
    """Deterministically draw ``count`` rows spread across source and year.

    Ordering by ``(source, year, stable_hash)`` and then taking a systematic
    every-k-th pick spreads the draw across outlets and years without needing a
    second allocation layer, and is reproducible from the seed alone.
    """

    if count <= 0 or not rows:
        return []
    ordered = sorted(rows, key=lambda row: (row.source, row.year, stable_hash(seed, row.url), row.url))
    if count >= len(ordered):
        return list(ordered)
    step = len(ordered) / count
    picked = [ordered[min(int(index * step), len(ordered) - 1)] for index in range(count)]
    # Guard against collisions from int() flooring on short strata.
    seen: set[str] = set()
    unique: list[FrameRow] = []
    for row in picked:
        if row.url not in seen:
            seen.add(row.url)
            unique.append(row)
    for row in ordered:
        if len(unique) >= count:
            break
        if row.url not in seen:
            seen.add(row.url)
            unique.append(row)
    return unique


def build_locked_sample(
    frame: Sequence[FrameRow],
    seed: int = DEFAULT_SEED,
    allocation: dict[str, int] | None = None,
) -> tuple[list[FrameRow], dict[str, dict[str, Any]]]:
    """Return the sampled rows plus per-stratum bookkeeping (N, n, weight)."""

    quotas = dict(allocation or DECISION_ALLOCATION)
    by_decision: dict[str, dict[str, list[FrameRow]]] = {}
    for row in frame:
        by_decision.setdefault(row.pipeline_decision, {}).setdefault(row.route_lang or 'unknown', []).append(row)

    sampled: list[FrameRow] = []
    bookkeeping: dict[str, dict[str, Any]] = {}
    for decision in sorted(by_decision):
        lang_groups = by_decision[decision]
        sizes = {lang: len(rows) for lang, rows in lang_groups.items()}
        quota = quotas.get(decision, 0)
        per_lang = allocate_within_decision(sizes, quota)
        for lang in sorted(lang_groups):
            take = per_lang.get(lang, 0)
            drawn = systematic_draw(lang_groups[lang], take, seed)
            sampled.extend(drawn)
            stratum = f'{decision}|{lang}'
            bookkeeping[stratum] = {
                'pipeline_decision': decision,
                'route_lang': lang,
                'population_n': sizes[lang],
                'sampled_n': len(drawn),
                'inclusion_weight': round(sizes[lang] / len(drawn), 6) if drawn else None,
            }
    sampled.sort(key=lambda row: row.url)
    return sampled, bookkeeping


def compute_lock_hash(rows: Sequence[FrameRow]) -> str:
    """SHA-256 over the ordered URL list. This is the identity of the test set."""

    return stable_hash('locked_test_set', DESIGN_VERSION, [row.url for row in sorted(rows, key=lambda r: r.url)])


def _label_records(rows: Sequence[FrameRow]) -> Iterable[dict[str, Any]]:
    for index, row in enumerate(rows, start=1):
        yield {
            'row_id': f'{DESIGN_VERSION}-{index:04d}',
            'url': row.url,
            'source': row.source,
            'year': row.year,
            'route_lang': row.route_lang,
            'title': row.title,
            'snippet': row.snippet,
        }


def _prediction_records(
    rows: Sequence[FrameRow],
    bookkeeping: dict[str, dict[str, Any]],
) -> Iterable[dict[str, Any]]:
    for index, row in enumerate(rows, start=1):
        record: dict[str, Any] = {
            'row_id': f'{DESIGN_VERSION}-{index:04d}',
            'url': row.url,
            'stratum': row.stratum,
            'pipeline_decision': row.pipeline_decision,
            'inclusion_weight': (bookkeeping.get(row.stratum) or {}).get('inclusion_weight'),
        }
        record.update(row.predictions)
        yield record


def verify_locked_manifest(manifest_path: Path, labels_path: Path) -> bool:
    """Re-derive the lock hash from the labels file and compare to the manifest.

    Call this before scoring. A mismatch means the frozen set was edited, which
    invalidates it as a held-out set.
    """

    import csv

    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    with labels_path.open(encoding='utf-8', newline='') as handle:
        urls = [row['url'] for row in csv.DictReader(handle)]
    recomputed = stable_hash('locked_test_set', manifest['design_version'], sorted(urls))
    return recomputed == manifest['lock_hash']


def run_locked_test_set_stage(config: AppConfig) -> dict[str, Any]:
    """Draw, write and hash-lock the held-out test set. Refuses to overwrite."""

    outputs_dir = config.resolve_path('outputs_dir')
    ensure_directory(outputs_dir)
    labels_path = outputs_dir / f'{OUTPUT_STEM}_labels.csv'
    predictions_path = outputs_dir / f'{OUTPUT_STEM}_predictions.csv'
    manifest_path = outputs_dir / f'{OUTPUT_STEM}_manifest.json'

    if manifest_path.exists():
        # Refusing to overwrite is the entire point of a locked set.
        LOGGER.warning(
            'Locked test set already exists at %s; refusing to redraw. '
            'Bump DESIGN_VERSION if you genuinely need a new set.', manifest_path,
        )
        return json.loads(manifest_path.read_text(encoding='utf-8'))

    with connect_sqlite(config.sqlite_path) as connection:
        frame = load_frame(connection)

    sampled, bookkeeping = build_locked_sample(frame)
    lock_hash = compute_lock_hash(sampled)

    write_csv(labels_path, LABEL_COLUMNS, _label_records(sampled))
    write_csv(predictions_path, PREDICTION_COLUMNS, _prediction_records(sampled, bookkeeping))

    manifest = {
        'design_version': DESIGN_VERSION,
        'created_at': iso_now(),
        'seed': DEFAULT_SEED,
        'frame_table': 'raw_articles',
        'frame_size': len(frame),
        'sample_size': len(sampled),
        'target_size': DEFAULT_TARGET_SIZE,
        'decision_allocation': DECISION_ALLOCATION,
        'strata': bookkeeping,
        'lock_hash': lock_hash,
        'truth_vocabularies': {key: list(value) for key, value in TRUTH_VOCABULARIES.items()},
        'labels_file': labels_path.name,
        'predictions_file': predictions_path.name,
        'notes': (
            'Held-out test set. Draw once, label once, never tune against it. '
            'Metrics MUST be weighted by inclusion_weight to describe the inventory '
            'rather than the sample.'
        ),
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    LOGGER.info(
        'Locked test set written: %d rows from a frame of %d (hash %s)',
        len(sampled), len(frame), lock_hash[:12],
    )
    return manifest
