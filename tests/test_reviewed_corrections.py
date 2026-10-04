"""Tests for the versioned post-validation correction layer."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from landslide_inventory.config import load_config
from landslide_inventory.db import connect_sqlite, initialize_sqlite
from landslide_inventory.unify.dedup_stage import load_dedup_events
from landslide_inventory.unify.reviewed_corrections import (
    apply_reviewed_corrections,
    load_reviewed_corrections,
)


def _insert_event(connection, url: str, index: int) -> None:
    connection.execute(
        """
        INSERT INTO raw_articles (
            url, source, title, published_date_ad, text, method
        ) VALUES (?, 'test', 'Landslide blocks road', '2026-08-22',
                  'A single landslide blocked the road in Nepal.', 'tag')
        """,
        (url,),
    )
    connection.execute(
        """
        INSERT INTO article_events (
            extracted_event_id, article_url, event_class, event_payload,
            url, source, title, published_date_ad, route_lang, class,
            event_date_ad, district, province, in_nepal, conf_class,
            conf_date, conf_district, conf_place, conf_fatalities, conf_trigger,
            specificity_ok, specificity_reason
        ) VALUES (?, ?, 1, '{}', ?, 'test', 'Landslide blocks road',
                  '2026-08-22', 'en', 1, '2026-08-22', 'Myagdi', 'Gandaki',
                  1, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 1, 'event_specific')
        """,
        (f'event-{index}', url, url),
    )


def test_reviewed_corrections_are_idempotent_audited_and_excluded_from_dedup(
    config_file: Path,
) -> None:
    config = load_config(config_file)
    correction_path = config.config_path.parent / 'article_corrections.csv'
    config.raw['validation']['article_corrections_path'] = str(correction_path)
    initialize_sqlite(config.sqlite_path)
    keep_url = 'https://example.test/correct-date'
    exclude_url = 'https://example.test/exclude'
    with connect_sqlite(config.sqlite_path) as connection:
        _insert_event(connection, keep_url, 1)
        _insert_event(connection, exclude_url, 2)
        connection.commit()
    correction_path.write_text(
        'url,reviewed_at,reviewed_by,evidence_url,correction_action,reason,'
        'published_date_ad,event_date_ad,in_nepal,exclude_from_canonical,'
        'scope_reason\n'
        f'{keep_url},2026-08-10,tester,https://evidence.test/1,correct_year,'
        'Verified duplicate,2025-08-22,2025-08-22,,0,\n'
        f'{exclude_url},2026-08-10,tester,https://evidence.test/2,exclude_foreign,'
        'Foreign event,2023-10-10,2023-10-03,0,1,reviewed_foreign_event\n',
        encoding='utf-8',
    )

    first = apply_reviewed_corrections(config)
    second = apply_reviewed_corrections(config)

    assert first['rows'] == second['rows'] == 2
    with connect_sqlite(config.sqlite_path) as connection:
        kept = connection.execute(
            'SELECT published_date_ad, event_date_ad FROM article_events WHERE url=?',
            (keep_url,),
        ).fetchone()
        excluded = connection.execute(
            """
            SELECT e.published_date_ad, e.event_date_ad, e.in_nepal,
                   c.exclude_from_canonical, c.before_json
            FROM article_events e
            JOIN reviewed_article_corrections c ON c.url=e.url
            WHERE e.url=?
            """,
            (exclude_url,),
        ).fetchone()
    assert tuple(kept) == ('2025-08-22', '2025-08-22')
    assert tuple(excluded)[:4] == ('2023-10-10', '2023-10-03', 0, 1)
    assert json.loads(excluded['before_json'])['event_date_ad'] == '2026-08-22'
    assert [event.url for event in load_dedup_events(config.sqlite_path)] == [keep_url]

    report_path = config.resolve_path('outputs_dir') / 'reviewed_corrections_applied.csv'
    with report_path.open(encoding='utf-8', newline='') as handle:
        report = list(csv.DictReader(handle))
    assert len(report) == 2
    assert all(row['corrections_sha256'] == first['sha256'] for row in report)


def test_reviewed_correction_can_repair_admin_location(config_file: Path) -> None:
    config = load_config(config_file)
    correction_path = config.config_path.parent / 'location_corrections.csv'
    config.raw['validation']['article_corrections_path'] = str(correction_path)
    initialize_sqlite(config.sqlite_path)
    url = 'https://example.test/parbat-road'
    with connect_sqlite(config.sqlite_path) as connection:
        _insert_event(connection, url, 1)
        connection.commit()
    correction_path.write_text(
        'url,reviewed_at,reviewed_by,evidence_url,correction_action,reason,'
        'published_date_ad,event_date_ad,district,province,municipality,in_nepal,'
        'exclude_from_canonical,scope_reason\n'
        f'{url},2026-09-26,human,{url},correct_location,Explicit location,,,'
        'Parbat,Gandaki Province,Kushma Municipality,,0,reviewed_location\n',
        encoding='utf-8',
    )

    apply_reviewed_corrections(config)

    with connect_sqlite(config.sqlite_path) as connection:
        row = connection.execute(
            'SELECT district, province, municipality FROM article_events WHERE url=?',
            (url,),
        ).fetchone()
    assert tuple(row) == ('Parbat', 'Gandaki Province', 'Kushma Municipality')


def test_reviewed_corrections_reject_shifted_extra_csv_fields(tmp_path: Path) -> None:
    path = tmp_path / 'shifted.csv'
    path.write_text(
        'url,reviewed_at,reviewed_by,evidence_url,correction_action,reason\n'
        'https://example.test/event,2026-09-29,human,https://example.test/event,'
        'correct_date,reviewed,unexpected\n',
        encoding='utf-8',
    )

    with pytest.raises(ValueError, match='unexpected extra CSV fields'):
        load_reviewed_corrections(path)
