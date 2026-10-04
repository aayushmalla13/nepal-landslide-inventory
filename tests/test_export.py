"""Tests for the final-deliverable export.

canonical_events_final.csv was produced by no code in the repository
(docs/TECHNICAL_REVIEW.md section 3.4). These tests pin the reconstruction so it
cannot drift back into being unreproducible.
"""

from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path

import pytest

from landslide_inventory.export import (
    FINAL_COLUMNS,
    assert_event_typing_complete,
    build_final_rows,
    verify_export_matches,
    write_final_csv,
)


@pytest.fixture()
def connection() -> sqlite3.Connection:
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE canonical_events (
            event_id TEXT PRIMARY KEY, dedup_cluster_id TEXT, event_date_ad TEXT,
            district TEXT, province TEXT, municipality TEXT, event_payload TEXT,
            inserted_at TEXT, municipality_candidates_json TEXT,
            ward_candidates_json TEXT, place_name_candidates_json TEXT
        );
        CREATE TABLE cluster_summary (
            cluster_id TEXT PRIMARY KEY, district TEXT, date_min TEXT, date_max TEXT,
            size INTEGER, sources TEXT, urls TEXT, inserted_at TEXT
        );
        CREATE TABLE article_events (
            url TEXT PRIMARY KEY, source TEXT, title TEXT, trigger TEXT,
            deaths INTEGER, missing INTEGER, injured INTEGER, conf_date REAL,
            conf_class REAL, specificity_reason TEXT, in_nepal INTEGER,
            scope_reason TEXT, location_consistent INTEGER, location_reason TEXT
        );
        """
    )
    conn.execute(
        'INSERT INTO article_events VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
        ('https://x/a', 'setopati', 'Landslide kills three', 'rainfall', 3, 0, 1,
         0.9, 0.95, 'event_specific', 1, 'district_match', 1, 'title_match'),
    )
    conn.execute(
        'INSERT INTO cluster_summary VALUES (?,?,?,?,?,?,?,?)',
        ('c1', 'Rasuwa', '2024-07-16', '2024-07-16', 2,
         '["setopati", "ekantipur"]', '["https://x/a"]', 'now'),
    )
    conn.execute(
        'INSERT INTO canonical_events VALUES (?,?,?,?,?,?,?,?,?,?,?)',
        ('e1', 'c1', '2024-07-16', 'Rasuwa', 'Bagmati', 'Uttargaya Rural Municipality',
         json.dumps({'representative_url': 'https://x/a'}), 'now', '[]', '[]', '["Rasuwa"]'),
    )
    return conn


def test_export_joins_cluster_and_representative_article(connection) -> None:
    rows = build_final_rows(connection)
    assert len(rows) == 1
    row = rows[0]
    assert row['cluster_size'] == 2
    assert row['representative_source'] == 'setopati'
    assert row['representative_title'] == 'Landslide kills three'
    assert row['deaths'] == 3
    assert row['specificity_reason'] == 'event_specific'
    assert row['location_reason'] == 'title_match'


def test_sources_json_is_compact(connection) -> None:
    """Matches the distributed file and utils.stable_hash's separators."""

    assert build_final_rows(connection)[0]['sources_json'] == '["setopati","ekantipur"]'


def test_export_schema_is_stable(connection) -> None:
    rows = build_final_rows(connection)
    assert list(rows[0].keys()) == FINAL_COLUMNS
    assert 'inserted_at' not in rows[0]


def test_export_is_chronological_and_deterministic(connection) -> None:
    """Ties must break on event_id or the published dataset reshuffles."""

    connection.execute(
        'INSERT INTO canonical_events VALUES (?,?,?,?,?,?,?,?,?,?,?)',
        ('e0', 'c1', '2015-04-07', 'Rasuwa', 'Bagmati', None, '{}', 'now', '[]', '[]', '[]'),
    )
    connection.execute(
        'INSERT INTO canonical_events VALUES (?,?,?,?,?,?,?,?,?,?,?)',
        ('e2', 'c1', '2015-04-07', 'Rasuwa', 'Bagmati', None, '{}', 'now', '[]', '[]', '[]'),
    )
    ids = [row['event_id'] for row in build_final_rows(connection)]
    assert ids == ['e0', 'e2', 'e1']
    assert ids == [row['event_id'] for row in build_final_rows(connection)], 'must be stable'


def test_write_is_byte_stable(connection, tmp_path: Path) -> None:
    rows = build_final_rows(connection)
    first = write_final_csv(rows, tmp_path / 'a.csv').read_bytes()
    second = write_final_csv(build_final_rows(connection), tmp_path / 'b.csv').read_bytes()
    assert first == second


def test_verify_detects_a_field_difference(tmp_path: Path) -> None:
    def _write(path: Path, deaths: str) -> Path:
        with path.open('w', encoding='utf-8', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=FINAL_COLUMNS)
            writer.writeheader()
            writer.writerow({**{c: '' for c in FINAL_COLUMNS}, 'event_id': 'e1', 'deaths': deaths})
        return path

    same = verify_export_matches(_write(tmp_path / 'a.csv', '3'), _write(tmp_path / 'b.csv', '3'))
    assert same['identical'] is True

    diff = verify_export_matches(_write(tmp_path / 'c.csv', '3'), _write(tmp_path / 'd.csv', '4'))
    assert diff['identical'] is False
    assert diff['mismatched_columns'] == {'deaths': 1}


def test_verify_reports_rows_present_on_only_one_side(tmp_path: Path) -> None:
    def _write(path: Path, event_ids: list[str]) -> Path:
        with path.open('w', encoding='utf-8', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=FINAL_COLUMNS)
            writer.writeheader()
            for event_id in event_ids:
                writer.writerow({**{c: '' for c in FINAL_COLUMNS}, 'event_id': event_id})
        return path

    result = verify_export_matches(
        _write(tmp_path / 'a.csv', ['e1', 'e2']), _write(tmp_path / 'b.csv', ['e1'])
    )
    assert result['identical'] is False
    assert result['only_in_generated'] == ['e2']


def test_final_export_gate_rejects_missing_event_typing(connection) -> None:
    with pytest.raises(RuntimeError, match='event_typing'):
        assert_event_typing_complete(connection)

    for column in ('event_type', 'hazard_type', 'event_granularity', 'article_role'):
        connection.execute(f'ALTER TABLE canonical_events ADD COLUMN {column} TEXT')
    with pytest.raises(RuntimeError, match='1 canonical events'):
        assert_event_typing_complete(connection)

    connection.execute(
        """
        UPDATE canonical_events
        SET event_type='landslide', hazard_type='landslide',
            event_granularity='single', article_role='first_report'
        """
    )
    assert_event_typing_complete(connection)
