"""Tests for BIPAD external validation."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from landslide_inventory.bipad.validation import load_bipad_events, match_events, run_bipad_validation_stage
from landslide_inventory.config import load_config
from landslide_inventory.db import initialize_sqlite
from landslide_inventory.run import resolve_stage_name, STAGE_HANDLERS


def test_load_bipad_events_normalizes_districts_and_filters_landslides(tmp_path: Path) -> None:
    path = tmp_path / 'bipad.csv'
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=['id', 'Incident Date', 'District Name', 'Disaster', 'Deaths'])
        writer.writeheader()
        writer.writerow({'id': 'b1', 'Incident Date': '2024-07-16', 'District Name': 'Sindhupalchowk', 'Disaster': 'Landslide', 'Deaths': '2'})
        writer.writerow({'id': 'b2', 'Incident Date': '2024-07-17', 'District Name': 'Dhading', 'Disaster': 'Flood', 'Deaths': '1'})
    events = load_bipad_events(path)
    assert len(events) == 1
    assert events[0].district == 'Sindhupalchok'
    assert events[0].deaths == 2


def test_bipad_stage_writes_metrics_matches_and_district_coverage(config_file: Path) -> None:
    config = load_config(config_file)
    initialize_sqlite(config.sqlite_path)
    config.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    bipad_path = config_file.parent / 'bipad_landslides.csv'
    config.raw['bipad']['bipad_input_path'] = str(bipad_path)

    with config.sqlite_path.open('ab'):
        pass
    import sqlite3
    with sqlite3.connect(config.sqlite_path) as connection:
        connection.execute(
            """
            INSERT INTO canonical_events (
                event_id, dedup_cluster_id, event_date_ad, district, province, municipality,
                event_payload, inserted_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ('event_a', 'cluster_a', '2024-07-16', 'Dhading', 'Bagmati', None, json.dumps({'representative_url': 'https://example.com/a'}), 'now'),
        )
        connection.execute(
            """
            INSERT INTO canonical_events (
                event_id, dedup_cluster_id, event_date_ad, district, province, municipality,
                event_payload, inserted_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ('event_b', 'cluster_b', '2024-07-20', 'Sindhupalchok', 'Bagmati', None, json.dumps({'representative_url': 'https://example.com/b'}), 'now'),
        )
        connection.execute(
            """
            INSERT INTO article_events (
                extracted_event_id, article_url, event_class, event_payload, url, source, title,
                class, event_date_ad, district, deaths, missing, injured
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ('a', 'https://example.com/a', 1, '{}', 'https://example.com/a', 'test', 'Dhading landslide', 1, '2024-07-16', 'Dhading', 1, None, None),
        )
        connection.execute(
            """
            INSERT INTO article_events (
                extracted_event_id, article_url, event_class, event_payload, url, source, title,
                class, event_date_ad, district, deaths, missing, injured
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ('b', 'https://example.com/b', 1, '{}', 'https://example.com/b', 'test', 'Sindhupalchok landslide', 1, '2024-07-20', 'Sindhupalchok', 2, None, None),
        )
        connection.commit()

    with bipad_path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=['id', 'date', 'district', 'disaster', 'deaths', 'title'])
        writer.writeheader()
        writer.writerow({'id': 'bipad_1', 'date': '2024-07-17', 'district': 'Dhading', 'disaster': 'landslide', 'deaths': '1', 'title': 'BIPAD Dhading'})
        writer.writerow({'id': 'bipad_2', 'date': '2024-07-30', 'district': 'Sindhupalchowk', 'disaster': 'landslide', 'deaths': '2', 'title': 'Too far'})

    matches = run_bipad_validation_stage(config)
    assert matches == 1
    metrics = json.loads((config.resolve_path('outputs_dir') / 'bipad_metrics.json').read_text(encoding='utf-8'))
    assert metrics['windows']['1']['matches'] == 1
    assert metrics['windows']['1']['precision'] == 0.5
    assert metrics['windows']['1']['recall'] == 0.5
    assert (config.resolve_path('outputs_dir') / 'bipad_matches.csv').exists()
    coverage = (config.resolve_path('outputs_dir') / 'bipad_district_coverage.csv').read_text(encoding='utf-8')
    assert 'Dhading' in coverage


def test_bipad_stage_is_registered() -> None:
    assert resolve_stage_name('bipad') == 'bipad'
    assert resolve_stage_name('bipad_validate') == 'bipad'
    assert STAGE_HANDLERS['bipad'] is run_bipad_validation_stage
