"""SQLite persistence for scraping stages."""

from __future__ import annotations

import csv
from pathlib import Path

from ..db import connect_sqlite
from ..utils import ensure_directory, utc_now_iso
from .models import DiscoveredUrl, FetchResult, ParsedArticle
from .parser import text_looks_like_parser_noise


def upsert_discovered_url(database_path: Path, discovered: DiscoveredUrl) -> bool:
    """Insert a discovered URL idempotently and return whether it was newly inserted."""

    with connect_sqlite(database_path) as connection:
        existing = connection.execute(
            'SELECT 1 FROM discovered_urls WHERE url = ?',
            (discovered.url,),
        ).fetchone()
        connection.execute(
            """
            INSERT INTO discovered_urls (url, source, discovered_at, method, entry_point, query_term, year_hint)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(url) DO UPDATE SET
                source = excluded.source,
                method = excluded.method,
                entry_point = excluded.entry_point,
                query_term = excluded.query_term,
                year_hint = COALESCE(excluded.year_hint, discovered_urls.year_hint)
            """,
            (
                discovered.url,
                discovered.source,
                utc_now_iso(),
                discovered.method,
                discovered.entry_point,
                discovered.query_term,
                discovered.year_hint,
            ),
        )
        connection.commit()
    return existing is None


def discovered_urls_for_source(database_path: Path, source: str) -> set[str]:
    """Return all previously discovered URLs for a source."""

    with connect_sqlite(database_path) as connection:
        rows = connection.execute(
            'SELECT url FROM discovered_urls WHERE source = ?',
            (source,),
        ).fetchall()
    return {str(row['url']) for row in rows}


def raw_article_urls_for_source(database_path: Path, source: str) -> set[str]:
    """Return already fetched article URLs so interrupted crawls can resume."""

    with connect_sqlite(database_path) as connection:
        rows = connection.execute(
            'SELECT url FROM raw_articles WHERE source = ?',
            (source,),
        ).fetchall()
    return {str(row['url']) for row in rows}


def count_discovered_urls_for_source(database_path: Path, source: str) -> int:
    """Return the total discovered URL count for a source."""

    with connect_sqlite(database_path) as connection:
        row = connection.execute(
            'SELECT COUNT(*) AS total FROM discovered_urls WHERE source = ?',
            (source,),
        ).fetchone()
    return int(row['total'])


def stale_raw_article_urls_for_source(database_path: Path, source: str, *, limit: int = 200) -> list[str]:
    """Return stored article URLs whose parsed text still looks like parser noise."""

    with connect_sqlite(database_path) as connection:
        rows = connection.execute(
            'SELECT url, COALESCE(text, "") AS text FROM raw_articles WHERE source = ? ORDER BY fetched_at DESC',
            (source,),
        ).fetchall()
    stale: list[str] = []
    for row in rows:
        if text_looks_like_parser_noise(str(row['text'] or '')):
            stale.append(str(row['url']))
            if len(stale) >= limit:
                break
    return stale


def upsert_raw_article(
    database_path: Path,
    source: str,
    url: str,
    fetch_result: FetchResult,
    parsed: ParsedArticle,
    method: str,
    entry_point: str,
) -> None:
    """Insert or update a fetched raw article idempotently."""

    with connect_sqlite(database_path) as connection:
        connection.execute(
            """
            INSERT INTO raw_articles (
                url, source, title, published_date_raw, published_date_ad, text,
                fetched_at, http_status, parse_success, method, entry_point
            )
            VALUES (?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(url) DO UPDATE SET
                source = excluded.source,
                title = excluded.title,
                published_date_raw = excluded.published_date_raw,
                text = excluded.text,
                fetched_at = excluded.fetched_at,
                http_status = excluded.http_status,
                parse_success = excluded.parse_success,
                method = excluded.method,
                entry_point = excluded.entry_point
            """,
            (
                url,
                source,
                parsed.title,
                parsed.published_date_raw,
                parsed.text,
                fetch_result.fetched_at,
                fetch_result.status_code,
                int(parsed.parse_success),
                method,
                entry_point,
            ),
        )
        connection.commit()


def write_coverage_report(database_path: Path, output_path: Path) -> Path:
    """Write the source-year coverage report."""

    ensure_directory(output_path.parent)
    rows = coverage_rows(database_path)
    with output_path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                'source',
                'year',
                'discovered_url_count',
                'fetched_ok_count',
                'parsed_ok_count',
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return output_path


def coverage_rows(database_path: Path) -> list[dict[str, int | str]]:
    """Compute coverage metrics per source-year."""

    with connect_sqlite(database_path) as connection:
        discovered_rows = connection.execute(
            """
            SELECT source, year_hint AS year, COUNT(*) AS discovered_url_count
            FROM discovered_urls
            WHERE year_hint BETWEEN 2015 AND 2026
            GROUP BY source, year_hint
            """
        ).fetchall()
        raw_rows = connection.execute(
            """
            SELECT source, year, fetched_ok_count, parsed_ok_count
            FROM (
                SELECT
                    source,
                    CAST(SUBSTR(COALESCE(published_date_raw, fetched_at), 1, 4) AS INTEGER) AS year,
                    SUM(CASE WHEN http_status BETWEEN 200 AND 299 THEN 1 ELSE 0 END) AS fetched_ok_count,
                    SUM(CASE WHEN parse_success = 1 THEN 1 ELSE 0 END) AS parsed_ok_count
                FROM raw_articles
                GROUP BY source, CAST(SUBSTR(COALESCE(published_date_raw, fetched_at), 1, 4) AS INTEGER)
            )
            WHERE year BETWEEN 2015 AND 2026
            """
        ).fetchall()
    merged: dict[tuple[str, int], dict[str, int | str]] = {}
    for row in discovered_rows:
        key = (str(row['source']), int(row['year']))
        merged[key] = {
            'source': key[0],
            'year': key[1],
            'discovered_url_count': int(row['discovered_url_count']),
            'fetched_ok_count': 0,
            'parsed_ok_count': 0,
        }
    for row in raw_rows:
        key = (str(row['source']), int(row['year']))
        record = merged.setdefault(
            key,
            {
                'source': key[0],
                'year': key[1],
                'discovered_url_count': 0,
                'fetched_ok_count': 0,
                'parsed_ok_count': 0,
            },
        )
        record['fetched_ok_count'] = int(row['fetched_ok_count'] or 0)
        record['parsed_ok_count'] = int(row['parsed_ok_count'] or 0)
    return [merged[key] for key in sorted(merged)]
