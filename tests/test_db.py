"""Tests for SQLite initialization."""

from __future__ import annotations

from pathlib import Path

from landslide_inventory.db import connect_sqlite, initialize_sqlite, list_tables


def test_initialize_sqlite_creates_expected_tables(tmp_path: Path) -> None:
    database_path = tmp_path / 'data' / 'raw_sqlite' / 'inventory.sqlite'
    initialize_sqlite(database_path)
    assert list_tables(database_path) == [
        'article_events',
        'article_lang',
        'article_location_check',
        'article_scope',
        'article_specificity',
        'canonical_events',
        'cluster_summary',
        'discovered_urls',
        'pipeline_runs',
        'raw_articles',
    ]



def test_article_events_schema_contains_place_columns(tmp_path: Path) -> None:
    database_path = tmp_path / 'data' / 'raw_sqlite' / 'inventory.sqlite'
    initialize_sqlite(database_path)
    with connect_sqlite(database_path) as connection:
        columns = {
            str(row['name'])
            for row in connection.execute('PRAGMA table_info(article_events)').fetchall()
        }
    assert {'url', 'source', 'route_lang', 'mixed_flag', 'class', 'district', 'municipality', 'ward', 'place_name_raw', 'place_candidates_json', 'conf_place', 'extracted_at', 'specificity_ok', 'specificity_reason', 'specificity_score', 'location_consistent', 'location_reason', 'dedup_cluster_id'} <= columns


def test_canonical_events_schema_contains_location_evidence_columns(tmp_path: Path) -> None:
    database_path = tmp_path / 'data' / 'raw_sqlite' / 'inventory.sqlite'
    initialize_sqlite(database_path)
    with connect_sqlite(database_path) as connection:
        columns = {
            str(row['name'])
            for row in connection.execute('PRAGMA table_info(canonical_events)').fetchall()
        }
    assert {'municipality_candidates_json', 'ward_candidates_json', 'place_name_candidates_json'} <= columns
