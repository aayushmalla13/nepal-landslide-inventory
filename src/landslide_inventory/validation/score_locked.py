"""Score the frozen, decision-stratified test set without changing its labels.

The primary target is the headline definition frozen in
``docs/ANNOTATION_RUBRIC.md``: a single Nepal landslide-family event. Pipeline
positives are retained Class-1 or Class-2 articles that also pass the same
hazard and road/aggregate typing used by the canonical inventory.

District and event-date extraction are reported separately. They are not part
of event-detection truth, because making them prerequisites would confound an
extractor failure with whether the article describes a real event.
"""

from __future__ import annotations

import csv
import hashlib
import json
import logging
import random
import shutil
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from ..config import AppConfig
from ..db import connect_sqlite
from ..unify.event_typing import classify_event_type
from ..utils import ensure_directory
from .common import iso_now, write_csv
from .locked_test_set import (
    PREDICTION_COLUMNS,
    TRUTH_VOCABULARIES,
    locked_output_stem,
    verify_locked_manifest,
)

LOGGER = logging.getLogger(__name__)

PRIMARY_FIELD = 'is_landslide_event_true'
BOOTSTRAP_REPLICATES = 2000
BOOTSTRAP_SEED = 20260809
MIN_EXTRACTION_TRUTH_ROWS = 30
TYPING_FIELDS = (
    'event_type_pred',
    'hazard_type_pred',
    'typing_reason_pred',
    'extraction_basis_pred',
    'headline_pred',
)


def load_filled_labels(path: Path) -> list[dict[str, str]]:
    """Load a UTF-8 label CSV, accepting an optional spreadsheet BOM."""

    with path.open(encoding='utf-8-sig', newline='') as handle:
        return [row for row in csv.DictReader(handle)]


def validate_vocabularies(rows: Sequence[Mapping[str, str]]) -> list[str]:
    """Return every out-of-vocabulary truth value found. Empty means clean."""

    problems: list[str] = []
    for row in rows:
        for field, allowed in TRUTH_VOCABULARIES.items():
            value = (row.get(field) or '').strip()
            if value and value not in allowed:
                problems.append(
                    f"{row.get('row_id', '?')}: {field}={value!r} "
                    f"not in {sorted(allowed)}"
                )
    return problems


def _truth_headline(row: Mapping[str, str]) -> bool | None:
    """Return strict headline truth, or ``None`` when it is undecidable.

    Only ``event_granularity_true=single`` is positive. Multi-event articles,
    roundups, and not-applicable rows are negatives, exactly as specified by
    the frozen annotation rubric.
    """

    event = (row.get('is_landslide_event_true') or '').strip()
    nepal = (row.get('in_nepal_true') or '').strip()
    hazard = (row.get('hazard_type_true') or '').strip()
    granularity = (row.get('event_granularity_true') or '').strip()
    if not event:
        return None
    if event == 'no' or nepal == 'no':
        return False
    if event == 'unclear' or nepal in {'', 'unclear'}:
        return None
    if hazard in {'avalanche', 'flood', 'other_hazard', 'not_a_hazard'}:
        return False
    if hazard in {'', 'unclear'}:
        return None
    if granularity == 'unclear':
        return None
    return (
        event == 'yes'
        and nepal == 'yes'
        and hazard in {'landslide', 'debris_flow', 'rockfall'}
        and granularity == 'single'
    )


def _predicted_headline(prediction: Mapping[str, str]) -> bool:
    """Return the typed article-level headline decision."""

    raw_value = prediction.get('headline_pred')
    value = '' if raw_value is None else str(raw_value).strip().casefold()
    if value in {'1', 'true', 'yes'}:
        return True
    if value in {'0', 'false', 'no'}:
        return False
    raise ValueError(
        f"Prediction {prediction.get('row_id', '?')} has no typed headline_pred. "
        'Refresh the locked prediction snapshot before scoring.'
    )


def _weight(prediction: Mapping[str, str]) -> float:
    try:
        return float(prediction.get('inclusion_weight') or 1.0)
    except (TypeError, ValueError):
        return 1.0


def _metrics(cells: Mapping[str, float]) -> dict[str, float | None]:
    tp, fp, fn = cells['tp'], cells['fp'], cells['fn']
    precision = tp / (tp + fp) if (tp + fp) else None
    recall = tp / (tp + fn) if (tp + fn) else None
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision is not None
        and recall is not None
        and (precision + recall)
        else None
    )
    return {'precision': precision, 'recall': recall, 'f1': f1}


def _percentile(values: Sequence[float], probability: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError('Cannot calculate a percentile from an empty sample.')
    position = probability * (len(ordered) - 1)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def _stratified_bootstrap_ci(
    records: Sequence[Mapping[str, Any]],
    *,
    replicates: int = BOOTSTRAP_REPLICATES,
    seed: int = BOOTSTRAP_SEED,
) -> dict[str, list[float] | None]:
    """Approximate weighted 95% CIs by resampling within design strata."""

    groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for record in records:
        groups[str(record['stratum'])].append(record)
    if not groups or replicates <= 0:
        return {key: None for key in ('precision', 'recall', 'f1')}

    rng = random.Random(seed)
    draws: dict[str, list[float]] = defaultdict(list)
    for _index in range(replicates):
        cells = {'tp': 0.0, 'fp': 0.0, 'fn': 0.0, 'tn': 0.0}
        for group in groups.values():
            for record in rng.choices(group, k=len(group)):
                cells[str(record['cell'])] += float(record['weight'])
        for key, value in _metrics(cells).items():
            if value is not None:
                draws[key].append(value)
    return {
        key: (
            [
                _percentile(draws[key], 0.025),
                _percentile(draws[key], 0.975),
            ]
            if draws[key]
            else None
        )
        for key in ('precision', 'recall', 'f1')
    }


def _normalize_exact(value: str | None) -> str:
    return ' '.join((value or '').strip().casefold().split())


def _score_extraction_fields(
    labels: Sequence[Mapping[str, str]],
    predictions: Mapping[str, Mapping[str, str]],
) -> dict[str, dict[str, float | int | None]]:
    """Score district and date separately among true headline events."""

    field_pairs = {
        'district': ('district_true', 'district_pred'),
        'event_date': ('date_true', 'event_date_pred'),
    }
    output: dict[str, dict[str, float | int | None]] = {}
    for name, (truth_field, prediction_field) in field_pairs.items():
        eligible_n = predicted_n = exact_n = 0
        eligible_weight = predicted_weight = exact_weight = 0.0
        for label in labels:
            if _truth_headline(label) is not True:
                continue
            truth_value = _normalize_exact(label.get(truth_field))
            if not truth_value:
                continue
            prediction = predictions.get(label.get('row_id', ''))
            if prediction is None:
                continue
            weight = _weight(prediction)
            predicted_value = _normalize_exact(prediction.get(prediction_field))
            eligible_n += 1
            eligible_weight += weight
            if predicted_value:
                predicted_n += 1
                predicted_weight += weight
            if predicted_value == truth_value:
                exact_n += 1
                exact_weight += weight
        output[name] = {
            'truth_available_n': eligible_n,
            'predicted_nonblank_n': predicted_n,
            'exact_n': exact_n,
            'reportable': eligible_n >= MIN_EXTRACTION_TRUTH_ROWS,
            'minimum_truth_rows': MIN_EXTRACTION_TRUTH_ROWS,
            'weighted_coverage': (
                predicted_weight / eligible_weight if eligible_weight else None
            ),
            'weighted_exact_accuracy': (
                exact_weight / eligible_weight if eligible_weight else None
            ),
            'unweighted_exact_accuracy': (
                exact_n / eligible_n if eligible_n else None
            ),
        }
    return output


def score(
    labels: Sequence[Mapping[str, str]],
    predictions: Mapping[str, Mapping[str, str]],
    *,
    bootstrap_replicates: int = BOOTSTRAP_REPLICATES,
) -> dict[str, Any]:
    """Return weighted headline classification and separate extraction metrics."""

    weighted_cells = {'tp': 0.0, 'fp': 0.0, 'fn': 0.0, 'tn': 0.0}
    raw_cells = {'tp': 0, 'fp': 0, 'fn': 0, 'tn': 0}
    per_stratum: dict[str, dict[str, int]] = defaultdict(
        lambda: {'labelled': 0, 'total': 0}
    )
    undecidable = 0
    primary_answered = 0
    examples: dict[str, list[str]] = {'fp': [], 'fn': []}
    bootstrap_records: list[dict[str, Any]] = []

    for label in labels:
        row_id = label.get('row_id', '')
        prediction = predictions.get(row_id)
        if prediction is None:
            continue
        stratum = prediction.get('stratum', '?')
        per_stratum[stratum]['total'] += 1
        if not (label.get(PRIMARY_FIELD) or '').strip():
            continue
        primary_answered += 1
        per_stratum[stratum]['labelled'] += 1

        truth = _truth_headline(label)
        if truth is None:
            undecidable += 1
            continue
        predicted = _predicted_headline(prediction)
        weight = _weight(prediction)
        cell = 'tp' if truth and predicted else 'fn' if truth else 'fp' if predicted else 'tn'
        weighted_cells[cell] += weight
        raw_cells[cell] += 1
        bootstrap_records.append(
            {'stratum': stratum, 'cell': cell, 'weight': weight}
        )
        if cell in examples and len(examples[cell]) < 12:
            examples[cell].append(label.get('url', row_id))

    return {
        'scoring_definition': {
            'truth': (
                'is_landslide_event=yes AND in_nepal=yes AND hazard_type in '
                '{landslide,debris_flow,rockfall} AND event_granularity=single'
            ),
            'prediction': (
                'pipeline_decision in {kept_class1,kept_class2} AND '
                'event_type_pred=landslide AND hazard_type_pred in '
                '{landslide,debris_flow,rockfall}'
            ),
            'unit': 'article-level headline classification',
        },
        'primary_answered_rows': primary_answered,
        'labelled_rows': sum(raw_cells.values()),
        'undecidable_rows': undecidable,
        'weighted_confusion': {
            key: round(value, 1) for key, value in weighted_cells.items()
        },
        'unweighted_confusion': dict(raw_cells),
        'weighted': _metrics(weighted_cells),
        'weighted_ci95_stratified_bootstrap': _stratified_bootstrap_ci(
            bootstrap_records,
            replicates=bootstrap_replicates,
        ),
        'bootstrap': {
            'method': 'within-stratum weighted percentile bootstrap',
            'replicates': bootstrap_replicates,
            'seed': BOOTSTRAP_SEED,
            'note': (
                'Approximate design-aware interval; resampling respects the locked '
                'decision-by-language strata and uses inclusion weights.'
            ),
        },
        'unweighted_sample_only': _metrics(
            {key: float(value) for key, value in raw_cells.items()}
        ),
        'extraction_among_true_headline_articles': _score_extraction_fields(
            labels, predictions
        ),
        'per_stratum_coverage': {
            key: dict(value) for key, value in sorted(per_stratum.items())
        },
        'false_positive_examples': examples['fp'],
        'false_negative_examples': examples['fn'],
    }


def _typing_snapshot_rows(
    config: AppConfig,
    predictions: Sequence[dict[str, str]],
) -> tuple[list[dict[str, Any]], bool]:
    """Backfill typed prediction fields once without consulting truth labels."""

    if predictions and all(
        all((row.get(field) or '').strip() for field in TYPING_FIELDS)
        for row in predictions
    ):
        return [dict(row) for row in predictions], False

    urls = [row.get('url', '') for row in predictions]
    placeholders = ','.join('?' for _url in urls)
    with connect_sqlite(config.sqlite_path) as connection:
        records = connection.execute(
            f"""
            SELECT r.url, r.title, r.text, e.deaths, e.missing, e.injured
            FROM raw_articles AS r
            LEFT JOIN article_events AS e ON e.url = r.url
            WHERE r.url IN ({placeholders})
            """,
            urls,
        ).fetchall()
    by_url = {row['url']: dict(row) for row in records}
    missing = sorted(set(urls) - set(by_url))
    if missing:
        raise ValueError(
            f'{len(missing)} locked prediction URLs are missing from raw_articles; '
            f'first missing URL: {missing[0]}'
        )

    enriched: list[dict[str, Any]] = []
    for prediction in predictions:
        row = by_url[prediction['url']]
        typing = classify_event_type(
            title=row.get('title'),
            text=row.get('text'),
            deaths=row.get('deaths'),
            missing=row.get('missing'),
            injured=row.get('injured'),
        )
        item: dict[str, Any] = dict(prediction)
        item.update(
            {
                'event_type_pred': typing.event_type,
                'hazard_type_pred': typing.hazard_type,
                'typing_reason_pred': typing.reason,
                'event_granularity_pred': typing.event_granularity,
                'article_role_pred': typing.article_role,
                'extraction_basis_pred': typing.extraction_basis,
                'headline_pred': int(
                    prediction.get('pipeline_decision')
                    in {'kept_class1', 'kept_class2'}
                    and typing.in_headline_counts
                ),
            }
        )
        enriched.append(item)
    return enriched, True


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _format(report: Mapping[str, Any]) -> str:
    lines = [
        (
            f"Primary answers: {report['primary_answered_rows']} | "
            f"decidable headline rows scored: {report['labelled_rows']} | "
            f"undecidable: {report['undecidable_rows']}"
        ),
        '',
        '  Weighted article-level headline classification:',
    ]
    intervals = report['weighted_ci95_stratified_bootstrap']
    for key in ('precision', 'recall', 'f1'):
        value = report['weighted'][key]
        interval = intervals.get(key)
        if value is None:
            lines.append(f'    {key:10s} n/a')
        elif interval:
            lines.append(
                f'    {key:10s} {value:.3f}  '
                f'(stratified bootstrap 95% CI {interval[0]:.3f}-{interval[1]:.3f})'
            )
        else:
            lines.append(f'    {key:10s} {value:.3f}')
    lines.extend(['', '  Extraction among true headline articles:'])
    for field, result in report['extraction_among_true_headline_articles'].items():
        accuracy = result['weighted_exact_accuracy']
        coverage = result['weighted_coverage']
        if not result['reportable']:
            lines.append(
                f"    {field:10s} not reportable: truth available "
                f"n={result['truth_available_n']} "
                f"(minimum {result['minimum_truth_rows']})"
            )
        elif accuracy is not None and coverage is not None:
            lines.append(
                f"    {field:10s} exact={accuracy:.3f} coverage={coverage:.3f} "
                f"(truth available n={result['truth_available_n']})"
            )
        else:
            lines.append(f'    {field:10s} n/a')
    lines.extend(['', '  Stratum coverage (primary answered / sampled):'])
    for stratum, counts in report['per_stratum_coverage'].items():
        lines.append(
            f"    {stratum:28s} {counts['labelled']:3d} / {counts['total']:3d}"
        )
    return '\n'.join(lines)


def run_score_locked_stage(config: AppConfig) -> dict[str, Any]:
    """Validate frozen inputs, snapshot typing, score, and write the report."""

    outputs_dir = config.resolve_path('outputs_dir')
    ensure_directory(outputs_dir)
    stem = locked_output_stem(config)
    edited = outputs_dir / f'{stem}_LABEL_HERE.csv'
    fallback = outputs_dir / f'{stem}_labels_filled.csv'
    labels_path = edited if edited.exists() else fallback
    reference_path = outputs_dir / f'{stem}_labels.csv'
    predictions_path = outputs_dir / f'{stem}_predictions.csv'
    manifest_path = outputs_dir / f'{stem}_manifest.json'
    frozen_labels_path = outputs_dir / f'{stem}_labels_final.csv'

    if not labels_path.exists():
        raise FileNotFoundError(f'No labelled file at {edited} or {fallback}.')
    for required in (reference_path, predictions_path, manifest_path):
        if not required.exists():
            raise FileNotFoundError(f'Missing locked-test artifact: {required}')
    if not verify_locked_manifest(manifest_path, reference_path):
        raise ValueError(
            f'{reference_path.name} no longer matches its manifest lock hash.'
        )
    if frozen_labels_path.exists() and _sha256(labels_path) != _sha256(frozen_labels_path):
        raise ValueError(
            f'{labels_path.name} no longer matches frozen {frozen_labels_path.name}; '
            'restore the frozen labels before scoring.'
        )

    labels = load_filled_labels(labels_path)
    reference = load_filled_labels(reference_path)
    expected = {(row['row_id'], row['url']) for row in reference}
    observed = {(row.get('row_id', ''), row.get('url', '')) for row in labels}
    if len(labels) != len(reference) or observed != expected:
        raise ValueError(
            'The labelled row IDs/URLs do not match the locked reference file.'
        )
    missing_primary = [
        row.get('row_id', '?')
        for row in labels
        if not (row.get(PRIMARY_FIELD) or '').strip()
    ]
    if missing_primary:
        raise ValueError(
            f'{len(missing_primary)} rows have blank {PRIMARY_FIELD}; '
            f'first: {missing_primary[0]}. Finish labeling before scoring.'
        )
    missing_controlled = [
        f"{row.get('row_id', '?')}: {field}"
        for row in labels
        for field in TRUTH_VOCABULARIES
        if not (row.get(field) or '').strip()
    ]
    if missing_controlled:
        raise ValueError(
            f'{len(missing_controlled)} controlled truth cells are blank; '
            f'first: {missing_controlled[0]}. Use a vocabulary value or unclear.'
        )
    problems = validate_vocabularies(labels)
    if problems:
        raise ValueError(
            'Out-of-vocabulary truth values found:\n  ' + '\n  '.join(problems[:20])
        )

    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    expected_prediction_hash = manifest.get('predictions_sha256')
    if (
        expected_prediction_hash
        and _sha256(predictions_path) != expected_prediction_hash
    ):
        raise ValueError(
            f'{predictions_path.name} changed after the locked draw. Restore the '
            'frozen prediction snapshot before scoring.'
        )
    with predictions_path.open(encoding='utf-8', newline='') as handle:
        prediction_rows = list(csv.DictReader(handle))
    prediction_rows, enriched = _typing_snapshot_rows(config, prediction_rows)
    if enriched:
        write_csv(predictions_path, PREDICTION_COLUMNS, prediction_rows)
        LOGGER.info(
            'Added frozen event/hazard typing to %d locked predictions',
            len(prediction_rows),
        )
    predictions = {row['row_id']: row for row in prediction_rows}
    if set(predictions) != {row['row_id'] for row in reference}:
        raise ValueError('Prediction row IDs do not match the locked reference file.')

    if not frozen_labels_path.exists():
        shutil.copyfile(labels_path, frozen_labels_path)
        LOGGER.info('Frozen completed labels at %s', frozen_labels_path)

    report = score(labels, predictions)
    report.update(
        {
            'generated_at': iso_now(),
            'labels_file': labels_path.name,
            'labels_sha256': _sha256(labels_path),
            'predictions_file': predictions_path.name,
            'predictions_sha256': _sha256(predictions_path),
        }
    )

    report_path = outputs_dir / f'{stem}_score.json'
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8',
    )
    for line in _format(report).splitlines():
        LOGGER.info(line)
    LOGGER.info('Report written to %s', report_path)
    return report
