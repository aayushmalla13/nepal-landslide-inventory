"""Tests for published-date normalization."""

from __future__ import annotations

from pathlib import Path

from landslide_inventory.config import load_config
from landslide_inventory.db import connect_sqlite, initialize_sqlite
from landslide_inventory.preprocess.dates import (
    bs_to_ad,
    detect_bs_date,
    devanagari_to_ascii_digits,
    extract_date_from_url,
    normalize_dates_in_sqlite,
    normalize_published_date,
)


def test_normalize_published_date_supports_english_formats() -> None:
    assert normalize_published_date('July 14, 2021', 'en') == '2021-07-14'
    assert normalize_published_date('2021-07-14T08:00:00+05:45', 'en') == '2021-07-14'


def test_year_hint_does_not_truncate_day_in_complete_english_date() -> None:
    assert (
        normalize_published_date('October 11, 2022', 'en', year_hint=2022)
        == '2022-10-11'
    )


def test_devanagari_to_ascii_digits_converts_digits() -> None:
    assert devanagari_to_ascii_digits('२०८०-०१-०१') == '2080-01-01'


def test_detect_bs_date_handles_devanagari_digits() -> None:
    assert detect_bs_date('प्रकाशित: २०८०-०१-०१') == (2080, 1, 1)


def test_bs_to_ad_converts_known_example() -> None:
    assert bs_to_ad((2080, 1, 1)).isoformat() == '2023-04-14'


def test_normalize_published_date_uses_bs_for_nepali_source() -> None:
    assert normalize_published_date('२०८०-०१-०१', 'np') == '2023-04-14'


def test_extract_date_from_url_reads_iso_date_path() -> None:
    assert (
        extract_date_from_url('https://kathmandupost.com/national/2026/03/24/example-story')
        == '2026-03-24'
    )


def test_normalize_dates_stage_updates_sqlite_rows(config_file: Path) -> None:
    config = load_config(config_file)
    initialize_sqlite(config.sqlite_path)
    with connect_sqlite(config.sqlite_path) as connection:
        connection.execute(
            '''
            INSERT INTO raw_articles (
                url, source, title, published_date_raw, published_date_ad, text,
                fetched_at, http_status, parse_success, method, entry_point
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                'https://example.com/story',
                'kathmandu-post',
                'Example',
                'July 14, 2021',
                None,
                'story body',
                '2026-03-04T00:00:00+00:00',
                200,
                1,
                'tag',
                'https://example.com/tag',
            ),
        )
        connection.commit()
    updated = normalize_dates_in_sqlite(config)
    assert updated == 1
    with connect_sqlite(config.sqlite_path) as connection:
        row = connection.execute(
            'SELECT published_date_ad FROM raw_articles WHERE url = ?',
            ('https://example.com/story',),
        ).fetchone()
    assert row['published_date_ad'] == '2021-07-14'


def test_normalize_dates_stage_backfills_raw_date_from_url(config_file: Path) -> None:
    config = load_config(config_file)
    initialize_sqlite(config.sqlite_path)
    with connect_sqlite(config.sqlite_path) as connection:
        connection.execute(
            '''
            INSERT INTO raw_articles (
                url, source, title, published_date_raw, published_date_ad, text,
                fetched_at, http_status, parse_success, method, entry_point
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                'https://kathmandupost.com/national/2026/03/24/example-story',
                'kathmandu-post',
                'Example',
                None,
                None,
                'story body',
                '2026-03-04T00:00:00+00:00',
                200,
                1,
                'tag',
                'https://example.com/tag',
            ),
        )
        connection.commit()
    updated = normalize_dates_in_sqlite(config)
    assert updated == 1
    with connect_sqlite(config.sqlite_path) as connection:
        row = connection.execute(
            'SELECT published_date_raw, published_date_ad FROM raw_articles WHERE url = ?',
            ('https://kathmandupost.com/national/2026/03/24/example-story',),
        ).fetchone()
    assert row['published_date_raw'] == '2026-03-24'
    assert row['published_date_ad'] == '2026-03-24'


def test_detect_bs_date_handles_nepali_month_name() -> None:
    assert detect_bs_date('प्रकाशित मिति: आइतबार, साउन ४, २०८२ १६:३४') == (2082, 4, 4)


def test_normalize_published_date_handles_setopati_bs_text() -> None:
    assert normalize_published_date('आइतबार, साउन ४, २०८२ १६:३४', 'np') == '2025-07-20'


def test_detect_bs_date_rejects_invalid_numeric_values() -> None:
    assert detect_bs_date('2081-11-76') is None



def test_normalize_published_date_uses_year_hint_for_english_lead_text() -> None:
    assert (
        normalize_published_date('Kimathanka, June 1 (RSS): Two people were buried in a landslide.', 'en', year_hint=2022)
        == '2022-06-01'
    )


def test_normalize_published_date_uses_year_hint_for_nepali_month_day_text() -> None:
    assert (
        normalize_published_date('१९ साउन, काठमाडौं । पहिरोले घर पुर्दा मृत्यु।', 'np', year_hint=2023)
        == '2023-08-04'
    )


def test_normalize_dates_stage_repairs_mismatched_year_with_text_hint(config_file: Path) -> None:
    config = load_config(config_file)
    initialize_sqlite(config.sqlite_path)
    with connect_sqlite(config.sqlite_path) as connection:
        connection.execute(
            '''
            INSERT INTO raw_articles (
                url, source, title, published_date_raw, published_date_ad, text,
                fetched_at, http_status, parse_success, method, entry_point
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                'https://www.onlinekhabar.com/2023/08/example-story',
                'online-khabar',
                'Example',
                '2025-11-19',
                '2025-11-19',
                '१९ साउन, काठमाडौं । पहिरोले घर पुर्दा बाबु-छोरीको मृत्यु भएको छ।',
                '2026-03-04T00:00:00+00:00',
                200,
                1,
                'tag',
                'https://example.com/tag',
            ),
        )
        connection.execute(
            '''
            INSERT INTO discovered_urls (url, source, discovered_at, method, entry_point, year_hint)
            VALUES (?, ?, ?, ?, ?, ?)
            ''',
            (
                'https://www.onlinekhabar.com/2023/08/example-story',
                'online-khabar',
                '2026-03-04T00:00:00+00:00',
                'tag',
                'https://example.com/tag',
                2023,
            ),
        )
        connection.commit()
    updated = normalize_dates_in_sqlite(config)
    assert updated == 1
    with connect_sqlite(config.sqlite_path) as connection:
        row = connection.execute(
            'SELECT published_date_ad FROM raw_articles WHERE url = ?',
            ('https://www.onlinekhabar.com/2023/08/example-story',),
        ).fetchone()
    assert row['published_date_ad'] == '2023-08-04'


def test_normalize_dates_stage_prefers_url_year_over_bad_discovery_hint(config_file: Path) -> None:
    config = load_config(config_file)
    initialize_sqlite(config.sqlite_path)
    with connect_sqlite(config.sqlite_path) as connection:
        connection.execute(
            '''
            INSERT INTO raw_articles (
                url, source, title, published_date_raw, published_date_ad, text,
                fetched_at, http_status, parse_success, method, entry_point
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                'https://www.onlinekhabar.com/2025/08/example-story',
                'online-khabar',
                'Example',
                None,
                '2024-08-23',
                '७ भदौ, काठमाडौं । अविरल वर्षाका कारण पहिरो गएको छ।',
                '2026-03-04T00:00:00+00:00',
                200,
                1,
                'tag',
                'https://example.com/tag',
            ),
        )
        connection.execute(
            '''
            INSERT INTO discovered_urls (url, source, discovered_at, method, entry_point, year_hint)
            VALUES (?, ?, ?, ?, ?, ?)
            ''',
            (
                'https://www.onlinekhabar.com/2025/08/example-story',
                'online-khabar',
                '2026-03-04T00:00:00+00:00',
                'tag',
                'https://example.com/tag',
                2024,
            ),
        )
        connection.commit()
    updated = normalize_dates_in_sqlite(config)
    assert updated == 1
    with connect_sqlite(config.sqlite_path) as connection:
        row = connection.execute(
            'SELECT published_date_ad FROM raw_articles WHERE url = ?',
            ('https://www.onlinekhabar.com/2025/08/example-story',),
        ).fetchone()
    assert row['published_date_ad'] == '2025-08-23'


def test_normalize_dates_stage_prefers_nepali_text_candidate_over_machine_raw(config_file: Path) -> None:
    config = load_config(config_file)
    initialize_sqlite(config.sqlite_path)
    with connect_sqlite(config.sqlite_path) as connection:
        connection.execute(
            '''
            INSERT INTO raw_articles (
                url, source, title, published_date_raw, published_date_ad, text,
                fetched_at, http_status, parse_success, method, entry_point
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                'https://www.onlinekhabar.com/2025/08/example-machine-date',
                'online-khabar',
                'Example',
                '2025-11-19',
                '2025-11-19',
                '''{{data.tags[i].name}} सबै रिज्ल्ट हेर्नुस + क्रिकेट

News Summary
५ भदौ, काभ्रेपलाञ्चोक । पहिरोले सडक अबरुद्ध हुँदा सडक सञ्चालनमा आएको छ ।''',
                '2026-03-04T00:00:00+00:00',
                200,
                1,
                'tag',
                'https://example.com/tag',
            ),
        )
        connection.commit()
    updated = normalize_dates_in_sqlite(config)
    assert updated == 1
    with connect_sqlite(config.sqlite_path) as connection:
        row = connection.execute(
            'SELECT published_date_ad FROM raw_articles WHERE url = ?',
            ('https://www.onlinekhabar.com/2025/08/example-machine-date',),
        ).fetchone()
    assert row['published_date_ad'] == '2025-08-21'


def test_normalize_dates_stage_prefers_rising_nepal_lead_text_over_stale_visible_date(config_file: Path) -> None:
    config = load_config(config_file)
    initialize_sqlite(config.sqlite_path)
    with connect_sqlite(config.sqlite_path) as connection:
        connection.execute(
            '''
            INSERT INTO raw_articles (
                url, source, title, published_date_raw, published_date_ad, text,
                fetched_at, http_status, parse_success, method, entry_point
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                "https://risingnepaldaily.com/news/11980",
                "rising-nepal",
                "Two buried to death in landslide in Sankhuwasabha",
                "Wednesday, 1 April 2026",
                "2022-04-20",
                "Kimathanka, June 1 (RSS): Two people have been buried to death in a landslide today morning.",
                "2026-03-04T00:00:00+00:00",
                200,
                1,
                "tag",
                "https://example.com/tag",
            ),
        )
        connection.execute(
            '''
            INSERT INTO discovered_urls (url, source, discovered_at, method, entry_point, year_hint)
            VALUES (?, ?, ?, ?, ?, ?)
            ''',
            (
                "https://risingnepaldaily.com/news/11980",
                "rising-nepal",
                "2026-03-04T00:00:00+00:00",
                "googlenews",
                "https://example.com/feed",
                2022,
            ),
        )
        connection.commit()
    updated = normalize_dates_in_sqlite(config)
    assert updated == 1
    with connect_sqlite(config.sqlite_path) as connection:
        row = connection.execute(
            "SELECT published_date_ad FROM raw_articles WHERE url = ?",
            ("https://risingnepaldaily.com/news/11980",),
        ).fetchone()
    assert row["published_date_ad"] == "2022-06-01"
