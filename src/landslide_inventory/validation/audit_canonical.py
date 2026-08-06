"""Canonical-event audit sample generation."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from ..config import AppConfig
from ..db import connect_sqlite, initialize_sqlite
from .common import parse_json_list, stable_sample, write_csv

OUTPUT_COLUMNS = [
    'event_id', 'cluster_id', 'event_date_ad', 'district', 'municipality', 'ward',
    'deaths', 'missing', 'injured', 'trigger', 'sources_count', 'urls_count',
    'representative_title', 'representative_url', 'specificity_reason', 'specificity_score',
    'location_consistency_status', 'in_nepal', 'scope_reason',
    'is_real_event', 'issue_type', 'reviewer_notes',
]


@dataclass(frozen=True)
class CanonicalAuditRow:
    event_id: str
    cluster_id: str
    event_date_ad: str | None
    district: str | None
    municipality: str | None
    ward: str | None
    deaths: int | None
    missing: int | None
    injured: int | None
    trigger: str | None
    sources_count: int
    urls_count: int
    representative_title: str
    representative_url: str
    specificity_reason: str | None
    specificity_score: float | None
    location_consistency_status: str | None
    in_nepal: int | None
    scope_reason: str | None


def run_audit_canonical_stage(config: AppConfig) -> int:
    """Generate a deterministic canonical-event audit sample CSV."""

    initialize_sqlite(config.sqlite_path)
    seed = int(config.raw['validation']['random_seed'])
    rows = load_canonical_audit_rows(config.sqlite_path)
    sample = sample_canonical_rows(rows, 30, seed)
    output_path = config.resolve_path('outputs_dir') / 'canonical_audit_sample.csv'
    write_csv(output_path, OUTPUT_COLUMNS, [row_to_dict(row) for row in sample])
    return len(sample)


def sample_canonical_rows(rows: list[CanonicalAuditRow], sample_size: int, seed: int) -> list[CanonicalAuditRow]:
    """Return a deterministic canonical audit sample."""

    if len(rows) <= sample_size:
        return sorted(rows, key=lambda row: (row.event_date_ad or '', row.district or '', row.event_id))
    return stable_sample(rows, sample_size, seed, key=lambda row: row.event_id)


def load_canonical_audit_rows(database_path: Path) -> list[CanonicalAuditRow]:
    """Load canonical rows joined to representative article evidence."""

    with connect_sqlite(database_path) as connection:
        canonical_rows = connection.execute(
            """
            SELECT c.event_id,
                   c.dedup_cluster_id,
                   c.event_date_ad,
                   c.district,
                   c.municipality,
                   json_extract(c.event_payload, '$.representative_url') AS representative_url,
                   c.event_payload,
                   s.sources,
                   s.urls
            FROM canonical_events c
            JOIN cluster_summary s ON s.cluster_id = c.dedup_cluster_id
            ORDER BY c.event_date_ad, c.district, c.event_id
            """
        ).fetchall()

        rows: list[CanonicalAuditRow] = []
        for row in canonical_rows:
            cluster_id = str(row['dedup_cluster_id'])
            representative_url = str(row['representative_url'])
            evidence_rows = connection.execute(
                """
                SELECT url, title, ward, deaths, missing, injured, trigger,
                       specificity_reason, specificity_score, location_reason, location_consistent,
                       in_nepal, scope_reason
                FROM article_events
                WHERE dedup_cluster_id = ?
                ORDER BY url ASC
                """,
                (cluster_id,),
            ).fetchall()
            representative_title = choose_representative_title(evidence_rows, representative_url)
            representative_row = next((item for item in evidence_rows if str(item['url']) == representative_url), evidence_rows[0])
            payload = json.loads(str(row['event_payload']))
            source_list = parse_json_list(str(row['sources']))
            url_list = parse_json_list(str(row['urls']))
            rows.append(
                CanonicalAuditRow(
                    event_id=str(row['event_id']),
                    cluster_id=cluster_id,
                    event_date_ad=row['event_date_ad'],
                    district=row['district'],
                    municipality=row['municipality'],
                    ward=representative_row['ward'],
                    deaths=representative_row['deaths'],
                    missing=representative_row['missing'],
                    injured=representative_row['injured'],
                    trigger=representative_row['trigger'],
                    sources_count=len(source_list),
                    urls_count=len(url_list),
                    representative_title=representative_title,
                    representative_url=representative_url,
                    specificity_reason=representative_row['specificity_reason'],
                    specificity_score=float(representative_row['specificity_score']) if representative_row['specificity_score'] is not None else None,
                    location_consistency_status='consistent' if representative_row['location_consistent'] in (None, 1) else str(representative_row['location_reason'] or 'conflict'),
                    in_nepal=representative_row['in_nepal'],
                    scope_reason=representative_row['scope_reason'],
                )
            )
        return rows


def choose_representative_title(evidence_rows: list[Any], representative_url: str) -> str:
    """Choose the most informative title deterministically from cluster evidence."""

    scored = []
    for row in evidence_rows:
        title = str(row['title'] or '').strip()
        if not title:
            continue
        score = (
            int(bool(row['deaths'] or row['missing'] or row['injured'])),
            len(title),
            int(str(row['url']) == representative_url),
            title,
        )
        scored.append((score, title))
    if not scored:
        return ''
    return sorted(scored, key=lambda item: item[0], reverse=True)[0][1]


def row_to_dict(row: CanonicalAuditRow) -> dict[str, Any]:
    """Convert a canonical audit row to CSV-friendly dict output."""

    return {
        'event_id': row.event_id,
        'cluster_id': row.cluster_id,
        'event_date_ad': row.event_date_ad,
        'district': row.district,
        'municipality': row.municipality,
        'ward': row.ward,
        'deaths': row.deaths,
        'missing': row.missing,
        'injured': row.injured,
        'trigger': row.trigger,
        'sources_count': row.sources_count,
        'urls_count': row.urls_count,
        'representative_title': row.representative_title,
        'representative_url': row.representative_url,
        'specificity_reason': row.specificity_reason,
        'specificity_score': row.specificity_score,
        'location_consistency_status': row.location_consistency_status,
        'in_nepal': row.in_nepal,
        'scope_reason': row.scope_reason,
        'is_real_event': '',
        'issue_type': '',
        'reviewer_notes': '',
    }
