"""Detailed audit helpers for the completed manual verification pack."""

from __future__ import annotations

import json
from typing import Any

from ..config import AppConfig
from ..utils import ensure_directory
from .common import is_truth_filled, iso_now
from .manual_score import (
    _field_comparator,
    compute_manual_metrics,
    load_manual_labels,
)


def run_manual_audit_stage(config: AppConfig) -> int:
    """Build a detailed mismatch audit from the completed manual verification sample."""

    output_dir = config.resolve_path('outputs_dir')
    refreshed_path = output_dir / 'manual_verification_sample_refreshed.csv'
    sample_path = refreshed_path if refreshed_path.exists() else output_dir / 'manual_verification_sample.csv'
    rows = load_manual_labels(sample_path)
    audit = build_manual_audit(rows)
    output_dir = config.resolve_path('outputs_dir')
    ensure_directory(output_dir)
    audit_path = output_dir / 'manual_audit.json'
    report_path = output_dir / 'manual_audit.md'
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True), encoding='utf-8')
    report_path.write_text(build_manual_audit_report(audit), encoding='utf-8')
    return int(audit['labeled_rows'])


def build_manual_audit(rows: list[dict[str, str]]) -> dict[str, Any]:
    """Summarize priority mismatches and labeling coverage from the manual sample."""

    labeled_rows = [row for row in rows if is_truth_filled(row.get('class_true'))]
    unlabeled_rows = [row for row in rows if not is_truth_filled(row.get('class_true'))]
    metrics = compute_manual_metrics(rows)
    mismatch_summary = {
        'class': _summarize_class_mismatches(labeled_rows),
        'district': _summarize_field_mismatches(labeled_rows, 'district_pred', 'district_true'),
        'municipality': _summarize_field_mismatches(labeled_rows, 'municipality_pred', 'municipality_true'),
        'date': _summarize_field_mismatches(labeled_rows, 'event_date_pred', 'date_true'),
        'deaths': _summarize_deaths_mismatches(labeled_rows),
        'trigger': _summarize_field_mismatches(labeled_rows, 'trigger_pred', 'trigger_true'),
    }
    priority_rows = sorted(
        (_build_priority_row(row) for row in labeled_rows),
        key=lambda row: (-row['priority'], row['source'], row['title'], row['url']),
    )
    priority_rows = [row for row in priority_rows if row['issues']]
    return {
        'generated_at': iso_now(),
        'total_rows': len(rows),
        'labeled_rows': len(labeled_rows),
        'unlabeled_rows': len(unlabeled_rows),
        'unlabeled_items': [
            {
                'url': row.get('url', ''),
                'source': row.get('source', ''),
                'title': row.get('title', ''),
            }
            for row in unlabeled_rows
        ],
        'metrics': metrics,
        'mismatch_summary': mismatch_summary,
        'priority_rows': priority_rows[:25],
    }


def build_manual_audit_report(audit: dict[str, Any]) -> str:
    """Render a human-readable markdown report for manual audit results."""

    metrics = audit['metrics']
    lines = [
        '# Manual Audit Report',
        '',
        f"Generated at: {audit['generated_at']}",
        f"Total rows: {audit['total_rows']}",
        f"Labeled rows: {audit['labeled_rows']}",
        f"Unlabeled rows: {audit['unlabeled_rows']}",
        '',
        '## Snapshot Metrics',
        f"Classification macro F1: {metrics['classification']['macro']['f1']:.3f}",
        f"District accuracy: {metrics['district']['accuracy']}",
        f"Municipality accuracy: {metrics['municipality']['accuracy']}",
        f"Date accuracy: {metrics['date']['accuracy']}",
        f"Deaths exact match: {metrics['deaths']['exact_match_rate']}",
        f"Trigger accuracy: {metrics['trigger']['accuracy']}",
        '',
        '## Mismatch Summary',
    ]
    for field_name, summary in audit['mismatch_summary'].items():
        lines.append(
            f"- {field_name}: {summary['mismatch_rows']} mismatches, {summary['missing_prediction_rows']} missing predictions, {summary['labeled_rows']} labeled rows"
        )
    if audit['unlabeled_items']:
        lines.extend(['', '## Unlabeled Rows'])
        for row in audit['unlabeled_items']:
            lines.append(f"- [{row['source']}] {row['title']} ({row['url']})")
    lines.extend(['', '## Priority Rows'])
    if not audit['priority_rows']:
        lines.append('- No labeled mismatches found.')
    else:
        for row in audit['priority_rows']:
            issue_summary = '; '.join(row['issues'])
            lines.append(f"- P{row['priority']}: [{row['source']}] {row['title']} ({row['url']})")
            lines.append(f"  Issues: {issue_summary}")
    return '\n'.join(lines) + '\n'


def _summarize_class_mismatches(rows: list[dict[str, str]]) -> dict[str, Any]:
    labeled = [row for row in rows if is_truth_filled(row.get('class_true'))]
    mismatches = [row for row in labeled if row.get('class_pred', '').strip() != row.get('class_true', '').strip()]
    missing = [row for row in labeled if not is_truth_filled(row.get('class_pred'))]
    return {
        'labeled_rows': len(labeled),
        'mismatch_rows': len(mismatches),
        'missing_prediction_rows': len(missing),
    }


def _summarize_field_mismatches(rows: list[dict[str, str]], pred_field: str, true_field: str) -> dict[str, Any]:
    labeled = [row for row in rows if row.get("class_true", "").strip() != "3" and is_truth_filled(row.get(true_field))]
    comparator = _field_comparator(pred_field, true_field)
    mismatches = [row for row in labeled if not comparator(row.get(pred_field, ''), row.get(true_field, ''))]
    missing = [row for row in labeled if not is_truth_filled(row.get(pred_field))]
    return {
        'labeled_rows': len(labeled),
        'mismatch_rows': len(mismatches),
        'missing_prediction_rows': len(missing),
    }


def _summarize_deaths_mismatches(rows: list[dict[str, str]]) -> dict[str, Any]:
    labeled = [row for row in rows if row.get("class_true", "").strip() != "3" and is_truth_filled(row.get('deaths_true'))]
    mismatches = []
    missing = 0
    for row in labeled:
        pred_raw = row.get('deaths_pred', '').strip()
        true_raw = row.get('deaths_true', '').strip()
        true_value = int(true_raw)
        if pred_raw == '':
            if true_value != 0:
                missing += 1
                mismatches.append(row)
            continue
        if int(pred_raw) != true_value:
            mismatches.append(row)
    return {
        'labeled_rows': len(labeled),
        'mismatch_rows': len(mismatches),
        'missing_prediction_rows': missing,
    }


def _build_priority_row(row: dict[str, str]) -> dict[str, Any]:
    issues: list[str] = []
    priority = 0

    class_pred = row.get('class_pred', '').strip()
    class_true = row.get('class_true', '').strip()
    if class_pred != class_true:
        issues.append(f'class {class_pred or "<missing>"} -> {class_true}')
        priority = max(priority, 3 if class_true == '1' else 2)

    if class_true == '3':
        return {
            'priority': priority,
            'source': row.get('source', ''),
            'title': row.get('title', ''),
            'url': row.get('url', ''),
            'issues': issues,
        }

    for pred_field, true_field, label in (
        ('district_pred', 'district_true', 'district'),
        ('municipality_pred', 'municipality_true', 'municipality'),
        ('event_date_pred', 'date_true', 'date'),
        ('trigger_pred', 'trigger_true', 'trigger'),
    ):
        truth = row.get(true_field, '')
        if not is_truth_filled(truth):
            continue
        comparator = _field_comparator(pred_field, true_field)
        predicted = row.get(pred_field, '')
        if not comparator(predicted, truth):
            issues.append(f"{label} {predicted.strip() or '<missing>'} -> {truth.strip()}")
            priority = max(priority, 2)

    deaths_truth = row.get('deaths_true', '')
    if is_truth_filled(deaths_truth):
        predicted = row.get('deaths_pred', '').strip()
        true_value = int(deaths_truth.strip())
        predicted_value = None if predicted == '' else int(predicted)
        if predicted_value is None and true_value != 0:
            issues.append(f'deaths <missing> -> {true_value}')
            priority = max(priority, 2)
        elif predicted_value is not None and predicted_value != true_value:
            issues.append(f'deaths {predicted_value} -> {true_value}')
            priority = max(priority, 2)

    return {
        'priority': priority,
        'source': row.get('source', ''),
        'title': row.get('title', ''),
        'url': row.get('url', ''),
        'issues': issues,
    }
