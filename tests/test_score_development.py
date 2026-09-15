"""Tests for development-only label validation and diagnostics."""

from __future__ import annotations

from pathlib import Path

import pytest

from landslide_inventory.config import load_config
from landslide_inventory.validation.common import write_csv
from landslide_inventory.validation.locked_test_set import (
    LABEL_COLUMNS,
    PREDICTION_COLUMNS,
)
from landslide_inventory.validation.score_development import (
    diagnose,
    run_score_development_stage,
    run_score_development_tuned_stage,
)


def _label(row_id: str, *, granularity: str = 'single') -> dict[str, str]:
    return {
        'row_id': row_id,
        'url': f'https://example.test/{row_id}',
        'source': 'test',
        'year': '2022',
        'route_lang': 'en',
        'title': 'Landslide report',
        'snippet': 'A landslide occurred in Nepal.',
        'is_landslide_event_true': 'yes',
        'in_nepal_true': 'yes',
        'hazard_type_true': 'landslide',
        'event_granularity_true': granularity,
        'article_role_true': 'first_report',
        'district_true': 'Mugu',
        'municipality_true': '',
        'date_true': '2022-10-10',
        'deaths_true': '',
        'trigger_true': 'unknown',
        'annotator': 'tester',
        'notes': '',
    }


def _prediction(row_id: str, *, headline: int) -> dict[str, str | int]:
    return {
        'row_id': row_id,
        'url': f'https://example.test/{row_id}',
        'stratum': 'kept_class1|en',
        'pipeline_decision': 'kept_class1',
        'class_pred': '1',
        'district_pred': 'Mugu',
        'event_date_pred': '2022-10-10',
        'event_type_pred': 'landslide',
        'hazard_type_pred': 'landslide',
        'typing_reason_pred': 'casualties_recorded',
        'headline_pred': headline,
    }


def test_diagnose_reports_unweighted_sample_errors() -> None:
    labels = [_label('tp'), _label('fp', granularity='multi'), _label('fn')]
    predictions = {
        'tp': _prediction('tp', headline=1),
        'fp': _prediction('fp', headline=1),
        'fn': _prediction('fn', headline=0),
    }

    report, errors = diagnose(labels, predictions)

    assert report['design'] == 'development_only_not_for_evaluation'
    assert report['sample_confusion'] == {'tp': 1, 'fp': 1, 'fn': 1, 'tn': 0}
    assert report['error_counts'] == {'false_positive': 1, 'false_negative': 1}
    assert {row['error'] for row in errors} == {'false_positive', 'false_negative'}


def test_score_development_freezes_valid_bom_labels(config_file: Path) -> None:
    config = load_config(config_file)
    config.raw['validation']['development_set'] = {'version': 'test-v1'}
    output_dir = config.resolve_path('outputs_dir')
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = 'development_set_test-v1'
    reference = _label('dev-test-v1-0001')
    reference.update({field: '' for field in LABEL_COLUMNS[7:]})
    completed = _label('dev-test-v1-0001')
    write_csv(output_dir / f'{stem}_labels.csv', LABEL_COLUMNS, [reference])
    working_path = output_dir / f'{stem}_LABEL_HERE.csv'
    write_csv(working_path, LABEL_COLUMNS, [completed])
    working_path.write_bytes(b'\xef\xbb\xbf' + working_path.read_bytes())
    write_csv(
        output_dir / f'{stem}_predictions.csv',
        PREDICTION_COLUMNS,
        [_prediction('dev-test-v1-0001', headline=1)],
    )

    report = run_score_development_stage(config)

    assert report['sample_confusion']['tp'] == 1
    assert report['labels_file'] == f'{stem}_labels_final.csv'
    assert (output_dir / report['labels_file']).read_bytes() == working_path.read_bytes()
    assert (output_dir / report['errors_file']).exists()
    assert (output_dir / f'{stem}_diagnostics.json').exists()

    write_csv(
        output_dir / f'{stem}_predictions_tuned.csv',
        PREDICTION_COLUMNS,
        [_prediction('dev-test-v1-0001', headline=1)],
    )
    tuned = run_score_development_tuned_stage(config)
    assert tuned['comparison'] == 'post_tuning_development_snapshot'
    assert tuned['sample_confusion']['tp'] == 1
    assert (output_dir / f'{stem}_diagnostics_tuned.json').exists()


def test_score_development_rejects_changed_metadata(config_file: Path) -> None:
    config = load_config(config_file)
    config.raw['validation']['development_set'] = {'version': 'test-v1'}
    output_dir = config.resolve_path('outputs_dir')
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = 'development_set_test-v1'
    reference = _label('dev-test-v1-0001')
    reference.update({field: '' for field in LABEL_COLUMNS[7:]})
    completed = _label('dev-test-v1-0001')
    completed['title'] = 'Changed title'
    write_csv(output_dir / f'{stem}_labels.csv', LABEL_COLUMNS, [reference])
    write_csv(output_dir / f'{stem}_LABEL_HERE.csv', LABEL_COLUMNS, [completed])
    write_csv(
        output_dir / f'{stem}_predictions.csv',
        PREDICTION_COLUMNS,
        [_prediction('dev-test-v1-0001', headline=1)],
    )

    with pytest.raises(ValueError, match='protected field title'):
        run_score_development_stage(config)
