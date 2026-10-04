"""Regression tests for non-destructive, repeatable filter stages."""

from __future__ import annotations

from pathlib import Path

from landslide_inventory.config import load_config
from landslide_inventory.db import connect_sqlite, initialize_sqlite
from landslide_inventory.unify.event_specificity import run_event_specificity_stage
from landslide_inventory.unify.scope_filter import run_filter_scope_stage


def _insert_article(config_file: Path, *, url: str, title: str, text: str) -> None:
    config = load_config(config_file)
    initialize_sqlite(config.sqlite_path)
    with connect_sqlite(config.sqlite_path) as connection:
        connection.execute(
            """
            INSERT INTO raw_articles (
                url, source, title, text, published_date_ad, parse_success
            ) VALUES (?, 'test', ?, ?, '2024-07-16', 1)
            """,
            (url, title, text),
        )
        connection.execute(
            """
            INSERT INTO article_events (
                extracted_event_id, article_url, event_class, event_payload,
                url, source, title, published_date_ad, route_lang, mixed_flag,
                class, event_date_ad, district, province, deaths, trigger,
                conf_class, conf_date, conf_district, conf_place,
                conf_fatalities, conf_trigger, extracted_at
            ) VALUES (
                'extract-test', ?, 1, '{}', ?, 'test', ?, '2024-07-16', 'en', 0,
                1, '2024-07-15', 'Kathmandu', 'Bagmati', 2, 'rainfall',
                0.9, 0.9, 0.9, 0.8, 0.9, 0.9, '2024-07-16T00:00:00+00:00'
            )
            """,
            (url, url, title),
        )
        connection.commit()


def _state(config_file: Path, url: str) -> tuple:
    config = load_config(config_file)
    with connect_sqlite(config.sqlite_path) as connection:
        row = connection.execute(
            """
            SELECT class, event_date_ad, district, deaths, trigger,
                   specificity_ok, specificity_reason, in_nepal, scope_reason
            FROM article_events WHERE url = ?
            """,
            (url,),
        ).fetchone()
    return tuple(row)


def test_event_specificity_rerun_preserves_evidence_and_decision(config_file: Path) -> None:
    url = 'https://example.test/preparedness'
    _insert_article(
        config_file,
        url=url,
        title='Nepali Army rolls out monsoon disaster plan',
        text='The preparedness plan covers rescue after possible floods and landslides.',
    )
    config = load_config(config_file)

    run_event_specificity_stage(config)
    first = _state(config_file, url)
    run_event_specificity_stage(config)
    second = _state(config_file, url)

    assert first == second
    assert first[:5] == (3, '2024-07-15', 'Kathmandu', 2, 'rainfall')
    assert first[5:7] == (0, 'context_only')


def test_scope_rerun_preserves_extracted_evidence(config_file: Path) -> None:
    url = 'https://example.test/foreign'
    _insert_article(
        config_file,
        url=url,
        title='Landslide kills four in China',
        text='A landslide in China killed four people after heavy rain.',
    )
    config = load_config(config_file)

    run_filter_scope_stage(config)
    first = _state(config_file, url)
    run_filter_scope_stage(config)
    second = _state(config_file, url)

    assert first == second
    assert first[:5] == (3, '2024-07-15', 'Kathmandu', 2, 'rainfall')
    assert first[7:] == (0, 'out_of_country')
