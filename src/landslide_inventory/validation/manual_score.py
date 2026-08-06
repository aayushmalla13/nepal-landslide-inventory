"""Scoring helpers for the completed manual verification pack."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Callable

from ..config import AppConfig
from ..gazetteer import normalize_district
from ..gazetteer_municipality import normalize_municipality
from ..utils import ensure_directory
from .common import is_truth_filled, iso_now


CLASS_LABELS = ('1', '2', '3')


def run_manual_score_stage(config: AppConfig) -> int:
    """Score the completed manual verification sample and write reports."""

    sample_path = config.resolve_path('outputs_dir') / 'manual_verification_sample.csv'
    rows = load_manual_labels(sample_path)
    metrics = compute_manual_metrics(rows)
    output_dir = config.resolve_path('outputs_dir')
    ensure_directory(output_dir)
    metrics_path = output_dir / 'manual_metrics.json'
    report_path = output_dir / 'manual_report.md'
    metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2, sort_keys=True), encoding='utf-8')
    report_path.write_text(build_manual_report(metrics), encoding='utf-8')
    return int(metrics['labeled_rows'])


def load_manual_labels(path: Path) -> list[dict[str, str]]:
    """Load labeled manual verification rows from CSV."""

    with path.open('r', encoding='utf-8', newline='') as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def compute_manual_metrics(rows: list[dict[str, str]]) -> dict[str, Any]:
    """Compute manual validation metrics from a completed labeling CSV."""

    labeled_rows = [row for row in rows if is_truth_filled(row.get('class_true'))]
    if not labeled_rows:
        raise ValueError('manual_verification_sample.csv has no labeled rows yet')

    class_metrics = compute_classification_metrics(labeled_rows)
    district_metrics = compute_exact_field_metrics(labeled_rows, 'district_pred', 'district_true')
    municipality_metrics = compute_exact_field_metrics(labeled_rows, 'municipality_pred', 'municipality_true')
    date_metrics = compute_exact_field_metrics(labeled_rows, 'event_date_pred', 'date_true')
    deaths_metrics = compute_deaths_metrics(labeled_rows)
    trigger_metrics = compute_trigger_metrics(labeled_rows)

    return {
        'generated_at': iso_now(),
        'labeled_rows': len(labeled_rows),
        'classification': class_metrics,
        'district': district_metrics,
        'municipality': municipality_metrics,
        'date': date_metrics,
        'deaths': deaths_metrics,
        'trigger': trigger_metrics,
    }


def compute_classification_metrics(rows: list[dict[str, str]]) -> dict[str, Any]:
    """Compute macro precision/recall/F1 for class labels."""

    per_class: dict[str, dict[str, float]] = {}
    for label in CLASS_LABELS:
        tp = sum(1 for row in rows if row.get('class_pred', '').strip() == label and row.get('class_true', '').strip() == label)
        fp = sum(1 for row in rows if row.get('class_pred', '').strip() == label and row.get('class_true', '').strip() != label)
        fn = sum(1 for row in rows if row.get('class_pred', '').strip() != label and row.get('class_true', '').strip() == label)
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
        per_class[label] = {'precision': precision, 'recall': recall, 'f1': f1}
    macro = {
        metric: sum(values[metric] for values in per_class.values()) / len(CLASS_LABELS)
        for metric in ('precision', 'recall', 'f1')
    }
    return {'per_class': per_class, 'macro': macro}


def compute_exact_field_metrics(rows: list[dict[str, str]], pred_field: str, true_field: str) -> dict[str, Any]:
    """Compute exact-match accuracy and prediction missing rate on labeled rows."""

    labeled = [row for row in rows if is_truth_filled(row.get(true_field))]
    if not labeled:
        return {'labeled_rows': 0, 'accuracy': None, 'missing_rate': None}
    comparator = _field_comparator(pred_field, true_field)
    exact = sum(1 for row in labeled if comparator(row.get(pred_field, ''), row.get(true_field, '')))
    missing = sum(1 for row in labeled if not is_truth_filled(row.get(pred_field)))
    return {
        'labeled_rows': len(labeled),
        'accuracy': exact / len(labeled),
        'missing_rate': missing / len(labeled),
    }


def compute_deaths_metrics(rows: list[dict[str, str]]) -> dict[str, Any]:
    """Compute exact and +/-1 tolerant deaths metrics."""

    labeled = [row for row in rows if is_truth_filled(row.get('deaths_true'))]
    if not labeled:
        return {'labeled_rows': 0, 'exact_match_rate': None, 'within_one_rate': None, 'missing_rate': None}
    exact = 0
    within_one = 0
    missing = 0
    for row in labeled:
        pred_raw = row.get('deaths_pred', '').strip()
        true_value = int(row['deaths_true'].strip())
        if pred_raw == '' and true_value != 0:
            missing += 1
            continue
        pred_value = int(pred_raw or '0')
        if pred_value == true_value:
            exact += 1
        if abs(pred_value - true_value) <= 1:
            within_one += 1
    return {
        'labeled_rows': len(labeled),
        'exact_match_rate': exact / len(labeled),
        'within_one_rate': within_one / len(labeled),
        'missing_rate': missing / len(labeled),
    }


def compute_trigger_metrics(rows: list[dict[str, str]]) -> dict[str, Any]:
    """Compute trigger accuracy and confusion counts."""

    labeled = [row for row in rows if is_truth_filled(row.get('trigger_true'))]
    if not labeled:
        return {'labeled_rows': 0, 'accuracy': None, 'confusion_matrix': {}}
    exact = sum(1 for row in labeled if row.get('trigger_pred', '').strip() == row.get('trigger_true', '').strip())
    confusion: dict[str, dict[str, int]] = {}
    for row in labeled:
        truth = row['trigger_true'].strip()
        pred = row.get('trigger_pred', '').strip() or '<missing>'
        confusion.setdefault(truth, {})
        confusion[truth][pred] = confusion[truth].get(pred, 0) + 1
    return {
        'labeled_rows': len(labeled),
        'accuracy': exact / len(labeled),
        'confusion_matrix': confusion,
    }


def build_manual_report(metrics: dict[str, Any]) -> str:
    """Build a human-readable markdown report from scored metrics."""

    lines = [
        '# Manual Verification Report',
        '',
        f"Generated at: {metrics['generated_at']}",
        f"Labeled rows: {metrics['labeled_rows']}",
        '',
        '## Classification',
        f"Macro precision: {metrics['classification']['macro']['precision']:.3f}",
        f"Macro recall: {metrics['classification']['macro']['recall']:.3f}",
        f"Macro F1: {metrics['classification']['macro']['f1']:.3f}",
        '',
        '## Field Accuracy',
        f"District accuracy: {metrics['district']['accuracy']}",
        f"District missing rate: {metrics['district']['missing_rate']}",
        f"Municipality accuracy: {metrics['municipality']['accuracy']}",
        f"Municipality missing rate: {metrics['municipality']['missing_rate']}",
        f"Date accuracy: {metrics['date']['accuracy']}",
        f"Date missing rate: {metrics['date']['missing_rate']}",
        f"Deaths exact match: {metrics['deaths']['exact_match_rate']}",
        f"Deaths within +/-1: {metrics['deaths']['within_one_rate']}",
        f"Trigger accuracy: {metrics['trigger']['accuracy']}",
    ]
    return '\n'.join(lines) + '\n'


def _field_comparator(pred_field: str, true_field: str) -> Callable[[str, str], bool]:
    if pred_field == 'district_pred' and true_field == 'district_true':
        return _district_matches
    if pred_field == 'municipality_pred' and true_field == 'municipality_true':
        return _municipality_matches
    if pred_field == 'event_date_pred' and true_field == 'date_true':
        return _date_matches
    return _raw_matches


def _raw_matches(predicted: str, truth: str) -> bool:
    return predicted.strip() == truth.strip()


def _date_matches(predicted: str, truth: str) -> bool:
    return _clean_value(predicted) == _clean_value(truth)


def _district_matches(predicted: str, truth: str) -> bool:
    predicted_clean = _clean_value(predicted)
    truth_clean = _clean_value(truth)
    if predicted_clean == truth_clean:
        return True
    predicted_normalized = _normalize_district_value(predicted_clean)
    truth_normalized = _normalize_district_value(truth_clean)
    return bool(predicted_normalized and truth_normalized and predicted_normalized == truth_normalized)


def _municipality_matches(predicted: str, truth: str) -> bool:
    predicted_clean = _clean_value(predicted)
    truth_clean = _clean_value(truth)
    if predicted_clean == truth_clean:
        return True
    predicted_normalized = _normalize_municipality_value(predicted_clean)
    truth_normalized = _normalize_municipality_value(truth_clean)
    return bool(predicted_normalized and truth_normalized and predicted_normalized == truth_normalized)


def _normalize_district_value(value: str) -> str | None:
    if not value:
        return None
    return normalize_district(value, 'en')


def _normalize_municipality_value(value: str) -> str | None:
    if not value:
        return None
    return normalize_municipality(value, 'en')


def _clean_value(value: str) -> str:
    return value.strip()
