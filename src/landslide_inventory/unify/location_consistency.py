"""Title/body location-consistency validation for extracted article events."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any, Callable, Iterable

from ..config import AppConfig
from ..db import connect_sqlite, initialize_sqlite
from ..gazetteer import district_to_province, normalize_district, normalize_municipality, municipality_to_district
from ..nlp_en import extract_en
from ..nlp_np import extract_np
from ..utils import utc_now_iso

LOGGER = logging.getLogger(__name__)

ExtractorFunc = Callable[[str | None, str, str | None, dict[str, Callable[..., Any]], dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class LocationCheckRow:
    url: str
    source: str
    title: str | None
    text: str
    route_lang: str
    published_date_ad: str | None
    event_class: int | None
    district: str | None
    municipality: str | None
    province: str | None


@dataclass(frozen=True)
class LocationDecision:
    location_consistent: int
    location_reason: str
    title_district: str | None
    title_municipality: str | None
    updated_district: str | None
    updated_municipality: str | None
    updated_province: str | None
    updated_class: int | None


def run_location_consistency_stage(config: AppConfig) -> int:
    """Validate title-derived location against extracted district/municipality."""

    initialize_sqlite(config.sqlite_path)
    rows = list(_location_rows(config.sqlite_path))
    checked_at = utc_now_iso()
    keywords_cfg = dict(config.raw['keywords'])
    en_gazetteer = {
        'normalize_district': lambda name: normalize_district(name, 'en'),
        'normalize_municipality': lambda name: normalize_municipality(name, 'en'),
        'municipality_to_district': municipality_to_district,
        'district_to_province': district_to_province,
    }
    np_gazetteer = {
        'normalize_district': lambda name: normalize_district(name, 'np'),
        'normalize_municipality': lambda name: normalize_municipality(name, 'np'),
        'municipality_to_district': municipality_to_district,
        'district_to_province': district_to_province,
    }

    changed = 0
    with connect_sqlite(config.sqlite_path) as connection:
        connection.execute('DELETE FROM article_location_check')
        connection.execute('UPDATE article_events SET location_consistent = NULL, location_reason = NULL')
        for row in rows:
            decision = decide_location_consistency(
                row=row,
                keywords_cfg=keywords_cfg,
                en_gazetteer=en_gazetteer,
                np_gazetteer=np_gazetteer,
            )
            connection.execute(
                """
                INSERT INTO article_location_check (
                    url, location_consistent, location_reason, title_district, title_municipality, checked_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(url) DO UPDATE SET
                    location_consistent = excluded.location_consistent,
                    location_reason = excluded.location_reason,
                    title_district = excluded.title_district,
                    title_municipality = excluded.title_municipality,
                    checked_at = excluded.checked_at
                """,
                (
                    row.url,
                    decision.location_consistent,
                    decision.location_reason,
                    decision.title_district,
                    decision.title_municipality,
                    checked_at,
                ),
            )
            connection.execute(
                """
                UPDATE article_events
                SET location_consistent = ?,
                    location_reason = ?,
                    district = ?,
                    municipality = ?,
                    province = ?,
                    class = COALESCE(?, class),
                    event_class = COALESCE(?, event_class),
                    conf_class = CASE WHEN ? IS NULL THEN conf_class ELSE MAX(COALESCE(conf_class, 0.0), 0.8) END,
                    conf_district = CASE WHEN ? = 1 THEN conf_district ELSE MIN(COALESCE(conf_district, 1.0), 0.7) END,
                    conf_place = CASE WHEN ? = 1 THEN conf_place ELSE MIN(COALESCE(conf_place, 1.0), 0.7) END
                WHERE url = ?
                """,
                (
                    decision.location_consistent,
                    decision.location_reason,
                    decision.updated_district,
                    decision.updated_municipality,
                    decision.updated_province,
                    decision.updated_class,
                    decision.updated_class,
                    decision.updated_class,
                    decision.location_consistent,
                    decision.location_consistent,
                    row.url,
                ),
            )
            if decision.location_consistent == 0:
                changed += 1
        connection.commit()
    LOGGER.info('Location consistency checked=%s changed=%s', len(rows), changed)
    return len(rows)


def decide_location_consistency(
    *,
    row: LocationCheckRow,
    keywords_cfg: dict[str, Any],
    en_gazetteer: dict[str, Callable[..., Any]],
    np_gazetteer: dict[str, Callable[..., Any]],
    en_extractor: ExtractorFunc = extract_en,
    np_extractor: ExtractorFunc = extract_np,
) -> LocationDecision:
    """Compare title-derived location evidence against stored article event location."""

    title = (row.title or '').strip()
    if not title:
        return LocationDecision(1, 'no_title_signal', None, None, row.district, row.municipality, row.province, None)

    title_text = title
    if row.route_lang == 'np':
        result = np_extractor(title, title_text, row.published_date_ad, np_gazetteer, keywords_cfg)
    else:
        result = en_extractor(title, title_text, row.published_date_ad, en_gazetteer, keywords_cfg)

    title_municipality = result.get('municipality')
    title_district = result.get('district')
    if title_municipality:
        title_district = municipality_to_district(title_municipality) or title_district

    if not title_district and not title_municipality:
        return LocationDecision(1, 'no_title_signal', None, None, row.district, row.municipality, row.province, None)

    if title_municipality and title_municipality == row.municipality:
        canonical_district = municipality_to_district(title_municipality) or row.district
        return LocationDecision(1, 'title_match', canonical_district, title_municipality, canonical_district, row.municipality, district_to_province(canonical_district) if canonical_district else row.province, None)

    if title_district and row.district and title_district == row.district and (not title_municipality or row.municipality is None):
        return LocationDecision(1, 'title_match', title_district, title_municipality, row.district, row.municipality, row.province, None)

    if title_municipality:
        canonical_district = municipality_to_district(title_municipality)
        updated_class = 2 if row.event_class == 1 else row.event_class
        return LocationDecision(
            0,
            'title_municipality_conflict',
            canonical_district,
            title_municipality,
            canonical_district,
            title_municipality,
            district_to_province(canonical_district) if canonical_district else None,
            updated_class,
        )

    if title_district and title_district != row.district:
        updated_class = 2 if row.event_class == 1 else row.event_class
        return LocationDecision(
            0,
            'title_district_conflict',
            title_district,
            None,
            title_district,
            None,
            district_to_province(title_district),
            updated_class,
        )

    return LocationDecision(1, 'title_match', title_district, title_municipality, row.district, row.municipality, row.province, None)


def _location_rows(database_path: Path) -> Iterable[LocationCheckRow]:
    with connect_sqlite(database_path) as connection:
        rows = connection.execute(
            """
            SELECT e.url, e.source, e.title, COALESCE(r.text, '') AS text,
                   COALESCE(e.route_lang, l.route_lang, 'en') AS route_lang,
                   e.published_date_ad, e.class, e.district, e.municipality, e.province
            FROM article_events e
            LEFT JOIN raw_articles r ON r.url = e.url
            LEFT JOIN article_lang l ON l.url = e.url
            WHERE e.class = 1
            ORDER BY e.url ASC
            """
        ).fetchall()
    for row in rows:
        yield LocationCheckRow(
            url=str(row['url']),
            source=str(row['source']),
            title=row['title'],
            text=str(row['text'] or ''),
            route_lang=str(row['route_lang'] or 'en'),
            published_date_ad=row['published_date_ad'],
            event_class=int(row['class']) if row['class'] is not None else None,
            district=row['district'],
            municipality=row['municipality'],
            province=row['province'],
        )
