"""Tests for language routing."""

from __future__ import annotations

from landslide_inventory.config import load_config
from landslide_inventory.db import connect_sqlite, initialize_sqlite
from landslide_inventory.langdetect.router import devanagari_ratio, route_language, run_language_stage


def test_devanagari_ratio_is_zero_for_english_text() -> None:
    assert devanagari_ratio('Heavy rain triggered a landslide in Sindhupalchok.') == 0.0


def test_route_language_routes_nepali_text_to_np(config_file) -> None:
    config = load_config(config_file)
    result = route_language('सिन्धुपाल्चोकमा पहिरो जाँदा दुई जनाको मृत्यु भयो।', config)
    assert result.route_lang == 'np'
    assert result.mixed_flag is False
    assert result.devanagari_ratio > 0.30


def test_route_language_marks_threshold_band_as_mixed(config_file) -> None:
    config = load_config(config_file)
    text = 'Landslide update काठमाडौं road blocked due to पहिरो after heavy rain.'
    result = route_language(text, config)
    assert 0.10 <= result.devanagari_ratio <= 0.30
    assert result.route_lang == 'np'
    assert result.mixed_flag is True


def test_run_language_stage_writes_sqlite_rows(config_file) -> None:
    config = load_config(config_file)
    initialize_sqlite(config.sqlite_path)
    with connect_sqlite(config.sqlite_path) as connection:
        connection.executemany(
            """
            INSERT INTO raw_articles (
                url, source, title, published_date_raw, published_date_ad, text,
                fetched_at, http_status, parse_success, method, entry_point
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    'https://example.com/en-story',
                    'kathmandu-post',
                    'EN story',
                    '2024-07-01',
                    '2024-07-01',
                    'A landslide killed two people in Sindhupalchok district.',
                    '2026-03-27T00:00:00+00:00',
                    200,
                    1,
                    'tag',
                    'https://example.com/tag',
                ),
                (
                    'https://example.com/np-story',
                    'setopati',
                    'NP story',
                    '२०८१-०४-०१',
                    '2024-07-16',
                    'रामेछापमा पहिरो जाँदा सडक अवरुद्ध भएको छ।',
                    '2026-03-27T00:00:00+00:00',
                    200,
                    1,
                    'tag',
                    'https://example.com/tag',
                ),
            ],
        )
        connection.commit()
    routed = run_language_stage(config)
    assert routed == 2
    with connect_sqlite(config.sqlite_path) as connection:
        rows = connection.execute(
            'SELECT url, route_lang, mixed_flag FROM article_lang ORDER BY url'
        ).fetchall()
    assert [(row['url'], row['route_lang'], row['mixed_flag']) for row in rows] == [
        ('https://example.com/en-story', 'en', 0),
        ('https://example.com/np-story', 'np', 0),
    ]
