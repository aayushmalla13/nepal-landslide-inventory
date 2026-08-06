"""Refresh manual verification predictions from the current article-event inventory."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from ..config import AppConfig
from ..db import connect_sqlite
from ..utils import ensure_directory
from .common import normalize_whitespace
from ..gazetteer import normalize_district
from ..gazetteer_municipality import normalize_municipality
from .manual_pack import OUTPUT_COLUMNS
from .manual_score import build_manual_report, compute_manual_metrics


PREDICTION_FIELDS = {
    'class_pred': 'class',
    'district_pred': 'district',
    'municipality_pred': 'municipality',
    'ward_pred': 'ward',
    'event_date_pred': 'event_date_ad',
    'deaths_pred': 'deaths',
    'missing_pred': 'missing',
    'injured_pred': 'injured',
    'trigger_pred': 'trigger',
    'specificity_reason': 'specificity_reason',
    'specificity_score': 'specificity_score',
}


def run_manual_refresh_stage(config: AppConfig) -> int:
    """Write a refreshed copy of the manual verification CSV using current predictions."""

    output_dir = config.resolve_path('outputs_dir')
    ensure_directory(output_dir)
    source_path = output_dir / 'manual_verification_sample.csv'
    refreshed_path = output_dir / 'manual_verification_sample_refreshed.csv'
    metrics_path = output_dir / 'manual_metrics_refreshed.json'
    report_path = output_dir / 'manual_report_refreshed.md'

    rows = load_manual_sample_rows(source_path)
    refreshed_rows = refresh_manual_rows(config.sqlite_path, rows)
    write_manual_rows(refreshed_path, refreshed_rows)

    metrics = compute_manual_metrics(refreshed_rows)
    metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2, sort_keys=True), encoding='utf-8')
    report_path.write_text(build_manual_report(metrics), encoding='utf-8')
    return len(refreshed_rows)


def load_manual_sample_rows(path: Path) -> list[dict[str, str]]:
    with path.open('r', encoding='utf-8', newline='') as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def refresh_manual_rows(database_path: Path, rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Return a copy of manual rows with prediction columns refreshed from article_events."""

    refreshed: list[dict[str, str]] = []
    with connect_sqlite(database_path) as connection:
        for row in rows:
            updated = dict(row)
            live = _lookup_live_row(connection, row)
            if live is not None:
                for csv_field, db_field in PREDICTION_FIELDS.items():
                    updated[csv_field] = _csv_value(live[db_field])
                updated['source'] = _coalesce_text(live['source'], row.get('source', ''))
                updated['title'] = normalize_whitespace(_coalesce_text(live['title'], row.get('title', '')))
                updated['route_lang'] = _coalesce_text(live['route_lang'], row.get('route_lang', ''))
                updated['year'] = _derive_year(updated)
            refreshed.append(_normalize_row(updated))
    return refreshed


def _lookup_live_row(connection, row: dict[str, str]):
    live = connection.execute(
        """
        SELECT url, source, title, route_lang, class, district, municipality, ward,
               event_date_ad, deaths, missing, injured, trigger,
               specificity_reason, specificity_score
        FROM article_events
        WHERE url = ?
        ORDER BY rowid DESC
        LIMIT 1
        """,
        (row.get('url', ''),),
    ).fetchone()
    if live is not None:
        return live

    source = normalize_whitespace(row.get('source', ''))
    title = normalize_whitespace(row.get('title', ''))
    if not source or not title:
        return None
    return connection.execute(
        """
        SELECT url, source, title, route_lang, class, district, municipality, ward,
               event_date_ad, deaths, missing, injured, trigger,
               specificity_reason, specificity_score
        FROM article_events
        WHERE source = ? AND title = ?
        ORDER BY rowid DESC
        LIMIT 1
        """,
        (source, title),
    ).fetchone()


def write_manual_rows(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, '') for column in OUTPUT_COLUMNS})


def _csv_value(value: Any) -> str:
    if value is None:
        return ''
    return str(value)


def _coalesce_text(value: Any, fallback: str) -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text or fallback


def _derive_year(row: dict[str, str]) -> str:
    for field in ('event_date_pred', 'date_true'):
        value = (row.get(field) or '').strip()
        if len(value) >= 4 and value[:4].isdigit():
            return value[:4]
    return (row.get('year') or '').strip()


def _normalize_row(row: dict[str, str]) -> dict[str, str]:
    normalized = dict(row)
    normalized['title'] = normalize_whitespace(normalized.get('title', ''))
    normalized['snippet'] = normalize_whitespace(normalized.get('snippet', ''))[:280]
    for key in OUTPUT_COLUMNS:
        normalized[key] = '' if normalized.get(key) is None else str(normalized.get(key))
    for key in ('district_pred', 'district_true'):
        normalized[key] = _normalize_district_display(normalized.get(key, ''))
    for key in ('municipality_pred', 'municipality_true'):
        normalized[key] = _normalize_municipality_display(normalized.get(key, ''))
    return normalized


def _normalize_district_display(value: str) -> str:
    cleaned = normalize_whitespace(value)
    if not cleaned:
        return ''
    normalized = normalize_district(cleaned, 'en')
    return normalized or cleaned


def _normalize_municipality_display(value: str) -> str:
    cleaned = normalize_whitespace(value)
    if not cleaned:
        return ''
    normalized = normalize_municipality(cleaned, 'en')
    return normalized or cleaned
