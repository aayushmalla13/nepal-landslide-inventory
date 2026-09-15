"""Tests for the checksummed final validation and release bundle."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

import pytest

from landslide_inventory.config import load_config
from landslide_inventory.db import connect_sqlite, initialize_sqlite
from landslide_inventory.export import FINAL_COLUMNS
from landslide_inventory.unify.reviewed_corrections import apply_reviewed_corrections
from landslide_inventory.utils import stable_hash
from landslide_inventory.validation.common import write_csv
from landslide_inventory.validation.final_report import (
    build_validation_report,
    run_final_report_stage,
    summarize_canonical,
    validation_metric_rows,
)
from landslide_inventory.validation.locked_test_set import (
    LABEL_COLUMNS,
    PREDICTION_COLUMNS,
)


def _score(labels_path: Path, predictions_path: Path) -> dict[str, object]:
    return {
        'weighted': {'precision': 0.68, 'recall': 0.85, 'f1': 0.756},
        'weighted_ci95_stratified_bootstrap': {
            'precision': [0.61, 0.75],
            'recall': [0.79, 0.91],
            'f1': [0.70, 0.81],
        },
        'primary_answered_rows': 1,
        'labelled_rows': 1,
        'undecidable_rows': 0,
        'extraction_among_true_headline_articles': {
            'district': {
                'truth_available_n': 40,
                'reportable': True,
                'weighted_exact_accuracy': 0.8,
                'weighted_coverage': 0.9,
            },
            'event_date': {
                'truth_available_n': 2,
                'reportable': False,
                'minimum_truth_rows': 30,
                'weighted_exact_accuracy': 1.0,
                'weighted_coverage': 1.0,
            },
        },
        'labels_sha256': hashlib.sha256(labels_path.read_bytes()).hexdigest(),
        'predictions_sha256': hashlib.sha256(predictions_path.read_bytes()).hexdigest(),
    }


def test_metric_rows_hide_nonreportable_event_date() -> None:
    rows = validation_metric_rows(_score(Path(__file__), Path(__file__)))
    event_date = next(row for row in rows if row['measure'] == 'event_date_exact_accuracy')
    assert event_date['reportable'] == 'no'
    assert event_date['estimate'] == ''


def test_reportable_event_date_accuracy_and_coverage_reach_the_release_report() -> None:
    score = _score(Path(__file__), Path(__file__))
    event_date = score['extraction_among_true_headline_articles']['event_date']
    event_date.update(
        {
            'truth_available_n': 83,
            'reportable': True,
            'weighted_exact_accuracy': 0.824,
            'weighted_coverage': 0.976,
        }
    )
    rows = validation_metric_rows(score)
    date_rows = {row['measure']: row for row in rows if row['measure'].startswith('event_date')}
    assert date_rows['event_date_exact_accuracy']['estimate'] == 0.824
    assert date_rows['event_date_coverage']['estimate'] == 0.976
    assert {row['reportable'] for row in date_rows.values()} == {'yes'}

    report = build_validation_report(
        score,
        {'design_version': 'v7', 'sample_size': 400, 'eligible_frame_size': 1000},
        {
            'rows': 1,
            'date_min': '2020-01-01',
            'date_max': '2020-01-01',
            'districts': 1,
            'representative_sources': 1,
            'road_obstruction': 0,
            'non_single': 0,
            'sha256': 'abc',
        },
        {'rows': 0},
    )
    assert 'Event-date exact accuracy was 0.824, with coverage 0.976' in report
    assert 'Event-date performance is reported' in report


def test_canonical_summary_rejects_rows_after_release_cutoff(tmp_path: Path) -> None:
    path = tmp_path / 'canonical.csv'
    write_csv(
        path,
        FINAL_COLUMNS,
        [{'event_id': 'event-1', 'event_date_ad': '2026-08-11', 'district': 'Mugu'}],
    )
    with pytest.raises(ValueError, match='after release cutoff'):
        summarize_canonical(path, date(2026, 8, 10))


def test_final_report_writes_verified_release_bundle(config_file: Path) -> None:
    config = load_config(config_file)
    config.raw['validation'].update(
        {
            'locked_test_set': {
                'version': 'v3-test',
                'seed': 1,
                'allocation': {'kept_class1': 1},
            },
            'final_release_date': '2026-08-10',
        }
    )
    output_dir = config.resolve_path('outputs_dir')
    output_dir.mkdir(parents=True, exist_ok=True)
    correction_path = config.config_path.parent / 'corrections.csv'
    config.raw['validation']['article_corrections_path'] = str(correction_path)
    url = 'https://example.test/event'
    correction_path.write_text(
        'url,reviewed_at,reviewed_by,evidence_url,correction_action,reason,'
        'published_date_ad,event_date_ad,in_nepal,exclude_from_canonical,'
        'scope_reason\n'
        f'{url},2026-08-10,tester,https://evidence.test,verified,'
        'Verified date,2025-08-22,2025-08-22,,0,\n',
        encoding='utf-8',
    )
    initialize_sqlite(config.sqlite_path)
    with connect_sqlite(config.sqlite_path) as connection:
        connection.execute(
            """
            INSERT INTO raw_articles (url, source, title, published_date_ad, text)
            VALUES (?, 'test', 'Landslide report', '2026-08-22', 'A landslide.')
            """,
            (url,),
        )
        connection.execute(
            """
            INSERT INTO article_events (
                extracted_event_id, article_url, event_class, event_payload,
                url, source, title, published_date_ad, event_date_ad
            ) VALUES ('event-raw', ?, 1, '{}', ?, 'test', 'Landslide report',
                      '2026-08-22', '2026-08-22')
            """,
            (url, url),
        )
        connection.commit()
    apply_reviewed_corrections(config)

    stem = 'locked_test_set_v3-test'
    reference_path = output_dir / f'{stem}_labels.csv'
    final_labels_path = output_dir / f'{stem}_labels_final.csv'
    predictions_path = output_dir / f'{stem}_predictions.csv'
    label = {
        'row_id': 'v3-test-0001',
        'url': url,
        'is_landslide_event_true': 'yes',
        'in_nepal_true': 'yes',
        'hazard_type_true': 'landslide',
        'event_granularity_true': 'single',
        'article_role_true': 'first_report',
        'annotator': 'tester',
    }
    write_csv(reference_path, LABEL_COLUMNS, [{'row_id': label['row_id'], 'url': url}])
    write_csv(final_labels_path, LABEL_COLUMNS, [label])
    write_csv(
        predictions_path,
        PREDICTION_COLUMNS,
        [{'row_id': label['row_id'], 'url': url, 'headline_pred': 1}],
    )
    (output_dir / f'{stem}_manifest.json').write_text(
        json.dumps(
            {
                'design_version': 'v3-test',
                'sample_size': 1,
                'eligible_frame_size': 10,
                'lock_hash': stable_hash('locked_test_set', 'v3-test', [url]),
            }
        ),
        encoding='utf-8',
    )
    score = _score(final_labels_path, predictions_path)
    (output_dir / f'{stem}_score.json').write_text(
        json.dumps(score), encoding='utf-8'
    )
    write_csv(
        output_dir / 'canonical_events_final.csv',
        FINAL_COLUMNS,
        [
            {
                'event_id': 'canonical-1',
                'event_date_ad': '2025-08-22',
                'district': 'Myagdi',
                'representative_source': 'test',
                'event_type': 'landslide',
                'event_granularity': 'single',
            }
        ],
    )
    (output_dir / 'inventory_audit_summary.json').write_text('{}', encoding='utf-8')
    (output_dir / 'inventory_audit_report.md').write_text('# Audit\n', encoding='utf-8')

    manifest = run_final_report_stage(config)

    assert manifest['canonical_summary']['rows'] == 1
    assert manifest['checks']['canonical_rows_after_release_cutoff'] == 0
    release_dir = (
        config.config_path.parent
        / 'data/releases/nepal_landslide_inventory_v0.1.0_v3-test_20260810'
    )
    assert (release_dir / 'release_manifest.json').exists()
    assert (release_dir / 'landslide_inventory.sqlite').exists()
    assert (release_dir / f'{stem}_validation_report.md').exists()
