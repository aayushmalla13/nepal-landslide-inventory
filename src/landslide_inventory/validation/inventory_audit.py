"""Pre-BIPAD inventory QA summaries and audit exports."""

from __future__ import annotations

import json
from typing import Any

from ..config import AppConfig
from ..db import connect_sqlite, initialize_sqlite
from ..utils import ensure_directory
from .common import iso_now, parse_json_list, write_csv

LOW_CONFIDENCE_THRESHOLD = 0.75
FALLBACK_DATE_MAX_CONFIDENCE = 0.61


def run_inventory_audit_stage(config: AppConfig) -> int:
    """Generate pre-BIPAD QA summaries and analysis-ready audit exports."""

    initialize_sqlite(config.sqlite_path)
    output_dir = config.resolve_path('outputs_dir')
    ensure_directory(output_dir)
    with connect_sqlite(config.sqlite_path) as connection:
        summary = build_inventory_summary(connection)
        source_year_rows = load_source_year_rows(connection)
        source_language_rows = load_source_language_rows(connection)
        district_rows = load_district_rows(connection)
        district_year_rows = load_district_year_rows(connection)
        district_month_rows = load_district_month_rows(connection)
        cluster_rows = load_cluster_rows(connection)
        canonical_review_rows = load_canonical_review_rows(connection)
        low_confidence_rows = load_low_confidence_class1_rows(connection)
        fallback_date_rows = load_fallback_date_class1_rows(connection)

    (output_dir / 'inventory_audit_summary.json').write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True),
        encoding='utf-8',
    )
    (output_dir / 'inventory_audit_report.md').write_text(
        build_inventory_report(summary),
        encoding='utf-8',
    )
    write_csv(
        output_dir / 'source_year_summary.csv',
        [
            'source', 'route_lang', 'year', 'articles_total', 'class1_count', 'class2_count',
            'class3_count', 'canonical_cluster_hits', 'specificity_ok_count', 'in_nepal_count',
        ],
        source_year_rows,
    )
    write_csv(
        output_dir / 'source_language_summary.csv',
        [
            'source', 'route_lang', 'article_events_total', 'class1_count', 'class2_count',
            'class3_count', 'canonical_cluster_hits', 'specificity_ok_count', 'in_nepal_count',
        ],
        source_language_rows,
    )
    write_csv(
        output_dir / 'district_coverage_summary.csv',
        [
            'district', 'article_events_total', 'class1_count', 'canonical_events_count',
            'en_article_count', 'np_article_count', 'en_canonical_count', 'np_canonical_count',
        ],
        district_rows,
    )
    write_csv(
        output_dir / 'district_year_counts.csv',
        ['district', 'year', 'canonical_events_count'],
        district_year_rows,
    )
    write_csv(
        output_dir / 'district_month_counts.csv',
        ['district', 'year_month', 'canonical_events_count'],
        district_month_rows,
    )
    write_csv(
        output_dir / 'dedup_cluster_audit.csv',
        [
            'cluster_id', 'event_id', 'district', 'event_date_ad', 'size', 'source_count',
            'sources', 'municipality', 'municipality_candidates_json', 'ward_candidates_json',
            'place_name_candidates_json', 'representative_url',
        ],
        cluster_rows,
    )
    write_csv(
        output_dir / 'canonical_review_full.csv',
        [
            'event_id', 'cluster_id', 'event_date_ad', 'district', 'municipality', 'ward',
            'size', 'source_count', 'sources', 'representative_url', 'representative_title',
            'route_lang', 'deaths', 'missing', 'injured', 'trigger', 'conf_date',
            'conf_district', 'conf_place', 'specificity_reason', 'specificity_score',
            'scope_reason', 'location_reason',
        ],
        canonical_review_rows,
    )
    write_csv(
        output_dir / 'class1_low_confidence.csv',
        [
            'url', 'source', 'title', 'event_date_ad', 'published_date_ad', 'district',
            'municipality', 'conf_class', 'conf_date', 'conf_district', 'conf_place',
            'conf_fatalities', 'conf_trigger', 'specificity_reason', 'scope_reason',
            'location_reason',
        ],
        low_confidence_rows,
    )
    write_csv(
        output_dir / 'class1_fallback_dates.csv',
        [
            'url', 'source', 'title', 'published_date_ad', 'event_date_ad', 'district',
            'municipality', 'conf_date', 'specificity_reason', 'scope_reason',
        ],
        fallback_date_rows,
    )
    return int(summary['core_counts']['canonical_events'])


def build_inventory_summary(connection) -> dict[str, Any]:
    """Build the top-level pre-BIPAD QA summary."""

    core = {
        'raw_articles': scalar(connection, 'SELECT COUNT(*) FROM raw_articles'),
        'article_lang': scalar(connection, 'SELECT COUNT(*) FROM article_lang'),
        'article_events': scalar(connection, 'SELECT COUNT(*) FROM article_events'),
        'canonical_events': scalar(connection, 'SELECT COUNT(*) FROM canonical_events'),
        'class1': scalar(connection, 'SELECT COUNT(*) FROM article_events WHERE class = 1'),
        'class2': scalar(connection, 'SELECT COUNT(*) FROM article_events WHERE class = 2'),
        'class3': scalar(connection, 'SELECT COUNT(*) FROM article_events WHERE class = 3'),
        'class1_low_confidence': scalar(
            connection,
            f"""
            SELECT COUNT(*)
            FROM article_events
            WHERE class = 1
              AND (
                  COALESCE(conf_class, 0) < {LOW_CONFIDENCE_THRESHOLD}
                  OR COALESCE(conf_date, 0) < {LOW_CONFIDENCE_THRESHOLD}
                  OR COALESCE(conf_district, 0) < {LOW_CONFIDENCE_THRESHOLD}
                  OR COALESCE(conf_place, 0) < {LOW_CONFIDENCE_THRESHOLD}
              )
            """,
        ),
        'class1_fallback_dates': scalar(
            connection,
            f"""
            SELECT COUNT(*)
            FROM article_events
            WHERE class = 1
              AND published_date_ad IS NOT NULL
              AND event_date_ad = published_date_ad
              AND COALESCE(conf_date, 0) <= {FALLBACK_DATE_MAX_CONFIDENCE}
            """,
        ),
    }
    route_rows = connection.execute(
        """
        SELECT route_lang, COUNT(*) AS n
        FROM article_events
        GROUP BY route_lang
        ORDER BY route_lang
        """
    ).fetchall()
    route_counts = {str(row['route_lang'] or 'unknown'): int(row['n']) for row in route_rows}
    source_rows = connection.execute(
        """
        SELECT source,
               COUNT(*) AS article_events_count,
               SUM(CASE WHEN class = 1 THEN 1 ELSE 0 END) AS class1_count,
               SUM(CASE WHEN COALESCE(specificity_ok, 0) = 1 THEN 1 ELSE 0 END) AS specificity_ok_count,
               SUM(CASE WHEN COALESCE(in_nepal, 0) = 1 THEN 1 ELSE 0 END) AS in_nepal_count
        FROM article_events
        GROUP BY source
        ORDER BY source
        """
    ).fetchall()
    source_summary = [
        {
            'source': str(row['source']),
            'article_events_count': int(row['article_events_count']),
            'class1_count': int(row['class1_count'] or 0),
            'specificity_ok_count': int(row['specificity_ok_count'] or 0),
            'in_nepal_count': int(row['in_nepal_count'] or 0),
        }
        for row in source_rows
    ]
    district_rows = connection.execute(
        """
        SELECT district,
               SUM(CASE WHEN route_lang = 'en' THEN 1 ELSE 0 END) AS en_articles,
               SUM(CASE WHEN route_lang = 'np' THEN 1 ELSE 0 END) AS np_articles
        FROM article_events
        WHERE district IS NOT NULL
        GROUP BY district
        ORDER BY district
        """
    ).fetchall()
    only_en = sorted(
        str(row['district'])
        for row in district_rows
        if int(row['en_articles'] or 0) > 0 and int(row['np_articles'] or 0) == 0
    )
    only_np = sorted(
        str(row['district'])
        for row in district_rows
        if int(row['np_articles'] or 0) > 0 and int(row['en_articles'] or 0) == 0
    )
    overlap_row = connection.execute(
        """
        SELECT SUM(CASE WHEN source_count > 1 THEN 1 ELSE 0 END) AS multi_source_clusters,
               COUNT(*) AS total_clusters,
               MAX(size) AS max_cluster_size
        FROM (
            SELECT c.cluster_id,
                   c.size,
                   json_array_length(c.sources) AS source_count
            FROM cluster_summary c
        )
        """
    ).fetchone()
    return {
        'generated_at': iso_now(),
        'core_counts': core,
        'route_counts': route_counts,
        'source_summary': source_summary,
        'district_language_overlap': {
            'districts_only_en': only_en,
            'districts_only_np': only_np,
            'districts_both': len(district_rows) - len(only_en) - len(only_np),
        },
        'dedup_summary': {
            'total_clusters': int(overlap_row['total_clusters'] or 0),
            'multi_source_clusters': int(overlap_row['multi_source_clusters'] or 0),
            'max_cluster_size': int(overlap_row['max_cluster_size'] or 0),
        },
    }


def load_source_year_rows(connection) -> list[dict[str, Any]]:
    """Load per-source and per-year article summary rows."""

    rows = connection.execute(
        """
        SELECT source,
               route_lang,
               COALESCE(substr(COALESCE(published_date_ad, event_date_ad), 1, 4), 'unknown') AS year,
               COUNT(*) AS articles_total,
               SUM(CASE WHEN class = 1 THEN 1 ELSE 0 END) AS class1_count,
               SUM(CASE WHEN class = 2 THEN 1 ELSE 0 END) AS class2_count,
               SUM(CASE WHEN class = 3 THEN 1 ELSE 0 END) AS class3_count,
               SUM(CASE WHEN dedup_cluster_id IS NOT NULL THEN 1 ELSE 0 END) AS canonical_cluster_hits,
               SUM(CASE WHEN COALESCE(specificity_ok, 0) = 1 THEN 1 ELSE 0 END) AS specificity_ok_count,
               SUM(CASE WHEN COALESCE(in_nepal, 0) = 1 THEN 1 ELSE 0 END) AS in_nepal_count
        FROM article_events
        GROUP BY source, route_lang, year
        ORDER BY source, route_lang, year
        """
    ).fetchall()
    return [
        {
            'source': str(row['source']),
            'route_lang': str(row['route_lang'] or 'unknown'),
            'year': str(row['year']),
            'articles_total': int(row['articles_total']),
            'class1_count': int(row['class1_count'] or 0),
            'class2_count': int(row['class2_count'] or 0),
            'class3_count': int(row['class3_count'] or 0),
            'canonical_cluster_hits': int(row['canonical_cluster_hits'] or 0),
            'specificity_ok_count': int(row['specificity_ok_count'] or 0),
            'in_nepal_count': int(row['in_nepal_count'] or 0),
        }
        for row in rows
    ]


def load_source_language_rows(connection) -> list[dict[str, Any]]:
    """Load per-source and per-language summary rows."""

    rows = connection.execute(
        """
        SELECT source,
               route_lang,
               COUNT(*) AS article_events_total,
               SUM(CASE WHEN class = 1 THEN 1 ELSE 0 END) AS class1_count,
               SUM(CASE WHEN class = 2 THEN 1 ELSE 0 END) AS class2_count,
               SUM(CASE WHEN class = 3 THEN 1 ELSE 0 END) AS class3_count,
               SUM(CASE WHEN dedup_cluster_id IS NOT NULL THEN 1 ELSE 0 END) AS canonical_cluster_hits,
               SUM(CASE WHEN COALESCE(specificity_ok, 0) = 1 THEN 1 ELSE 0 END) AS specificity_ok_count,
               SUM(CASE WHEN COALESCE(in_nepal, 0) = 1 THEN 1 ELSE 0 END) AS in_nepal_count
        FROM article_events
        GROUP BY source, route_lang
        ORDER BY source, route_lang
        """
    ).fetchall()
    return [dict(row) for row in rows]


def load_district_rows(connection) -> list[dict[str, Any]]:
    """Load district-level coverage rows for bilingual comparison."""

    rows = connection.execute(
        """
        WITH district_events AS (
            SELECT district,
                   COUNT(*) AS article_events_total,
                   SUM(CASE WHEN class = 1 THEN 1 ELSE 0 END) AS class1_count,
                   SUM(CASE WHEN route_lang = 'en' THEN 1 ELSE 0 END) AS en_article_count,
                   SUM(CASE WHEN route_lang = 'np' THEN 1 ELSE 0 END) AS np_article_count
            FROM article_events
            WHERE district IS NOT NULL
            GROUP BY district
        ),
        canonical_by_district AS (
            SELECT c.district,
                   COUNT(*) AS canonical_events_count,
                   SUM(CASE WHEN json_extract(c.event_payload, '$.route_lang') = 'en' THEN 1 ELSE 0 END) AS en_canonical_count,
                   SUM(CASE WHEN json_extract(c.event_payload, '$.route_lang') = 'np' THEN 1 ELSE 0 END) AS np_canonical_count
            FROM canonical_events c
            GROUP BY c.district
        )
        SELECT d.district,
               d.article_events_total,
               d.class1_count,
               COALESCE(c.canonical_events_count, 0) AS canonical_events_count,
               d.en_article_count,
               d.np_article_count,
               COALESCE(c.en_canonical_count, 0) AS en_canonical_count,
               COALESCE(c.np_canonical_count, 0) AS np_canonical_count
        FROM district_events d
        LEFT JOIN canonical_by_district c ON c.district = d.district
        ORDER BY d.district
        """
    ).fetchall()
    return [dict(row) for row in rows]


def load_district_year_rows(connection) -> list[dict[str, Any]]:
    """Load canonical-event counts by district and year."""

    rows = connection.execute(
        """
        SELECT district,
               substr(event_date_ad, 1, 4) AS year,
               COUNT(*) AS canonical_events_count
        FROM canonical_events
        WHERE event_date_ad IS NOT NULL
        GROUP BY district, year
        ORDER BY district, year
        """
    ).fetchall()
    return [dict(row) for row in rows]


def load_district_month_rows(connection) -> list[dict[str, Any]]:
    """Load canonical-event counts by district and year-month."""

    rows = connection.execute(
        """
        SELECT district,
               substr(event_date_ad, 1, 7) AS year_month,
               COUNT(*) AS canonical_events_count
        FROM canonical_events
        WHERE event_date_ad IS NOT NULL
        GROUP BY district, year_month
        ORDER BY district, year_month
        """
    ).fetchall()
    return [dict(row) for row in rows]


def load_cluster_rows(connection) -> list[dict[str, Any]]:
    """Load cluster-level audit rows for dedup inspection."""

    rows = connection.execute(
        """
        SELECT c.cluster_id,
               k.event_id,
               k.district,
               k.event_date_ad,
               c.size,
               c.sources,
               k.municipality,
               k.municipality_candidates_json,
               k.ward_candidates_json,
               k.place_name_candidates_json,
               json_extract(k.event_payload, '$.representative_url') AS representative_url
        FROM cluster_summary c
        JOIN canonical_events k ON k.dedup_cluster_id = c.cluster_id
        ORDER BY k.event_date_ad, k.district, c.cluster_id
        """
    ).fetchall()
    cluster_rows: list[dict[str, Any]] = []
    for row in rows:
        sources = parse_json_list(str(row['sources']))
        cluster_rows.append(
            {
                'cluster_id': str(row['cluster_id']),
                'event_id': str(row['event_id']),
                'district': row['district'],
                'event_date_ad': row['event_date_ad'],
                'size': int(row['size']),
                'source_count': len(sources),
                'sources': json.dumps(sources, ensure_ascii=False),
                'municipality': row['municipality'],
                'municipality_candidates_json': row['municipality_candidates_json'],
                'ward_candidates_json': row['ward_candidates_json'],
                'place_name_candidates_json': row['place_name_candidates_json'],
                'representative_url': row['representative_url'],
            }
        )
    return cluster_rows


def load_canonical_review_rows(connection) -> list[dict[str, Any]]:
    """Load one full review row per canonical event."""

    rows = connection.execute(
        """
        SELECT c.event_id,
               c.dedup_cluster_id AS cluster_id,
               c.event_date_ad,
               c.district,
               c.municipality,
               c.municipality_candidates_json,
               c.ward_candidates_json,
               c.place_name_candidates_json,
               s.size,
               s.sources,
               json_array_length(s.sources) AS source_count,
               json_extract(c.event_payload, '$.representative_url') AS representative_url,
               e.title AS representative_title,
               e.route_lang,
               e.ward,
               e.deaths,
               e.missing,
               e.injured,
               e.trigger,
               e.conf_date,
               e.conf_district,
               e.conf_place,
               e.specificity_reason,
               e.specificity_score,
               e.scope_reason,
               e.location_reason
        FROM canonical_events c
        JOIN cluster_summary s ON s.cluster_id = c.dedup_cluster_id
        LEFT JOIN article_events e ON e.url = json_extract(c.event_payload, '$.representative_url')
        ORDER BY c.event_date_ad, c.district, c.event_id
        """
    ).fetchall()
    review_rows: list[dict[str, Any]] = []
    for row in rows:
        review_rows.append(
            {
                'event_id': row['event_id'],
                'cluster_id': row['cluster_id'],
                'event_date_ad': row['event_date_ad'],
                'district': row['district'],
                'municipality': row['municipality'],
                'ward': row['ward'],
                'size': int(row['size'] or 0),
                'source_count': int(row['source_count'] or 0),
                'sources': row['sources'],
                'representative_url': row['representative_url'],
                'representative_title': row['representative_title'],
                'route_lang': row['route_lang'],
                'deaths': row['deaths'],
                'missing': row['missing'],
                'injured': row['injured'],
                'trigger': row['trigger'],
                'conf_date': row['conf_date'],
                'conf_district': row['conf_district'],
                'conf_place': row['conf_place'],
                'specificity_reason': row['specificity_reason'],
                'specificity_score': row['specificity_score'],
                'scope_reason': row['scope_reason'],
                'location_reason': row['location_reason'],
            }
        )
    return review_rows


def load_low_confidence_class1_rows(connection) -> list[dict[str, Any]]:
    """Load low-confidence class-1 rows for manual QA."""

    rows = connection.execute(
        f"""
        SELECT url, source, title, event_date_ad, published_date_ad, district, municipality,
               conf_class, conf_date, conf_district, conf_place, conf_fatalities, conf_trigger,
               specificity_reason, scope_reason, location_reason
        FROM article_events
        WHERE class = 1
          AND (
              COALESCE(conf_class, 0) < {LOW_CONFIDENCE_THRESHOLD}
              OR COALESCE(conf_date, 0) < {LOW_CONFIDENCE_THRESHOLD}
              OR COALESCE(conf_district, 0) < {LOW_CONFIDENCE_THRESHOLD}
              OR COALESCE(conf_place, 0) < {LOW_CONFIDENCE_THRESHOLD}
          )
        ORDER BY event_date_ad, district, url
        """
    ).fetchall()
    return [dict(row) for row in rows]


def load_fallback_date_class1_rows(connection) -> list[dict[str, Any]]:
    """Load class-1 rows that still rely on publication-date fallback."""

    rows = connection.execute(
        f"""
        SELECT url, source, title, published_date_ad, event_date_ad, district, municipality,
               conf_date, specificity_reason, scope_reason
        FROM article_events
        WHERE class = 1
          AND published_date_ad IS NOT NULL
          AND event_date_ad = published_date_ad
          AND COALESCE(conf_date, 0) <= {FALLBACK_DATE_MAX_CONFIDENCE}
        ORDER BY event_date_ad, district, url
        """
    ).fetchall()
    return [dict(row) for row in rows]


def build_inventory_report(summary: dict[str, Any]) -> str:
    """Build a concise markdown report for pre-BIPAD QA."""

    core = summary['core_counts']
    lines = [
        '# Inventory Audit Report',
        '',
        f"Generated at: {summary['generated_at']}",
        '',
        '## Core Counts',
        f"- Raw articles: {core['raw_articles']}",
        f"- Article language rows: {core['article_lang']}",
        f"- Article events: {core['article_events']}",
        f"- Class 1 / 2 / 3: {core['class1']} / {core['class2']} / {core['class3']}",
        f"- Canonical events: {core['canonical_events']}",
        f"- Low-confidence Class 1 rows: {core['class1_low_confidence']}",
        f"- Fallback-date Class 1 rows: {core['class1_fallback_dates']}",
        '',
        '## Language Routing',
    ]
    for route_lang, count in sorted(summary['route_counts'].items()):
        lines.append(f"- {route_lang}: {count}")
    overlap = summary['district_language_overlap']
    lines.extend([
        '',
        '## District Language Overlap',
        f"- Districts seen in both EN and NP: {overlap['districts_both']}",
        f"- Districts only in EN: {len(overlap['districts_only_en'])}",
        f"- Districts only in NP: {len(overlap['districts_only_np'])}",
        '',
        '## Dedup Summary',
        f"- Total clusters: {summary['dedup_summary']['total_clusters']}",
        f"- Multi-source clusters: {summary['dedup_summary']['multi_source_clusters']}",
        f"- Max cluster size: {summary['dedup_summary']['max_cluster_size']}",
        '',
        '## Source Summary',
    ])
    for row in summary['source_summary']:
        lines.append(
            f"- {row['source']}: article_events={row['article_events_count']}, class1={row['class1_count']}, "
            f"specificity_ok={row['specificity_ok_count']}, in_nepal={row['in_nepal_count']}"
        )
    return '\n'.join(lines) + '\n'


def scalar(connection, query: str) -> int:
    """Return a single integer scalar query result."""

    row = connection.execute(query).fetchone()
    return int(row[0] or 0)
