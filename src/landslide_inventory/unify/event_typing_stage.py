"""Apply event typing to canonical events.

Writes ``event_type`` and ``extraction_basis`` onto ``canonical_events`` so the
paper can report headline counts and the road-obstruction subset separately,
per the decisions recorded in ``event_typing.py``.

Additive only: this stage adds columns and never removes or reclassifies a row
out of the inventory. Both labels are re-derivable, and the stage is idempotent.
"""

from __future__ import annotations

import logging
from typing import Any

from ..config import AppConfig
from ..db import connect_sqlite
from ..utils import ensure_directory, utc_now_iso
from ..validation.common import iso_now, write_csv
from .event_typing import classify_event_type, confidence_penalty, summarize_typing

LOGGER = logging.getLogger(__name__)

REPORT_COLUMNS = [
    'event_id', 'event_date_ad', 'district', 'event_type', 'hazard_type', 'extraction_basis',
    'reason', 'deaths', 'missing', 'injured', 'representative_source', 'representative_title',
]

MIGRATIONS = (
    'ALTER TABLE canonical_events ADD COLUMN event_type TEXT',
    'ALTER TABLE canonical_events ADD COLUMN hazard_type TEXT',
    'ALTER TABLE canonical_events ADD COLUMN extraction_basis TEXT',
    'ALTER TABLE canonical_events ADD COLUMN typing_reason TEXT',
    'ALTER TABLE canonical_events ADD COLUMN typed_at TEXT',
)


def ensure_typing_columns(connection) -> None:
    """Add the typing columns if absent. Safe to call repeatedly."""

    for statement in MIGRATIONS:
        try:
            connection.execute(statement)
        except Exception:  # noqa: BLE001 - column already exists
            pass


def run_event_typing_stage(config: AppConfig) -> dict[str, Any]:
    """Type every canonical event and report the split."""

    outputs_dir = config.resolve_path('outputs_dir')
    ensure_directory(outputs_dir)
    report_path = outputs_dir / 'event_typing.csv'
    typed_at = utc_now_iso()

    with connect_sqlite(config.sqlite_path) as connection:
        ensure_typing_columns(connection)
        rows = connection.execute(
            """
            SELECT ce.event_id      AS event_id,
                   ce.event_date_ad AS event_date_ad,
                   ce.district      AS district,
                   ae.title         AS title,
                   ae.source        AS representative_source,
                   COALESCE(r.text, '') AS text,
                   ae.deaths        AS deaths,
                   ae.missing       AS missing,
                   ae.injured       AS injured
            FROM canonical_events AS ce
            LEFT JOIN article_events AS ae
                   ON ae.url = json_extract(ce.event_payload, '$.representative_url')
            LEFT JOIN raw_articles AS r ON r.url = ae.url
            ORDER BY ce.event_id
            """
        ).fetchall()

        records: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            typing = classify_event_type(
                title=item.get('title'),
                text=item.get('text'),
                deaths=item.get('deaths'),
                missing=item.get('missing'),
                injured=item.get('injured'),
            )
            connection.execute(
                """
                UPDATE canonical_events
                SET event_type = ?, hazard_type = ?, extraction_basis = ?,
                    typing_reason = ?, typed_at = ?
                WHERE event_id = ?
                """,
                (typing.event_type, typing.hazard_type, typing.extraction_basis,
                 typing.reason, typed_at, item['event_id']),
            )
            records.append({
                'event_id': item['event_id'],
                'event_date_ad': item['event_date_ad'],
                'district': item['district'],
                'event_type': typing.event_type,
                'hazard_type': typing.hazard_type,
                'extraction_basis': typing.extraction_basis,
                'reason': typing.reason,
                'deaths': item.get('deaths'),
                'missing': item.get('missing'),
                'injured': item.get('injured'),
                'representative_source': item.get('representative_source'),
                'representative_title': ' '.join((item.get('title') or '').split())[:160],
            })
        connection.commit()

    write_csv(report_path, REPORT_COLUMNS, records)
    summary = summarize_typing(records)
    summary['generated_at'] = iso_now()
    summary['report'] = str(report_path)
    summary['title_only_confidence_multiplier'] = confidence_penalty('title_only')

    LOGGER.info(
        'Event typing: %d canonical events -> %d headline landslide events; '
        '%d road_obstruction, %d non-landslide hazard (both excluded from '
        'headline counts and BIPAD)',
        summary['total'], summary['headline_events'],
        summary['road_obstruction'], summary['non_landslide_hazard'],
    )
    for hazard, count in summary['by_hazard_type'].items():
        LOGGER.info('  hazard_type=%-14s %d', hazard, count)
    for basis, count in summary['by_extraction_basis'].items():
        LOGGER.info('  extraction_basis=%-12s %d', basis, count)
    return summary
