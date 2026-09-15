"""Contamination and lifecycle tests for the post-development locked v3 set."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from landslide_inventory.config import load_config
from landslide_inventory.db import connect_sqlite, initialize_sqlite
from landslide_inventory.validation.check_labels import run_check_labels_stage
from landslide_inventory.validation.common import write_csv
from landslide_inventory.validation.locked_test_set import (
    LABEL_COLUMNS,
    run_locked_test_set_stage,
    verify_locked_manifest,
)
from landslide_inventory.validation.score_locked import run_score_locked_stage


def _insert_article(connection, url: str, index: int, *, scope: bool = False) -> None:
    language = 'np' if index % 2 else 'en'
    connection.execute(
        """
        INSERT INTO raw_articles (url, source, title, text, method)
        VALUES (?, 'test', 'Landslide report',
                'A single landslide affected a settlement in Nepal.', 'tag')
        """,
        (url,),
    )
    connection.execute(
        """
        INSERT INTO article_events (
            extracted_event_id, article_url, event_class, event_payload,
            url, source, title, route_lang, class, in_nepal, specificity_ok
        ) VALUES (?, ?, 1, '{}', ?, 'test', 'Landslide report', ?, 1, ?, 1)
        """,
        (f'event-{index}', url, url, language, 0 if scope else 1),
    )


def test_v3_draw_excludes_prior_evaluation_and_freezes_completed_labels(
    config_file: Path,
) -> None:
    config = load_config(config_file)
    config.raw.setdefault('validation', {})['locked_test_set'] = {
        'version': 'v3-test',
        'seed': 91,
        'allocation': {'kept_class1': 2, 'dropped_scope': 1},
    }
    initialize_sqlite(config.sqlite_path)
    prior_urls = {
        'https://example.test/prior-locked',
        'https://example.test/prior-development',
        'https://example.test/prior-manual',
    }
    eligible_urls = {
        'https://example.test/eligible-en',
        'https://example.test/eligible-np',
        'https://example.test/eligible-scope',
    }
    with connect_sqlite(config.sqlite_path) as connection:
        for index, url in enumerate(sorted(prior_urls | eligible_urls)):
            _insert_article(
                connection,
                url,
                index,
                scope=url.endswith('scope'),
            )
        connection.execute(
            """
            INSERT INTO raw_articles (url, source, title, text, method)
            VALUES ('https://example.test/assisted', 'test', 'Landslide report',
                    'A landslide in Nepal.', 'external_seed_bipad_reviewed')
            """
        )
        connection.commit()

    output_dir = config.resolve_path('outputs_dir')
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / 'locked_test_set_v2_labels.csv').write_text(
        'row_id,url\nv2-0001,https://example.test/prior-locked\n',
        encoding='utf-8',
    )
    (output_dir / 'development_set_v1_labels.csv').write_text(
        'row_id,url\ndev-v1-0001,https://example.test/prior-development\n',
        encoding='utf-8',
    )
    (output_dir / 'manual_verification_sample.csv').write_text(
        'url,class_true\nhttps://example.test/prior-manual,1\n',
        encoding='utf-8',
    )

    manifest = run_locked_test_set_stage(config)

    stem = 'locked_test_set_v3-test'
    reference_path = output_dir / f'{stem}_labels.csv'
    working_path = output_dir / f'{stem}_LABEL_HERE.csv'
    manifest_path = output_dir / f'{stem}_manifest.json'
    with working_path.open(encoding='utf-8', newline='') as handle:
        labels = list(csv.DictReader(handle))
    assert {row['url'] for row in labels} == eligible_urls
    assert prior_urls.isdisjoint(row['url'] for row in labels)
    assert all(not row['is_landslide_event_true'] for row in labels)
    assert manifest['sample_size'] == 3
    assert manifest['eligible_frame_size'] == 3
    assert manifest['overlap_with_prior_evaluation'] == 0
    assert verify_locked_manifest(manifest_path, reference_path)
    assert run_locked_test_set_stage(config) == manifest

    blank_report = run_check_labels_stage(config)
    assert len(blank_report['problems']['missing_primary']) == 3
    with pytest.raises(ValueError, match='blank is_landslide_event_true'):
        run_score_locked_stage(config)

    for row in labels:
        row.update(
            {
                'is_landslide_event_true': 'yes',
                'in_nepal_true': 'yes',
                'hazard_type_true': 'landslide',
                'event_granularity_true': 'single',
                'article_role_true': 'first_report',
                'annotator': 'test-annotator',
            }
        )
    write_csv(working_path, LABEL_COLUMNS, labels)
    complete_report = run_check_labels_stage(config)
    assert complete_report['total_problems'] == 0

    score = run_score_locked_stage(config)
    assert score['primary_answered_rows'] == 3
    assert (output_dir / f'{stem}_labels_final.csv').exists()
    assert (output_dir / f'{stem}_score.json').exists()
