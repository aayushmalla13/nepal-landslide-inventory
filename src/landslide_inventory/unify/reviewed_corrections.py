"""Apply transparent, reviewed article corrections before canonical deduplication.

The source CSV is a small, versionable errata layer. It never rewrites article
text or human evaluation labels. Date corrections update the extracted record;
``exclude_from_canonical`` is consumed only by dedup, keeping the original
article and its automated classification available for audit.
"""

from __future__ import annotations

import csv
import hashlib
import json
import logging
from datetime import date
from pathlib import Path
from typing import Any

from ..config import AppConfig
from ..db import connect_sqlite, initialize_sqlite
from ..utils import ensure_directory, utc_now_iso
from ..validation.common import write_csv

LOGGER = logging.getLogger(__name__)

OUTPUT_COLUMNS = [
    'url', 'reviewed_at', 'reviewed_by', 'evidence_url', 'correction_action',
    'reason', 'published_date_ad', 'event_date_ad', 'district', 'province',
    'municipality', 'in_nepal',
    'exclude_from_canonical', 'scope_reason', 'before_json', 'after_json',
    'corrections_sha256', 'applied_at',
]


def corrections_path(config: AppConfig) -> Path | None:
    """Return the configured corrections CSV, or ``None`` when disabled."""

    value = config.raw.get('validation', {}).get('article_corrections_path')
    if not value:
        return None
    path = Path(str(value))
    return path if path.is_absolute() else config.config_path.parent / path


def _optional_iso(value: str, field: str, row_number: int) -> str | None:
    cleaned = value.strip()
    if not cleaned:
        return None
    try:
        return date.fromisoformat(cleaned).isoformat()
    except ValueError as exc:
        raise ValueError(
            f'Correction row {row_number}: {field} must be YYYY-MM-DD, got {cleaned!r}'
        ) from exc


def _optional_bool(value: str, field: str, row_number: int) -> int | None:
    cleaned = value.strip().casefold()
    if not cleaned:
        return None
    if cleaned in {'1', 'true', 'yes'}:
        return 1
    if cleaned in {'0', 'false', 'no'}:
        return 0
    raise ValueError(
        f'Correction row {row_number}: {field} must be 0/1, got {value!r}'
    )


def load_reviewed_corrections(path: Path) -> list[dict[str, Any]]:
    """Load and validate the versioned correction layer."""

    with path.open(encoding='utf-8-sig', newline='') as handle:
        rows = list(csv.DictReader(handle))
    seen: set[str] = set()
    parsed: list[dict[str, Any]] = []
    for row_number, row in enumerate(rows, start=2):
        if row.get(None):
            raise ValueError(
                f'Correction row {row_number}: unexpected extra CSV fields {row[None]!r}'
            )
        url = (row.get('url') or '').strip()
        if not url:
            raise ValueError(f'Correction row {row_number}: url is required')
        if url in seen:
            raise ValueError(f'Correction row {row_number}: duplicate URL {url}')
        seen.add(url)
        reason = (row.get('reason') or '').strip()
        evidence_url = (row.get('evidence_url') or '').strip()
        reviewed_by = (row.get('reviewed_by') or '').strip()
        reviewed_at = (row.get('reviewed_at') or '').strip()
        if not all((reason, evidence_url, reviewed_by, reviewed_at)):
            raise ValueError(
                f'Correction row {row_number}: provenance fields may not be blank'
            )
        _optional_iso(reviewed_at, 'reviewed_at', row_number)
        parsed.append(
            {
                'url': url,
                'reviewed_at': reviewed_at,
                'reviewed_by': reviewed_by,
                'evidence_url': evidence_url,
                'correction_action': (row.get('correction_action') or '').strip(),
                'reason': reason,
                'published_date_ad': _optional_iso(
                    row.get('published_date_ad') or '', 'published_date_ad', row_number
                ),
                'event_date_ad': _optional_iso(
                    row.get('event_date_ad') or '', 'event_date_ad', row_number
                ),
                'district': (row.get('district') or '').strip() or None,
                'province': (row.get('province') or '').strip() or None,
                'municipality': (row.get('municipality') or '').strip() or None,
                'in_nepal': _optional_bool(
                    row.get('in_nepal') or '', 'in_nepal', row_number
                ),
                'exclude_from_canonical': _optional_bool(
                    row.get('exclude_from_canonical') or '',
                    'exclude_from_canonical',
                    row_number,
                ) or 0,
                'scope_reason': (row.get('scope_reason') or '').strip() or None,
            }
        )
    return parsed


def _snapshot(connection, url: str) -> dict[str, Any] | None:
    row = connection.execute(
        """
        SELECT r.published_date_ad AS raw_published_date_ad,
               e.published_date_ad AS event_published_date_ad,
               e.event_date_ad, e.district, e.province, e.municipality,
               e.in_nepal, e.scope_reason
        FROM raw_articles AS r
        LEFT JOIN article_events AS e ON e.url = r.url
        WHERE r.url = ?
        """,
        (url,),
    ).fetchone()
    return dict(row) if row is not None else None


def apply_reviewed_corrections(config: AppConfig) -> dict[str, Any]:
    """Apply configured corrections idempotently and write an audit export."""

    path = corrections_path(config)
    if path is None:
        return {'configured': False, 'rows': 0}
    if not path.exists():
        raise FileNotFoundError(f'Reviewed corrections file not found: {path}')

    initialize_sqlite(config.sqlite_path)
    corrections = load_reviewed_corrections(path)
    source_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    applied_at = utc_now_iso()
    audit_rows: list[dict[str, Any]] = []
    with connect_sqlite(config.sqlite_path) as connection:
        for item in corrections:
            before = _snapshot(connection, item['url'])
            if before is None:
                raise ValueError(
                    f"Correction URL is missing from raw_articles: {item['url']}"
                )
            existing = connection.execute(
                'SELECT before_json FROM reviewed_article_corrections WHERE url = ?',
                (item['url'],),
            ).fetchone()
            original_before = (
                json.loads(existing['before_json']) if existing is not None else before
            )
            if item['published_date_ad'] is not None:
                connection.execute(
                    'UPDATE raw_articles SET published_date_ad = ? WHERE url = ?',
                    (item['published_date_ad'], item['url']),
                )
                connection.execute(
                    'UPDATE article_events SET published_date_ad = ? WHERE url = ?',
                    (item['published_date_ad'], item['url']),
                )
            updates: dict[str, Any] = {}
            for field in (
                'event_date_ad', 'district', 'province', 'municipality',
                'in_nepal', 'scope_reason',
            ):
                if item[field] is not None:
                    updates[field] = item[field]
            if updates:
                assignments = ', '.join(f'{field} = ?' for field in updates)
                connection.execute(
                    f'UPDATE article_events SET {assignments} WHERE url = ?',
                    (*updates.values(), item['url']),
                )
            after = _snapshot(connection, item['url'])
            connection.execute(
                """
                INSERT INTO reviewed_article_corrections (
                    url, reviewed_at, reviewed_by, evidence_url,
                    correction_action, reason, published_date_ad, event_date_ad,
                    district, province, municipality, in_nepal,
                    exclude_from_canonical, scope_reason, before_json,
                    after_json, corrections_sha256, applied_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(url) DO UPDATE SET
                    reviewed_at=excluded.reviewed_at,
                    reviewed_by=excluded.reviewed_by,
                    evidence_url=excluded.evidence_url,
                    correction_action=excluded.correction_action,
                    reason=excluded.reason,
                    published_date_ad=excluded.published_date_ad,
                    event_date_ad=excluded.event_date_ad,
                    district=excluded.district,
                    province=excluded.province,
                    municipality=excluded.municipality,
                    in_nepal=excluded.in_nepal,
                    exclude_from_canonical=excluded.exclude_from_canonical,
                    scope_reason=excluded.scope_reason,
                    after_json=excluded.after_json,
                    corrections_sha256=excluded.corrections_sha256,
                    applied_at=excluded.applied_at
                """,
                (
                    item['url'], item['reviewed_at'], item['reviewed_by'],
                    item['evidence_url'], item['correction_action'], item['reason'],
                    item['published_date_ad'], item['event_date_ad'],
                    item['district'], item['province'], item['municipality'], item['in_nepal'],
                    item['exclude_from_canonical'], item['scope_reason'],
                    json.dumps(original_before, ensure_ascii=False, sort_keys=True),
                    json.dumps(after, ensure_ascii=False, sort_keys=True),
                    source_hash, applied_at,
                ),
            )
            audit_rows.append(
                item
                | {
                    'before_json': json.dumps(
                        original_before, ensure_ascii=False, sort_keys=True
                    ),
                    'after_json': json.dumps(after, ensure_ascii=False, sort_keys=True),
                    'corrections_sha256': source_hash,
                    'applied_at': applied_at,
                }
            )
        connection.commit()

    outputs_dir = config.resolve_path('outputs_dir')
    ensure_directory(outputs_dir)
    report_path = outputs_dir / 'reviewed_corrections_applied.csv'
    write_csv(report_path, OUTPUT_COLUMNS, audit_rows)
    LOGGER.info(
        'Applied %d reviewed corrections from %s (sha256 %s)',
        len(audit_rows), path, source_hash[:12],
    )
    return {
        'configured': True,
        'rows': len(audit_rows),
        'source': str(path),
        'sha256': source_hash,
        'report': str(report_path),
    }


def run_reviewed_corrections_stage(config: AppConfig) -> dict[str, Any]:
    """CLI wrapper for the reviewed correction layer."""

    return apply_reviewed_corrections(config)
