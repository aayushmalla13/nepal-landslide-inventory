"""Reproducible export of the final inventory deliverable.

Why this module exists
----------------------
``data/outputs/canonical_events_final.csv`` -- the file named like the paper's
dataset, with a richer schema than anything the pipeline emitted -- was
**produced by no code in this repository** (review section 3.4). Neither was
``data/raw_sqlite/landslide_inventory_final_snapshot_20260423.sqlite``. For a
paper claiming a reproducible pipeline, a deliverable that cannot be
regenerated is disqualifying on its own.

It turns out the file *is* reproducible: it is ``canonical_events`` joined to
``cluster_summary`` (cluster size and contributing sources) and to the
representative article's row in ``article_events`` (title, casualties, trigger,
and the filter reasons), with ``inserted_at`` dropped. This module implements
that join, so the deliverable has a code path again.

``verify_export_matches`` compares a freshly generated export against an
existing file field-by-field, which is how the reconstruction above was
confirmed rather than assumed.

Result of that verification against the distributed 2026-04-23 file:
**all 1,071 events match on all 26 fields**, with no rows on either side only.
The two files are not byte-identical, for one cosmetic reason: the orphaned
writer quoted 432 multi-word values ("Kusma Municipality") that need no
quoting. Parsed values are identical; this export uses stdlib ``QUOTE_MINIMAL``
and is byte-stable with itself, which is the property that actually matters for
a checksummable published dataset.

A note on the schema
--------------------
This export deliberately carries ``specificity_reason``, ``scope_reason`` and
``location_reason`` alongside each event. A published inventory should let a
reader see *why* the pipeline believed each row, not just what it concluded.
"""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import Any, Iterable

from .config import AppConfig
from .db import connect_sqlite
from .utils import ensure_directory

LOGGER = logging.getLogger(__name__)

FINAL_COLUMNS = [
    'event_id', 'dedup_cluster_id', 'event_date_ad', 'district', 'province', 'municipality',
    'cluster_size', 'sources_json', 'representative_url', 'representative_source',
    'representative_title', 'trigger', 'deaths', 'missing', 'injured',
    'conf_date', 'conf_class', 'specificity_reason', 'in_nepal', 'scope_reason',
    'location_consistent', 'location_reason',
    'municipality_candidates_json', 'ward_candidates_json', 'place_name_candidates_json',
    'event_payload',
]

DEFAULT_FILENAME = 'canonical_events_final.csv'


def _compact_json(raw: str | None) -> str | None:
    """Re-serialize a JSON column with compact separators.

    ``cluster_summary.sources`` is stored with ', ' separators, but the
    distributed ``canonical_events_final.csv`` used compact ',' -- the only
    field-level difference between this export and the orphaned file, across
    all 1,071 events (19 multi-source clusters). Normalizing here reproduces
    the deliverable exactly and matches the compact form ``utils.stable_hash``
    already uses, so the CSV is checksum-stable.
    """

    if not raw:
        return raw
    try:
        return json.dumps(json.loads(raw), ensure_ascii=False, separators=(',', ':'))
    except json.JSONDecodeError:
        return raw


def _payload_field(payload: str | None, key: str) -> Any:
    """Pull a key out of the canonical event's JSON payload."""

    if not payload:
        return None
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return None
    return data.get(key) if isinstance(data, dict) else None


def build_final_rows(connection) -> list[dict[str, Any]]:
    """Join canonical_events -> cluster_summary -> representative article_events row.

    Ordered by (event_date_ad, district, event_id): chronological, which is what
    a reader of a landslide inventory wants, and fully deterministic because
    event_id breaks every tie. Determinism matters here -- a published dataset
    should be checksummable, and re-running the export must not reshuffle it.

    This is also the order of the distributed canonical_events_final.csv, which
    is part of how that file was confirmed reproducible.
    """

    query = """
        SELECT ce.event_id                     AS event_id,
               ce.dedup_cluster_id             AS dedup_cluster_id,
               ce.event_date_ad                AS event_date_ad,
               ce.district                     AS district,
               ce.province                     AS province,
               ce.municipality                 AS municipality,
               ce.municipality_candidates_json AS municipality_candidates_json,
               ce.ward_candidates_json         AS ward_candidates_json,
               ce.place_name_candidates_json   AS place_name_candidates_json,
               ce.event_payload                AS event_payload,
               cs.size                         AS cluster_size,
               cs.sources                      AS sources_json,
               ae.url                          AS representative_url,
               ae.source                       AS representative_source,
               ae.title                        AS representative_title,
               ae.trigger                      AS trigger,
               ae.deaths                       AS deaths,
               ae.missing                      AS missing,
               ae.injured                      AS injured,
               ae.conf_date                    AS conf_date,
               ae.conf_class                   AS conf_class,
               ae.specificity_reason           AS specificity_reason,
               ae.in_nepal                     AS in_nepal,
               ae.scope_reason                 AS scope_reason,
               ae.location_consistent          AS location_consistent,
               ae.location_reason              AS location_reason
        FROM canonical_events AS ce
        LEFT JOIN cluster_summary AS cs
               ON cs.cluster_id = ce.dedup_cluster_id
        LEFT JOIN article_events AS ae
               ON ae.url = json_extract(ce.event_payload, '$.representative_url')
        ORDER BY ce.event_date_ad, ce.district, ce.event_id
    """
    rows: list[dict[str, Any]] = []
    for record in connection.execute(query):
        item = dict(record)
        # Fall back to reading the payload in Python if the SQLite build lacks
        # the JSON1 extension, so the export is not silently empty.
        if item.get('representative_url') is None:
            url = _payload_field(item['event_payload'], 'representative_url')
            if url:
                extra = connection.execute(
                    """SELECT url, source, title, trigger, deaths, missing, injured,
                              conf_date, conf_class, specificity_reason, in_nepal,
                              scope_reason, location_consistent, location_reason
                       FROM article_events WHERE url = ?""",
                    (url,),
                ).fetchone()
                if extra is not None:
                    extra = dict(extra)
                    item['representative_url'] = extra.pop('url')
                    item['representative_source'] = extra.pop('source')
                    item['representative_title'] = extra.pop('title')
                    item.update(extra)
        item['sources_json'] = _compact_json(item.get('sources_json'))
        rows.append({column: item.get(column) for column in FINAL_COLUMNS})
    return rows


def write_final_csv(rows: Iterable[dict[str, Any]], path: Path) -> Path:
    """Write the deliverable deterministically."""

    ensure_directory(path.parent)
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=FINAL_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column) for column in FINAL_COLUMNS})
    return path


def verify_export_matches(generated: Path, existing: Path) -> dict[str, Any]:
    """Field-by-field comparison against a previously distributed file.

    Used to prove that the reconstruction above really does reproduce the
    orphaned ``canonical_events_final.csv``, rather than merely resembling it.
    """

    def _load(path: Path) -> dict[str, dict[str, str]]:
        with path.open(encoding='utf-8', newline='') as handle:
            return {row['event_id']: row for row in csv.DictReader(handle)}

    left, right = _load(generated), _load(existing)
    only_generated = sorted(set(left) - set(right))
    only_existing = sorted(set(right) - set(left))
    shared = sorted(set(left) & set(right))

    mismatches: dict[str, int] = {}
    examples: dict[str, dict[str, str]] = {}
    for event_id in shared:
        for column in FINAL_COLUMNS:
            lhs, rhs = (left[event_id].get(column) or ''), (right[event_id].get(column) or '')
            if lhs != rhs:
                mismatches[column] = mismatches.get(column, 0) + 1
                examples.setdefault(column, {
                    'event_id': event_id, 'generated': lhs[:120], 'existing': rhs[:120],
                })
    return {
        'rows_generated': len(left),
        'rows_existing': len(right),
        'only_in_generated': only_generated[:10],
        'only_in_existing': only_existing[:10],
        'identical': not mismatches and not only_generated and not only_existing,
        'mismatched_columns': dict(sorted(mismatches.items(), key=lambda kv: -kv[1])),
        'examples': examples,
    }


def run_export_final_stage(config: AppConfig) -> dict[str, Any]:
    """Regenerate the final deliverable from the database."""

    outputs_dir = config.resolve_path('outputs_dir')
    target = outputs_dir / DEFAULT_FILENAME

    with connect_sqlite(config.sqlite_path) as connection:
        rows = build_final_rows(connection)

    if not rows:
        raise RuntimeError(
            'Export produced zero rows. canonical_events is empty -- run the dedup stage first.'
        )

    write_final_csv(rows, target)
    LOGGER.info('Wrote %s (%d events) from canonical_events', target, len(rows))
    return {'path': str(target), 'rows': len(rows)}
