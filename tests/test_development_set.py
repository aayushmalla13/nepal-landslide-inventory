"""Tests for the independent pipeline-development sample."""

from __future__ import annotations

import csv
from pathlib import Path

from landslide_inventory.config import load_config
from landslide_inventory.db import connect_sqlite, initialize_sqlite
from landslide_inventory.validation.development_set import (
    allocate_balanced_languages,
    build_development_sample,
    collect_prior_evaluation_urls,
    run_development_set_stage,
)
from landslide_inventory.validation.locked_test_set import FrameRow


def _frame_row(url: str, decision: str, language: str) -> FrameRow:
    return FrameRow(
        url=url,
        source='source',
        year='2022',
        route_lang=language,
        title='Landslide article',
        snippet='A landslide affected a settlement.',
        pipeline_decision=decision,
        predictions={'headline_pred': 1},
    )


def test_balanced_language_allocation_redistributes_shortfall() -> None:
    assert allocate_balanced_languages({'en': 2, 'np': 8}, 8) == {'en': 2, 'np': 6}


def test_development_sample_is_deterministic_balanced_and_excludes_prior_urls() -> None:
    frame = [
        *[_frame_row(f'https://example.test/en/{index}', 'dropped_specificity', 'en')
          for index in range(6)],
        *[_frame_row(f'https://example.test/np/{index}', 'dropped_specificity', 'np')
          for index in range(6)],
    ]
    excluded = {'https://example.test/en/0'}
    allocation = {'dropped_specificity': 8}

    first, first_bookkeeping = build_development_sample(
        frame, excluded, allocation, seed=123
    )
    second, second_bookkeeping = build_development_sample(
        frame, excluded, allocation, seed=123
    )

    assert [row.url for row in first] == [row.url for row in second]
    assert excluded.isdisjoint(row.url for row in first)
    assert sum(row.route_lang == 'en' for row in first) == 4
    assert sum(row.route_lang == 'np' for row in first) == 4
    assert first_bookkeeping == second_bookkeeping


def test_prior_evaluation_exclusions_include_locked_and_labelled_manual_rows(
    config_file: Path,
) -> None:
    config = load_config(config_file)
    output_dir = config.resolve_path('outputs_dir')
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / 'locked_test_set_v2_labels.csv').write_text(
        'row_id,url,is_landslide_event_true\n'
        'v2-0001,https://example.test/locked,\n',
        encoding='utf-8',
    )
    (output_dir / 'manual_verification_sample.csv').write_text(
        'url,class_true\n'
        'https://example.test/labelled,1\n'
        'https://example.test/unlabelled,\n',
        encoding='utf-8',
    )

    excluded, audit = collect_prior_evaluation_urls(config)

    assert excluded == {
        'https://example.test/locked',
        'https://example.test/labelled',
    }
    assert {item['category'] for item in audit} == {
        'locked_test',
        'labelled_manual_evaluation',
    }


def test_development_stage_writes_blind_zero_overlap_artifacts(config_file: Path) -> None:
    config = load_config(config_file)
    config.raw['validation']['development_set'] = {
        'version': 'test-v1',
        'seed': 77,
        'allocation': {'kept_class1': 2, 'kept_class2': 1},
    }
    initialize_sqlite(config.sqlite_path)
    native_urls = [
        'https://example.test/locked',
        'https://example.test/class1',
        'https://example.test/class2',
    ]
    assisted_url = 'https://example.test/assisted'
    with connect_sqlite(config.sqlite_path) as connection:
        connection.executemany(
            """
            INSERT INTO raw_articles (url, source, title, text, method)
            VALUES (?, 'test', 'Landslide report',
                    'A landslide affected a village in Nepal.', ?)
            """,
            [(url, 'tag') for url in native_urls] + [(assisted_url, 'external_seed_bipad')],
        )
        for index, url in enumerate([*native_urls, assisted_url]):
            event_class = 2 if url.endswith('class2') else 1
            connection.execute(
                """
                INSERT INTO article_events (
                    extracted_event_id, article_url, event_class, event_payload,
                    url, source, title, route_lang, class, in_nepal,
                    specificity_ok
                ) VALUES (?, ?, ?, '{}', ?, 'test', 'Landslide report',
                          ?, ?, 1, 1)
                """,
                (f'event-{index}', url, event_class, url, 'np' if index % 2 else 'en',
                 event_class),
            )
        connection.commit()
    output_dir = config.resolve_path('outputs_dir')
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / 'locked_test_set_v2_labels.csv').write_text(
        'row_id,url\nv2-0001,https://example.test/locked\n',
        encoding='utf-8',
    )

    manifest = run_development_set_stage(config)

    assert manifest['sample_size'] == 2
    assert manifest['overlap_with_prior_evaluation'] == 0
    labels_path = output_dir / 'development_set_test-v1_LABEL_HERE.csv'
    predictions_path = output_dir / 'development_set_test-v1_predictions.csv'
    with labels_path.open(encoding='utf-8', newline='') as handle:
        labels = list(csv.DictReader(handle))
    with predictions_path.open(encoding='utf-8', newline='') as handle:
        predictions = list(csv.DictReader(handle))
    assert {row['url'] for row in labels} == {
        'https://example.test/class1',
        'https://example.test/class2',
    }
    assert all(not row['is_landslide_event_true'] for row in labels)
    assert all(row['headline_pred'] in {'0', '1'} for row in predictions)
    assert run_development_set_stage(config) == manifest
