"""Tests for the non-destructive decision log.

The property these tests exist to protect: after a filter stage demotes a row
and NULLs its fields, you can still recover what the extractor originally
found. Losing that is what made the ``by landslide`` bug invisible for so long
(docs/TECHNICAL_REVIEW.md section 2.2).
"""

from __future__ import annotations

import json
import sqlite3

import pytest

from landslide_inventory.unify.decisions import (
    PRESERVED_FIELDS,
    ensure_decisions_table,
    load_preserved_fields,
    preserved_field_recovery_rate,
    record_decision,
    restore_preserved_fields,
    snapshot_fields,
)


@pytest.fixture()
def connection() -> sqlite3.Connection:
    conn = sqlite3.connect(':memory:')
    columns = ', '.join(f'"{field}"' for field in PRESERVED_FIELDS)
    conn.execute(f'CREATE TABLE article_events (url TEXT PRIMARY KEY, {columns})')
    ensure_decisions_table(conn)
    return conn


def _insert_event(conn: sqlite3.Connection, url: str, **values: object) -> None:
    fields = ['url', *values]
    placeholders = ', '.join('?' for _ in fields)
    quoted = ', '.join(f'"{f}"' for f in fields)
    conn.execute(
        f'INSERT INTO article_events ({quoted}) VALUES ({placeholders})',
        [url, *values.values()],
    )


def test_snapshot_captures_extractor_fields(connection) -> None:
    _insert_event(connection, 'u1', district='Sindhupalchok', deaths=3, event_date_ad='2024-07-16')
    snapshot = snapshot_fields(connection, 'u1')
    assert snapshot['district'] == 'Sindhupalchok'
    assert snapshot['deaths'] == 3
    assert set(snapshot) == set(PRESERVED_FIELDS)


def test_snapshot_of_missing_url_is_empty(connection) -> None:
    assert snapshot_fields(connection, 'nope') == {}


def test_decision_survives_a_destructive_update(connection) -> None:
    """The core guarantee: demotion nulls the row, the log still has the truth."""

    _insert_event(connection, 'u1', district='Sindhupalchok', deaths=3, event_date_ad='2024-07-16')
    record_decision(
        connection, url='u1', stage='event_specificity', decision=0,
        reason='metaphor', score=0.2, updated_class=3,
        preserved=snapshot_fields(connection, 'u1'),
    )
    # Simulate the stage's destructive UPDATE.
    connection.execute(
        'UPDATE article_events SET district = NULL, deaths = NULL, event_date_ad = NULL WHERE url = ?',
        ('u1',),
    )
    assert connection.execute('SELECT district FROM article_events WHERE url = ?', ('u1',)).fetchone()[0] is None

    preserved = load_preserved_fields(connection, 'event_specificity')
    assert preserved['u1']['district'] == 'Sindhupalchok'
    assert preserved['u1']['deaths'] == 3


def test_rerun_does_not_overwrite_the_original_snapshot(connection) -> None:
    """Idempotency guarantee.

    A second run sees NULLed fields. If it overwrote the snapshot with those
    NULLs, the log would silently lose exactly the data it exists to keep.
    """

    _insert_event(connection, 'u1', district='Sindhupalchok', deaths=3)
    record_decision(
        connection, url='u1', stage='event_specificity', decision=0, reason='metaphor',
        score=0.2, preserved=snapshot_fields(connection, 'u1'),
    )
    connection.execute('UPDATE article_events SET district = NULL, deaths = NULL WHERE url = ?', ('u1',))

    # Second run: snapshot is now all-NULL.
    record_decision(
        connection, url='u1', stage='event_specificity', decision=0, reason='insufficient_signal',
        score=0.1, preserved=snapshot_fields(connection, 'u1'),
    )

    row = connection.execute(
        'SELECT reason, preserved_fields_json FROM article_decisions WHERE url = ? AND stage = ?',
        ('u1', 'event_specificity'),
    ).fetchone()
    assert row[0] == 'insufficient_signal', 'the decision itself should refresh'
    assert json.loads(row[1])['district'] == 'Sindhupalchok', 'the snapshot must not be overwritten'


def test_only_one_row_per_url_and_stage(connection) -> None:
    _insert_event(connection, 'u1', district='Dhading')
    for _ in range(3):
        record_decision(connection, url='u1', stage='filter_scope', decision=0, reason='out_of_country')
    count = connection.execute('SELECT COUNT(*) FROM article_decisions').fetchone()[0]
    assert count == 1


def test_stages_are_logged_independently(connection) -> None:
    _insert_event(connection, 'u1', district='Dhading')
    record_decision(connection, url='u1', stage='filter_scope', decision=1, reason='nepal_keyword')
    record_decision(connection, url='u1', stage='event_specificity', decision=0, reason='roundup')
    stages = {r[0] for r in connection.execute('SELECT stage FROM article_decisions')}
    assert stages == {'filter_scope', 'event_specificity'}


def test_restore_fills_only_nulls(connection) -> None:
    """A later stage that legitimately set a value must win over the snapshot."""

    current = {'district': None, 'deaths': 5, 'event_date_ad': None}
    preserved = {'district': 'Rasuwa', 'deaths': 2, 'event_date_ad': '2024-07-16'}
    restored = restore_preserved_fields(current, preserved)
    assert restored['district'] == 'Rasuwa', 'NULL should be filled from the snapshot'
    assert restored['deaths'] == 5, 'a present value must not be clobbered'
    assert restored['event_date_ad'] == '2024-07-16'


def test_restore_is_a_noop_without_preserved_values() -> None:
    current = {'district': None}
    assert restore_preserved_fields(current, None) == current
    assert restore_preserved_fields(current, {}) == current


def test_recovery_rate_reports_honestly(connection) -> None:
    """Rows demoted before the log existed have no recoverable provenance.

    The reporter must say so rather than implying the log is complete.
    """

    _insert_event(connection, 'good', district='Rasuwa')
    _insert_event(connection, 'already_nulled')  # pre-existing demoted row
    record_decision(connection, url='good', stage='event_specificity', decision=0,
                    reason='metaphor', preserved=snapshot_fields(connection, 'good'))
    record_decision(connection, url='already_nulled', stage='event_specificity', decision=0,
                    reason='metaphor', preserved=snapshot_fields(connection, 'already_nulled'))

    report = preserved_field_recovery_rate(connection, 'event_specificity')
    assert report['rows'] == 2
    assert report['recoverable']['district'] == 1


def test_preserved_fields_match_what_the_stages_null() -> None:
    """Guards against a column being added to the UPDATE but not to the log.

    If a stage nulls a column that PRESERVED_FIELDS does not list, that column's
    provenance is silently lost. This asserts the two stay in sync.
    """

    from pathlib import Path
    import re

    root = Path(__file__).resolve().parents[1] / 'src' / 'landslide_inventory' / 'unify'
    nulled: set[str] = set()
    for name in ('event_specificity.py', 'scope_filter.py'):
        source = (root / name).read_text(encoding='utf-8')
        nulled |= set(re.findall(r'(\w+) = CASE WHEN \? = 3 THEN NULL', source))
    missing = nulled - set(PRESERVED_FIELDS)
    assert missing == set(), (
        f'These columns are nulled on demotion but not preserved: {sorted(missing)}. '
        'Add them to PRESERVED_FIELDS or their provenance is lost.'
    )
