"""Tests for the safe dedup clustering stage."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from landslide_inventory.config import load_config
from landslide_inventory.db import connect_sqlite, initialize_sqlite
from landslide_inventory.unify.dedup_stage import (
    build_dedup_config,
    cluster_events,
    load_dedup_events,
    run_dedup_stage,
)


def _insert_raw_article(connection: sqlite3.Connection, url: str, source: str, title: str, text: str) -> None:
    connection.execute(
        """
        INSERT INTO raw_articles (url, source, title, text, parse_success)
        VALUES (?, ?, ?, ?, 1)
        ON CONFLICT(url) DO UPDATE SET source = excluded.source, title = excluded.title, text = excluded.text
        """,
        (url, source, title, text),
    )


def _insert_article_event(
    connection: sqlite3.Connection,
    *,
    url: str,
    source: str,
    title: str,
    event_class: int,
    in_nepal: int,
    event_date_ad: str | None,
    district: str | None,
    municipality: str | None,
    deaths: int | None = None,
    ward: str | None = None,
    place_name_raw: str | None = None,
) -> None:
    connection.execute(
        """
        INSERT INTO article_events (
            extracted_event_id, article_url, event_class, event_payload,
            url, source, title, route_lang, mixed_flag, class, event_date_ad,
            district, province, municipality, ward, place_admin_level,
            place_name_raw, place_candidates_json, deaths, missing, injured,
            trigger, conf_class, conf_date, conf_district, conf_place,
            conf_fatalities, conf_trigger, extracted_at, in_nepal, scope_reason
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'en', 0, ?, ?, ?, ?, ?, ?, 'municipality', ?, '[]', ?, NULL, NULL,
                  'rainfall', 0.95, 0.95, 0.9, 0.88, 0.9, 0.9, '2024-07-16T00:00:00+00:00', ?, 'district_match')
        ON CONFLICT(url) DO UPDATE SET
            source = excluded.source,
            title = excluded.title,
            class = excluded.class,
            event_class = excluded.event_class,
            event_date_ad = excluded.event_date_ad,
            district = excluded.district,
            province = excluded.province,
            municipality = excluded.municipality,
            place_name_raw = excluded.place_name_raw,
            deaths = excluded.deaths,
            in_nepal = excluded.in_nepal,
            scope_reason = excluded.scope_reason
        """,
        (
            f'extract-{url}', url, event_class, '{}',
            url, source, title, event_class, event_date_ad, district,
            'Bagmati' if district else None, municipality, ward, place_name_raw or municipality or title, deaths, in_nepal,
        ),
    )


def test_duplicates_across_sources_merge(config_file: Path) -> None:
    config = load_config(config_file)
    initialize_sqlite(config.sqlite_path)
    with connect_sqlite(config.sqlite_path) as connection:
        _insert_raw_article(connection, 'https://a.test/1', 'source-a', 'Dhading landslide kills 3', 'A landslide in Dhading district killed 3 people after heavy rain.')
        _insert_raw_article(connection, 'https://b.test/2', 'source-b', 'Dhading landslide leaves 3 dead', 'Heavy rain caused a landslide in Dhading district that killed 3 people.')
        _insert_article_event(connection, url='https://a.test/1', source='source-a', title='Dhading landslide kills 3', event_class=1, in_nepal=1, event_date_ad='2024-07-16', district='Dhading', municipality='Nilkantha Municipality', deaths=3)
        _insert_article_event(connection, url='https://b.test/2', source='source-b', title='Dhading landslide leaves 3 dead', event_class=1, in_nepal=1, event_date_ad='2024-07-17', district='Dhading', municipality='Nilkantha Municipality', deaths=3)
        connection.commit()

    run_dedup_stage(config)

    with connect_sqlite(config.sqlite_path) as connection:
        canonical_count = connection.execute('SELECT COUNT(*) FROM canonical_events').fetchone()[0]
        cluster_sizes = connection.execute('SELECT size FROM cluster_summary').fetchall()
        unclustered = connection.execute('SELECT COUNT(*) FROM article_events WHERE class = 1 AND in_nepal = 1 AND dedup_cluster_id IS NULL').fetchone()[0]
    assert canonical_count == 1
    assert [row[0] for row in cluster_sizes] == [2]
    assert unclustered == 0


def test_same_district_close_dates_different_municipalities_do_not_merge(config_file: Path) -> None:
    config = load_config(config_file)
    initialize_sqlite(config.sqlite_path)
    with connect_sqlite(config.sqlite_path) as connection:
        _insert_raw_article(connection, 'https://a.test/1', 'source-a', 'Landslide in Melamchi kills 2', 'Rain triggered a landslide in Melamchi Municipality.')
        _insert_raw_article(connection, 'https://b.test/2', 'source-b', 'Landslide in Barhabise kills 2', 'Rain triggered a separate landslide in Barhabise Municipality.')
        _insert_article_event(connection, url='https://a.test/1', source='source-a', title='Landslide in Melamchi kills 2', event_class=1, in_nepal=1, event_date_ad='2024-07-16', district='Sindhupalchok', municipality='Melamchi Municipality', deaths=2)
        _insert_article_event(connection, url='https://b.test/2', source='source-b', title='Landslide in Barhabise kills 2', event_class=1, in_nepal=1, event_date_ad='2024-07-17', district='Sindhupalchok', municipality='Barhabise Municipality', deaths=2)
        connection.commit()

    run_dedup_stage(config)

    with connect_sqlite(config.sqlite_path) as connection:
        canonical_count = connection.execute('SELECT COUNT(*) FROM canonical_events').fetchone()[0]
        cluster_sizes = sorted(row[0] for row in connection.execute('SELECT size FROM cluster_summary').fetchall())
    assert canonical_count == 2
    assert cluster_sizes == [1, 1]


def test_out_of_scope_rows_never_appear_in_canonical_events(config_file: Path) -> None:
    config = load_config(config_file)
    initialize_sqlite(config.sqlite_path)
    with connect_sqlite(config.sqlite_path) as connection:
        _insert_raw_article(connection, 'https://scope.test/1', 'source-a', 'Floods in India kill 4', 'India landslide disaster.')
        _insert_article_event(connection, url='https://scope.test/1', source='source-a', title='Floods in India kill 4', event_class=1, in_nepal=0, event_date_ad='2024-07-16', district='Dhading', municipality=None, deaths=4)
        connection.commit()

    run_dedup_stage(config)

    with connect_sqlite(config.sqlite_path) as connection:
        canonical_count = connection.execute('SELECT COUNT(*) FROM canonical_events').fetchone()[0]
        cluster_count = connection.execute('SELECT COUNT(*) FROM cluster_summary').fetchone()[0]
    assert canonical_count == 0
    assert cluster_count == 0


def test_dedup_stage_is_idempotent(config_file: Path) -> None:
    config = load_config(config_file)
    initialize_sqlite(config.sqlite_path)
    with connect_sqlite(config.sqlite_path) as connection:
        _insert_raw_article(connection, 'https://a.test/1', 'source-a', 'Dhading landslide kills 3', 'A landslide in Dhading district killed 3 people after heavy rain.')
        _insert_raw_article(connection, 'https://b.test/2', 'source-b', 'Dhading landslide leaves 3 dead', 'Heavy rain caused a landslide in Dhading district that killed 3 people.')
        _insert_article_event(connection, url='https://a.test/1', source='source-a', title='Dhading landslide kills 3', event_class=1, in_nepal=1, event_date_ad='2024-07-16', district='Dhading', municipality='Nilkantha Municipality', deaths=3)
        _insert_article_event(connection, url='https://b.test/2', source='source-b', title='Dhading landslide leaves 3 dead', event_class=1, in_nepal=1, event_date_ad='2024-07-16', district='Dhading', municipality='Nilkantha Municipality', deaths=3)
        connection.commit()

    run_dedup_stage(config)
    run_dedup_stage(config)

    with connect_sqlite(config.sqlite_path) as connection:
        canonical_count = connection.execute('SELECT COUNT(*) FROM canonical_events').fetchone()[0]
        cluster_count = connection.execute('SELECT COUNT(*) FROM cluster_summary').fetchone()[0]
        article_cluster_count = connection.execute('SELECT COUNT(DISTINCT dedup_cluster_id) FROM article_events WHERE dedup_cluster_id IS NOT NULL').fetchone()[0]
    assert canonical_count == 1
    assert cluster_count == 1
    assert article_cluster_count == 1


def test_cluster_events_uses_only_scope_filtered_class_one_rows(config_file: Path) -> None:
    config = load_config(config_file)
    initialize_sqlite(config.sqlite_path)
    with connect_sqlite(config.sqlite_path) as connection:
        _insert_raw_article(connection, 'https://a.test/1', 'source-a', 'Dhading landslide kills 3', 'A landslide in Dhading district killed 3 people after heavy rain.')
        _insert_article_event(connection, url='https://a.test/1', source='source-a', title='Dhading landslide kills 3', event_class=2, in_nepal=1, event_date_ad='2024-07-16', district='Dhading', municipality='Nilkantha Municipality', deaths=3)
        connection.commit()

    events = load_dedup_events(config.sqlite_path)
    clusters = cluster_events(events, build_dedup_config(config))
    assert events == []
    assert clusters == []


def test_canonical_events_preserve_location_evidence(config_file: Path) -> None:
    config = load_config(config_file)
    initialize_sqlite(config.sqlite_path)
    with connect_sqlite(config.sqlite_path) as connection:
        _insert_raw_article(connection, 'https://a.test/1', 'source-a', 'Dhading landslide kills 3', 'A landslide in Dhading district killed 3 people after heavy rain.')
        _insert_raw_article(connection, 'https://b.test/2', 'source-b', 'Dhading landslide leaves 3 dead', 'Heavy rain caused a landslide in Dhading district that killed 3 people.')
        _insert_article_event(connection, url='https://a.test/1', source='source-a', title='Dhading landslide kills 3', event_class=1, in_nepal=1, event_date_ad='2024-07-16', district='Dhading', municipality='Nilkantha Municipality', deaths=3, ward='Ward 5', place_name_raw='Nilkantha Municipality')
        _insert_article_event(connection, url='https://b.test/2', source='source-b', title='Dhading landslide leaves 3 dead', event_class=1, in_nepal=1, event_date_ad='2024-07-16', district='Dhading', municipality='Nilkantha Municipality', deaths=3, ward='Ward 5', place_name_raw='Salyantar')
        connection.commit()

    run_dedup_stage(config)

    with connect_sqlite(config.sqlite_path) as connection:
        row = connection.execute('SELECT municipality_candidates_json, ward_candidates_json, place_name_candidates_json FROM canonical_events').fetchone()
    assert 'Nilkantha Municipality' in row[0]
    assert 'Ward 5' in row[1]
    assert 'Salyantar' in row[2]


def test_one_missing_municipality_requires_stricter_similarity(config_file: Path) -> None:
    config = load_config(config_file)
    initialize_sqlite(config.sqlite_path)
    with connect_sqlite(config.sqlite_path) as connection:
        _insert_raw_article(connection, 'https://a.test/1', 'source-a', 'Dhading landslide kills 3 after rain', 'A landslide in Dhading district killed 3 people after rain.')
        _insert_raw_article(connection, 'https://b.test/2', 'source-b', 'Dhading landslide kills three after rainfall', 'Dhading district saw a landslide after rainfall.')
        _insert_article_event(connection, url='https://a.test/1', source='source-a', title='Dhading landslide kills 3 after rain', event_class=1, in_nepal=1, event_date_ad='2024-07-16', district='Dhading', municipality='Nilkantha Municipality', deaths=3)
        _insert_article_event(connection, url='https://b.test/2', source='source-b', title='Dhading landslide kills three after rainfall', event_class=1, in_nepal=1, event_date_ad='2024-07-16', district='Dhading', municipality=None, deaths=3, place_name_raw='Dhading')
        connection.commit()

    run_dedup_stage(config)

    with connect_sqlite(config.sqlite_path) as connection:
        canonical_count = connection.execute('SELECT COUNT(*) FROM canonical_events').fetchone()[0]
    assert canonical_count == 2
