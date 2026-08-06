"""SQLite helpers and schema migrations."""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS pipeline_runs (
        run_id TEXT PRIMARY KEY,
        stage TEXT NOT NULL,
        status TEXT NOT NULL,
        started_at TEXT NOT NULL,
        completed_at TEXT,
        config_hash TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS discovered_urls (
        url TEXT PRIMARY KEY,
        source TEXT NOT NULL,
        discovered_at TEXT NOT NULL,
        method TEXT NOT NULL,
        entry_point TEXT,
        query_term TEXT,
        year_hint INTEGER
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS raw_articles (
        url TEXT PRIMARY KEY,
        source TEXT NOT NULL,
        title TEXT,
        published_date_raw TEXT,
        published_date_ad TEXT,
        text TEXT,
        fetched_at TEXT,
        http_status INTEGER,
        parse_success INTEGER NOT NULL DEFAULT 0,
        method TEXT,
        entry_point TEXT,
        inserted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS article_lang (
        url TEXT PRIMARY KEY,
        source TEXT NOT NULL,
        devanagari_ratio REAL NOT NULL,
        langdetect_label TEXT NOT NULL,
        route_lang TEXT NOT NULL,
        mixed_flag INTEGER NOT NULL DEFAULT 0,
        computed_at TEXT NOT NULL,
        FOREIGN KEY(url) REFERENCES raw_articles(url)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS article_scope (
        url TEXT PRIMARY KEY,
        in_nepal INTEGER NOT NULL,
        scope_reason TEXT NOT NULL,
        scope_score REAL NOT NULL,
        decided_at TEXT NOT NULL,
        FOREIGN KEY(url) REFERENCES raw_articles(url)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS article_decisions (
        url TEXT NOT NULL,
        stage TEXT NOT NULL,
        decision INTEGER NOT NULL,
        reason TEXT NOT NULL,
        score REAL,
        updated_class INTEGER,
        preserved_fields_json TEXT,
        first_decided_at TEXT NOT NULL,
        decided_at TEXT NOT NULL,
        PRIMARY KEY (url, stage)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_article_decisions_stage_reason
        ON article_decisions (stage, reason)
    """,
    """
    CREATE TABLE IF NOT EXISTS article_specificity (
        url TEXT PRIMARY KEY,
        specificity_ok INTEGER NOT NULL,
        specificity_reason TEXT NOT NULL,
        specificity_score REAL NOT NULL,
        decided_at TEXT NOT NULL,
        FOREIGN KEY(url) REFERENCES raw_articles(url)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS article_location_check (
        url TEXT PRIMARY KEY,
        location_consistent INTEGER NOT NULL,
        location_reason TEXT NOT NULL,
        title_district TEXT,
        title_municipality TEXT,
        checked_at TEXT NOT NULL,
        FOREIGN KEY(url) REFERENCES raw_articles(url)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS article_events (
        extracted_event_id TEXT PRIMARY KEY,
        article_url TEXT NOT NULL,
        event_class INTEGER NOT NULL,
        municipality TEXT,
        ward TEXT,
        place_name_raw TEXT,
        place_candidates_json TEXT,
        conf_place REAL,
        event_payload TEXT NOT NULL,
        inserted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(article_url) REFERENCES raw_articles(url)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS canonical_events (
        event_id TEXT PRIMARY KEY,
        dedup_cluster_id TEXT NOT NULL,
        event_date_ad TEXT,
        district TEXT,
        province TEXT,
        municipality TEXT,
        municipality_candidates_json TEXT,
        ward_candidates_json TEXT,
        place_name_candidates_json TEXT,
        event_payload TEXT NOT NULL,
        inserted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS cluster_summary (
        cluster_id TEXT PRIMARY KEY,
        district TEXT NOT NULL,
        date_min TEXT NOT NULL,
        date_max TEXT NOT NULL,
        size INTEGER NOT NULL,
        sources TEXT NOT NULL,
        urls TEXT NOT NULL,
        inserted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
)

REQUIRED_RAW_ARTICLE_COLUMNS = {
    'url': 'TEXT PRIMARY KEY',
    'source': 'TEXT NOT NULL',
    'title': 'TEXT',
    'published_date_raw': 'TEXT',
    'published_date_ad': 'TEXT',
    'text': 'TEXT',
    'fetched_at': 'TEXT',
    'http_status': 'INTEGER',
    'parse_success': 'INTEGER NOT NULL DEFAULT 0',
    'method': 'TEXT',
    'entry_point': 'TEXT',
}


REQUIRED_CANONICAL_EVENT_COLUMNS = {
    'event_id': 'TEXT PRIMARY KEY',
    'dedup_cluster_id': 'TEXT NOT NULL',
    'event_date_ad': 'TEXT',
    'district': 'TEXT',
    'province': 'TEXT',
    'municipality': 'TEXT',
    'municipality_candidates_json': 'TEXT',
    'ward_candidates_json': 'TEXT',
    'place_name_candidates_json': 'TEXT',
    'event_payload': 'TEXT NOT NULL DEFAULT ""',
    'inserted_at': 'TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP',
}

REQUIRED_ARTICLE_EVENT_COLUMNS = {
    'url': 'TEXT',
    'source': 'TEXT',
    'title': 'TEXT',
    'published_date_raw': 'TEXT',
    'published_date_ad': 'TEXT',
    'route_lang': 'TEXT',
    'mixed_flag': 'INTEGER NOT NULL DEFAULT 0',
    'class': 'INTEGER',
    'event_date_ad': 'TEXT',
    'district': 'TEXT',
    'province': 'TEXT',
    'municipality': 'TEXT',
    'ward': 'TEXT',
    'place_admin_level': 'TEXT',
    'place_name_raw': 'TEXT',
    'place_candidates_json': 'TEXT',
    'deaths': 'INTEGER',
    'missing': 'INTEGER',
    'injured': 'INTEGER',
    'trigger': 'TEXT',
    'conf_class': 'REAL',
    'conf_date': 'REAL',
    'conf_district': 'REAL',
    'conf_place': 'REAL',
    'conf_fatalities': 'REAL',
    'conf_trigger': 'REAL',
    'extracted_at': 'TEXT',
    'in_nepal': 'INTEGER',
    'scope_reason': 'TEXT',
    'specificity_ok': 'INTEGER',
    'specificity_reason': 'TEXT',
    'specificity_score': 'REAL',
    'location_consistent': 'INTEGER',
    'location_reason': 'TEXT',
    'dedup_cluster_id': 'TEXT',
    'extracted_event_id': 'TEXT PRIMARY KEY',
    'article_url': 'TEXT NOT NULL',
    'event_class': 'INTEGER NOT NULL',
    'event_payload': 'TEXT NOT NULL DEFAULT ""',
    'inserted_at': 'TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP',
}


def connect_sqlite(database_path: Path) -> sqlite3.Connection:
    """Create a SQLite connection with row access enabled."""

    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_sqlite(database_path: Path) -> None:
    """Create the SQLite database and ensure required tables exist."""

    database_path.parent.mkdir(parents=True, exist_ok=True)
    with connect_sqlite(database_path) as connection:
        for statement in SCHEMA_STATEMENTS:
            connection.execute(statement)
        _migrate_raw_articles(connection)
        _migrate_article_events(connection)
        _migrate_canonical_events(connection)
        connection.commit()


def list_tables(database_path: Path) -> list[str]:
    """Return SQLite table names in deterministic order."""

    with connect_sqlite(database_path) as connection:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name ASC"
        ).fetchall()
    return [str(row['name']) for row in rows]


def _migrate_raw_articles(connection: sqlite3.Connection) -> None:
    """Add required columns to raw_articles if an older schema exists."""

    columns = {str(row['name']) for row in connection.execute('PRAGMA table_info(raw_articles)').fetchall()}
    for column, definition in REQUIRED_RAW_ARTICLE_COLUMNS.items():
        if column in columns:
            continue
        connection.execute(f'ALTER TABLE raw_articles ADD COLUMN {column} {definition}')


def _migrate_article_events(connection: sqlite3.Connection) -> None:
    """Add required columns and indexes to article_events if an older schema exists."""

    columns = {str(row['name']) for row in connection.execute('PRAGMA table_info(article_events)').fetchall()}
    for column, definition in REQUIRED_ARTICLE_EVENT_COLUMNS.items():
        if column in columns:
            continue
        if 'PRIMARY KEY' in definition:
            continue
        connection.execute(f'ALTER TABLE article_events ADD COLUMN {column} {definition}')
    connection.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_article_events_url ON article_events(url)')


def _migrate_canonical_events(connection: sqlite3.Connection) -> None:
    """Add required columns to canonical_events if an older schema exists."""

    columns = {str(row['name']) for row in connection.execute('PRAGMA table_info(canonical_events)').fetchall()}
    for column, definition in REQUIRED_CANONICAL_EVENT_COLUMNS.items():
        if column in columns:
            continue
        if 'PRIMARY KEY' in definition:
            continue
        connection.execute(f'ALTER TABLE canonical_events ADD COLUMN {column} {definition}')
