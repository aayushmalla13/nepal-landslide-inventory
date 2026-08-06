"""Tests for the pre-BIPAD inventory audit stage."""

from __future__ import annotations

import json

from landslide_inventory.config import load_config
from landslide_inventory.db import connect_sqlite, initialize_sqlite
from landslide_inventory.validation.inventory_audit import run_inventory_audit_stage


def test_inventory_audit_stage_writes_expected_outputs(config_file) -> None:
    config = load_config(config_file)
    initialize_sqlite(config.sqlite_path)
    with connect_sqlite(config.sqlite_path) as connection:
        connection.execute(
            """
            INSERT INTO raw_articles (url, source, title, published_date_ad, text, parse_success)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                'https://example.com/article-1',
                'myrepublica',
                'Landslide kills three in Dhading',
                '2024-07-16',
                'A rainfall-triggered landslide hit Dhading.',
                1,
            ),
        )
        connection.execute(
            """
            INSERT INTO article_lang (url, source, devanagari_ratio, langdetect_label, route_lang, mixed_flag, computed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ('https://example.com/article-1', 'myrepublica', 0.0, 'en', 'en', 0, '2026-03-28T00:00:00Z'),
        )
        connection.execute(
            """
            INSERT INTO article_events (
                url, source, title, published_date_ad, route_lang, mixed_flag, class,
                event_date_ad, district, province, municipality, place_admin_level,
                place_name_raw, place_candidates_json, deaths, trigger,
                conf_class, conf_date, conf_district, conf_place, conf_fatalities, conf_trigger,
                extracted_at, in_nepal, scope_reason, specificity_ok, specificity_reason,
                specificity_score, location_consistent, location_reason, dedup_cluster_id,
                extracted_event_id, article_url, event_class, event_payload
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                'https://example.com/article-1',
                'myrepublica',
                'Landslide kills three in Dhading',
                '2024-07-16',
                'en',
                0,
                1,
                '2024-07-16',
                'Dhading',
                'Bagmati',
                'Nilkantha Municipality',
                'municipality',
                'Nilkantha Municipality',
                '["Nilkantha Municipality"]',
                3,
                'rainfall',
                0.9,
                0.8,
                0.9,
                0.8,
                0.9,
                0.8,
                '2026-03-28T00:00:00Z',
                1,
                'district_match',
                1,
                'event_specific',
                0.9,
                1,
                'consistent',
                'cluster-1',
                'evt-1',
                'https://example.com/article-1',
                1,
                '{"route_lang":"en","representative_url":"https://example.com/article-1"}',
            ),
        )
        connection.execute(
            """
            INSERT INTO cluster_summary (cluster_id, district, date_min, date_max, size, sources, urls, inserted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                'cluster-1',
                'Dhading',
                '2024-07-16',
                '2024-07-16',
                1,
                '["myrepublica"]',
                '["https://example.com/article-1"]',
                '2026-03-28T00:00:00Z',
            ),
        )
        connection.execute(
            """
            INSERT INTO canonical_events (
                event_id, dedup_cluster_id, event_date_ad, district, province, municipality,
                municipality_candidates_json, ward_candidates_json, place_name_candidates_json,
                event_payload, inserted_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                'event-1',
                'cluster-1',
                '2024-07-16',
                'Dhading',
                'Bagmati',
                'Nilkantha Municipality',
                '["Nilkantha Municipality"]',
                '[]',
                '["Nilkantha Municipality"]',
                '{"route_lang":"en","representative_url":"https://example.com/article-1"}',
                '2026-03-28T00:00:00Z',
            ),
        )
        connection.commit()

    canonical_count = run_inventory_audit_stage(config)
    assert canonical_count == 1

    output_dir = config.resolve_path('outputs_dir')
    summary = json.loads((output_dir / 'inventory_audit_summary.json').read_text(encoding='utf-8'))
    report = (output_dir / 'inventory_audit_report.md').read_text(encoding='utf-8')
    assert summary['core_counts']['canonical_events'] == 1
    assert summary['core_counts']['class1_low_confidence'] == 0
    assert summary['core_counts']['class1_fallback_dates'] == 0
    assert summary['route_counts']['en'] == 1
    assert 'Canonical events: 1' in report
    assert 'Low-confidence Class 1 rows: 0' in report
    assert (output_dir / 'source_year_summary.csv').exists()
    assert (output_dir / 'source_language_summary.csv').exists()
    assert (output_dir / 'district_coverage_summary.csv').exists()
    assert (output_dir / 'district_year_counts.csv').exists()
    assert (output_dir / 'district_month_counts.csv').exists()
    assert (output_dir / 'canonical_review_full.csv').exists()
    assert (output_dir / 'class1_low_confidence.csv').exists()
    assert (output_dir / 'class1_fallback_dates.csv').exists()
    assert (output_dir / 'dedup_cluster_audit.csv').exists()
