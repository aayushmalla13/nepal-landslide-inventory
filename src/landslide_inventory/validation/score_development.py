"""Validate and diagnose a labelled development set without claiming evaluation.

Development labels may be used to tune the pipeline, so their metrics are not
held-out performance estimates. This stage freezes the completed labels, writes
an error-review CSV, and records unweighted sample diagnostics only.
"""

from __future__ import annotations

import csv
import hashlib
import json
import logging
import re
import shutil
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from ..config import AppConfig
from ..db import connect_sqlite
from .common import iso_now, write_csv
from .development_set import DEFAULT_VERSION
from .locked_test_set import PREDICTION_COLUMNS, TRUTH_VOCABULARIES, load_frame
from .score_locked import (
    _metrics,
    _predicted_headline,
    _score_extraction_fields,
    _truth_headline,
    load_filled_labels,
    validate_vocabularies,
)

LOGGER = logging.getLogger(__name__)

METADATA_COLUMNS = (
    'row_id', 'url', 'source', 'year', 'route_lang', 'title', 'snippet'
)
TRIGGER_VOCABULARY = {'', 'rainfall', 'earthquake', 'anthropogenic', 'unknown'}
ERROR_COLUMNS = (
    'row_id', 'url', 'source', 'route_lang', 'title', 'error',
    'truth_headline', 'headline_pred', 'pipeline_decision', 'stratum',
    'specificity_reason', 'scope_reason', 'event_type_pred', 'hazard_type_pred',
    'typing_reason_pred', 'hazard_type_true', 'event_granularity_true',
    'article_role_true', 'notes',
)
PATTERN_FIELDS = (
    'pipeline_decision', 'stratum', 'route_lang', 'source',
    'hazard_type_true', 'event_granularity_true', 'article_role_true',
    'specificity_reason', 'scope_reason', 'event_type_pred',
    'hazard_type_pred', 'typing_reason_pred',
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))


def _validate_completed_labels(
    labels: Sequence[Mapping[str, str]],
    reference: Sequence[Mapping[str, str]],
) -> None:
    problems = validate_vocabularies(labels)
    if len(labels) != len(reference):
        problems.append(
            f'row count changed: completed={len(labels)} reference={len(reference)}'
        )
    completed_ids = [row.get('row_id', '') for row in labels]
    reference_ids = [row.get('row_id', '') for row in reference]
    if len(set(completed_ids)) != len(completed_ids):
        problems.append('completed labels contain duplicate row_id values')
    if completed_ids != reference_ids:
        problems.append('row order or row_id values differ from the frozen reference')
    for index, (label, original) in enumerate(zip(labels, reference, strict=False), 1):
        row_id = label.get('row_id') or f'row {index}'
        for field in METADATA_COLUMNS:
            if (label.get(field) or '') != (original.get(field) or ''):
                problems.append(f'{row_id}: protected field {field} was changed')
        for field in TRUTH_VOCABULARIES:
            if not (label.get(field) or '').strip():
                problems.append(f'{row_id}: {field} is blank')
        if not (label.get('annotator') or '').strip():
            problems.append(f'{row_id}: annotator is blank')
        date_value = (label.get('date_true') or '').strip()
        if date_value and re.fullmatch(r'\d{4}-\d{2}-\d{2}', date_value) is None:
            problems.append(f'{row_id}: date_true must be YYYY-MM-DD or blank')
        deaths = (label.get('deaths_true') or '').strip()
        if deaths and not deaths.isdigit():
            problems.append(f'{row_id}: deaths_true must be a whole number or blank')
        trigger = (label.get('trigger_true') or '').strip()
        if trigger not in TRIGGER_VOCABULARY:
            problems.append(f'{row_id}: trigger_true={trigger!r} is not canonical')
    if problems:
        raise ValueError(
            'Development labels are not ready:\n  ' + '\n  '.join(problems[:30])
        )


def _validate_predictions(
    labels: Sequence[Mapping[str, str]],
    predictions: Sequence[Mapping[str, str]],
) -> dict[str, Mapping[str, str]]:
    by_id = {row.get('row_id', ''): row for row in predictions}
    if len(by_id) != len(predictions):
        raise ValueError('Development predictions contain duplicate row_id values.')
    label_ids = {row.get('row_id', '') for row in labels}
    if set(by_id) != label_ids:
        raise ValueError('Development label and prediction row_id sets differ.')
    for label in labels:
        prediction = by_id[label.get('row_id', '')]
        if (label.get('url') or '') != (prediction.get('url') or ''):
            raise ValueError(
                f"{label.get('row_id', '?')}: label and prediction URLs differ."
            )
    return by_id


def _pattern_counts(rows: Sequence[Mapping[str, str]]) -> dict[str, dict[str, int]]:
    return {
        field: dict(
            Counter((row.get(field) or '<blank>') for row in rows).most_common()
        )
        for field in PATTERN_FIELDS
    }


def diagnose(
    labels: Sequence[Mapping[str, str]],
    predictions: Mapping[str, Mapping[str, str]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Return development-only diagnostics and every headline disagreement."""

    cells = {'tp': 0.0, 'fp': 0.0, 'fn': 0.0, 'tn': 0.0}
    undecidable = 0
    errors: list[dict[str, Any]] = []
    per_stratum: dict[str, Counter[str]] = defaultdict(Counter)
    for label in labels:
        prediction = predictions[label.get('row_id', '')]
        truth = _truth_headline(label)
        if truth is None:
            undecidable += 1
            per_stratum[prediction.get('stratum', '?')]['undecidable'] += 1
            continue
        predicted = _predicted_headline(prediction)
        cell = 'tp' if truth and predicted else 'fn' if truth else 'fp' if predicted else 'tn'
        cells[cell] += 1.0
        per_stratum[prediction.get('stratum', '?')][cell] += 1
        if cell not in {'fp', 'fn'}:
            continue
        errors.append(
            {
                'row_id': label.get('row_id', ''),
                'url': label.get('url', ''),
                'source': label.get('source', ''),
                'route_lang': label.get('route_lang', ''),
                'title': label.get('title', ''),
                'error': 'false_positive' if cell == 'fp' else 'false_negative',
                'truth_headline': int(truth),
                'headline_pred': int(predicted),
                'pipeline_decision': prediction.get('pipeline_decision', ''),
                'stratum': prediction.get('stratum', ''),
                'specificity_reason': prediction.get('specificity_reason', ''),
                'scope_reason': prediction.get('scope_reason', ''),
                'event_type_pred': prediction.get('event_type_pred', ''),
                'hazard_type_pred': prediction.get('hazard_type_pred', ''),
                'typing_reason_pred': prediction.get('typing_reason_pred', ''),
                'hazard_type_true': label.get('hazard_type_true', ''),
                'event_granularity_true': label.get('event_granularity_true', ''),
                'article_role_true': label.get('article_role_true', ''),
                'notes': label.get('notes', ''),
            }
        )
    false_positives = [row for row in errors if row['error'] == 'false_positive']
    false_negatives = [row for row in errors if row['error'] == 'false_negative']
    extraction_raw = _score_extraction_fields(labels, predictions)
    extraction = {
        field: {
            'truth_available_n': values['truth_available_n'],
            'predicted_nonblank_n': values['predicted_nonblank_n'],
            'exact_n': values['exact_n'],
            'coverage': values['weighted_coverage'],
            'exact_accuracy': values['unweighted_exact_accuracy'],
        }
        for field, values in extraction_raw.items()
    }
    report = {
        'design': 'development_only_not_for_evaluation',
        'warning': (
            'Use these sample diagnostics to locate error patterns only. Do not '
            'report them as held-out or population performance.'
        ),
        'scoring_definition': {
            'truth': (
                'is_landslide_event=yes AND in_nepal=yes AND hazard_type in '
                '{landslide,debris_flow,rockfall} AND event_granularity=single'
            ),
            'prediction': (
                'retained Class 1/2 AND typed as headline landslide; canonical '
                'road_obstruction, aggregate, and other-hazard types excluded'
            ),
        },
        'rows': len(labels),
        'scored_rows': int(sum(cells.values())),
        'undecidable_rows': undecidable,
        'sample_confusion': {key: int(value) for key, value in cells.items()},
        'sample_diagnostic_metrics': _metrics(cells),
        'error_counts': {
            'false_positive': len(false_positives),
            'false_negative': len(false_negatives),
        },
        'false_positive_patterns': _pattern_counts(false_positives),
        'false_negative_patterns': _pattern_counts(false_negatives),
        'extraction_diagnostics': extraction,
        'per_stratum': {
            key: dict(value) for key, value in sorted(per_stratum.items())
        },
    }
    return report, errors


def run_score_development_stage(config: AppConfig) -> dict[str, Any]:
    """Freeze completed development labels and write diagnostic artifacts."""

    settings = dict(config.raw.get('validation', {}).get('development_set', {}))
    version = str(settings.get('version', DEFAULT_VERSION))
    stem = f'development_set_{version}'
    output_dir = config.resolve_path('outputs_dir')
    reference_path = output_dir / f'{stem}_labels.csv'
    working_path = output_dir / f'{stem}_LABEL_HERE.csv'
    predictions_path = output_dir / f'{stem}_predictions.csv'
    final_labels_path = output_dir / f'{stem}_labels_final.csv'
    errors_path = output_dir / f'{stem}_errors.csv'
    report_path = output_dir / f'{stem}_diagnostics.json'
    for required in (reference_path, working_path, predictions_path):
        if not required.exists():
            raise FileNotFoundError(f'Missing development artifact: {required}')

    labels = load_filled_labels(working_path)
    reference = load_filled_labels(reference_path)
    _validate_completed_labels(labels, reference)
    prediction_rows = _read_csv(predictions_path)
    predictions = _validate_predictions(labels, prediction_rows)
    report, errors = diagnose(labels, predictions)

    if final_labels_path.exists():
        if final_labels_path.read_bytes() != working_path.read_bytes():
            raise FileExistsError(
                f'Frozen development labels differ from {working_path}; refusing '
                'to overwrite the final snapshot.'
            )
    else:
        shutil.copyfile(working_path, final_labels_path)
    write_csv(errors_path, ERROR_COLUMNS, errors)
    report.update(
        {
            'created_at': iso_now(),
            'version': version,
            'labels_file': final_labels_path.name,
            'labels_sha256': _sha256(final_labels_path),
            'predictions_file': predictions_path.name,
            'predictions_sha256': _sha256(predictions_path),
            'errors_file': errors_path.name,
            'errors_sha256': _sha256(errors_path),
        }
    )
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8'
    )
    LOGGER.info(
        'Development diagnostics: scored=%d undecidable=%d fp=%d fn=%d',
        report['scored_rows'], report['undecidable_rows'],
        report['error_counts']['false_positive'],
        report['error_counts']['false_negative'],
    )
    LOGGER.info('Development report written to %s', report_path)
    return report


def run_refresh_development_predictions_stage(config: AppConfig) -> dict[str, Any]:
    """Write post-tuning predictions without altering the baseline snapshot."""

    settings = dict(config.raw.get('validation', {}).get('development_set', {}))
    version = str(settings.get('version', DEFAULT_VERSION))
    stem = f'development_set_{version}'
    output_dir = config.resolve_path('outputs_dir')
    reference_path = output_dir / f'{stem}_labels.csv'
    final_labels_path = output_dir / f'{stem}_labels_final.csv'
    baseline_path = output_dir / f'{stem}_predictions.csv'
    tuned_path = output_dir / f'{stem}_predictions_tuned.csv'
    for required in (reference_path, final_labels_path, baseline_path):
        if not required.exists():
            raise FileNotFoundError(f'Missing development artifact: {required}')

    labels = load_filled_labels(final_labels_path)
    reference = load_filled_labels(reference_path)
    _validate_completed_labels(labels, reference)
    baseline_rows = _read_csv(baseline_path)
    baseline = _validate_predictions(labels, baseline_rows)
    with connect_sqlite(config.sqlite_path) as connection:
        current = {row.url: row for row in load_frame(connection)}

    records: list[dict[str, Any]] = []
    decisions_changed = 0
    headlines_changed = 0
    for label in labels:
        row_id = label.get('row_id', '')
        url = label.get('url', '')
        frame_row = current.get(url)
        if frame_row is None:
            raise ValueError(f'{row_id}: URL is no longer present in the sampling frame')
        before = baseline[row_id]
        record: dict[str, Any] = {
            'row_id': row_id,
            'url': url,
            # Sampling-design fields belong to the original draw and stay
            # fixed even when the pipeline's current decision changes.
            'stratum': before.get('stratum', ''),
            'pipeline_decision': frame_row.pipeline_decision,
            'inclusion_weight': before.get('inclusion_weight', ''),
        }
        record.update(frame_row.predictions)
        records.append(record)
        decisions_changed += int(
            before.get('pipeline_decision', '') != frame_row.pipeline_decision
        )
        headlines_changed += int(
            str(before.get('headline_pred', ''))
            != str(frame_row.predictions.get('headline_pred', ''))
        )

    write_csv(tuned_path, PREDICTION_COLUMNS, records)
    result = {
        'rows': len(records),
        'decisions_changed': decisions_changed,
        'headlines_changed': headlines_changed,
        'path': str(tuned_path),
        'sha256': _sha256(tuned_path),
    }
    LOGGER.info(
        'Refreshed %d development predictions to %s; decisions changed=%d, '
        'headline predictions changed=%d',
        len(records), tuned_path, decisions_changed, headlines_changed,
    )
    return result


def run_score_development_tuned_stage(config: AppConfig) -> dict[str, Any]:
    """Score the separate post-tuning development prediction snapshot."""

    settings = dict(config.raw.get('validation', {}).get('development_set', {}))
    version = str(settings.get('version', DEFAULT_VERSION))
    stem = f'development_set_{version}'
    output_dir = config.resolve_path('outputs_dir')
    reference_path = output_dir / f'{stem}_labels.csv'
    labels_path = output_dir / f'{stem}_labels_final.csv'
    predictions_path = output_dir / f'{stem}_predictions_tuned.csv'
    errors_path = output_dir / f'{stem}_errors_tuned.csv'
    report_path = output_dir / f'{stem}_diagnostics_tuned.json'
    for required in (reference_path, labels_path, predictions_path):
        if not required.exists():
            raise FileNotFoundError(f'Missing development artifact: {required}')

    labels = load_filled_labels(labels_path)
    reference = load_filled_labels(reference_path)
    _validate_completed_labels(labels, reference)
    prediction_rows = _read_csv(predictions_path)
    predictions = _validate_predictions(labels, prediction_rows)
    report, errors = diagnose(labels, predictions)
    write_csv(errors_path, ERROR_COLUMNS, errors)
    report.update(
        {
            'created_at': iso_now(),
            'version': version,
            'comparison': 'post_tuning_development_snapshot',
            'labels_file': labels_path.name,
            'labels_sha256': _sha256(labels_path),
            'predictions_file': predictions_path.name,
            'predictions_sha256': _sha256(predictions_path),
            'errors_file': errors_path.name,
            'errors_sha256': _sha256(errors_path),
        }
    )
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8'
    )
    LOGGER.info(
        'Tuned development diagnostics: scored=%d undecidable=%d fp=%d fn=%d',
        report['scored_rows'], report['undecidable_rows'],
        report['error_counts']['false_positive'],
        report['error_counts']['false_negative'],
    )
    LOGGER.info('Tuned development report written to %s', report_path)
    return report
