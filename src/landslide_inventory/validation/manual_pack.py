"""Manual verification pack generation for article-level review."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

from ..config import AppConfig
from ..db import connect_sqlite, initialize_sqlite
from .common import derive_year, normalize_whitespace, stable_sample, write_csv

OUTPUT_COLUMNS = [
    'url', 'source', 'year', 'route_lang', 'title', 'snippet',
    'class_pred', 'district_pred', 'municipality_pred', 'ward_pred',
    'event_date_pred', 'deaths_pred', 'missing_pred', 'injured_pred', 'trigger_pred',
    'specificity_reason', 'specificity_score',
    'class_true', 'district_true', 'municipality_true', 'date_true', 'deaths_true', 'trigger_true', 'notes',
]


_CODE_SNIPPET_HINTS = (
    'getattribute(',
    'firstchild',
    'setattribute(',
    'return e.',
    'function(e',
    'function (e',
    'tolowercase()',
    'innerhtml',
    'defaultvalue',
)


def clean_manual_snippet(title: str, snippet: str) -> str:
    """Return a reviewer-friendly snippet even when stored raw text is contaminated."""

    cleaned = normalize_whitespace(snippet)
    if not cleaned:
        return ''
    if not _looks_like_code_snippet(cleaned):
        return cleaned[:280]
    fallback = _fallback_snippet_from_title(title)
    return fallback[:280]


def _looks_like_code_snippet(text: str) -> bool:
    sample = text[:280].lower()
    if any(hint in sample for hint in _CODE_SNIPPET_HINTS):
        return True
    punctuation = sum(1 for ch in sample if not ch.isalnum() and not ch.isspace())
    letters = sum(1 for ch in sample if ch.isalpha())
    if letters == 0 and punctuation > 20:
        return True
    if letters and punctuation / max(letters, 1) > 0.45 and ('===' in sample or '||' in sample or '){' in sample):
        return True
    return False


def _fallback_snippet_from_title(title: str) -> str:
    cleaned_title = normalize_whitespace(title)
    cleaned_title = re.sub(r'\s*-\s*The Himalayan Times.*$', '', cleaned_title, flags=re.IGNORECASE)
    return cleaned_title


@dataclass(frozen=True)
class ManualPackRow:
    url: str
    source: str
    year: str
    route_lang: str
    title: str
    snippet: str
    class_pred: int | None
    district_pred: str | None
    municipality_pred: str | None
    ward_pred: str | None
    event_date_pred: str | None
    deaths_pred: int | None
    missing_pred: int | None
    injured_pred: int | None
    trigger_pred: str | None
    specificity_reason: str | None
    specificity_score: float | None


def run_manual_pack_stage(config: AppConfig) -> int:
    """Generate the stratified manual verification sample CSV."""

    initialize_sqlite(config.sqlite_path)
    validation_cfg = dict(config.raw['validation'])
    total = int(validation_cfg.get('manual_sample_total', 150))
    target_en = int(validation_cfg.get('manual_en', total // 2))
    target_np = int(validation_cfg.get('manual_np', total - target_en))
    seed = int(validation_cfg['random_seed'])
    rows = load_manual_pack_rows(config.sqlite_path)
    sample = build_manual_pack_sample(rows, target_en, target_np, seed)
    output_path = config.resolve_path('outputs_dir') / 'manual_verification_sample.csv'
    write_csv(output_path, OUTPUT_COLUMNS, [row_to_dict(row) for row in sample])
    return len(sample)


def load_manual_pack_rows(database_path: Path) -> list[ManualPackRow]:
    """Load candidate article rows for manual review."""

    with connect_sqlite(database_path) as connection:
        rows = connection.execute(
            """
            SELECT e.url, e.source,
                   COALESCE(substr(e.published_date_ad, 1, 4), substr(e.event_date_ad, 1, 4), substr(e.published_date_raw, 1, 4), '') AS year,
                   COALESCE(e.route_lang, l.route_lang, 'en') AS route_lang,
                   COALESCE(e.title, '') AS title,
                   substr(COALESCE(r.text, ''), 1, 280) AS snippet,
                   e.class, e.district, e.municipality, e.ward,
                   e.event_date_ad, e.deaths, e.missing, e.injured, e.trigger,
                   e.specificity_reason, e.specificity_score
            FROM article_events e
            LEFT JOIN raw_articles r ON r.url = e.url
            LEFT JOIN article_lang l ON l.url = e.url
            WHERE COALESCE(e.in_nepal, 1) = 1
              AND COALESCE(e.class, 3) IN (1, 2)
            ORDER BY e.url ASC
            """
        ).fetchall()
    return [
        ManualPackRow(
            url=str(row['url']),
            source=str(row['source']),
            year=derive_year(str(row['year'] or '')),
            route_lang=str(row['route_lang'] or 'en'),
            title=normalize_whitespace(str(row['title'] or '')),
            snippet=clean_manual_snippet(str(row['title'] or ''), str(row['snippet'] or '')),
            class_pred=int(row['class']) if row['class'] is not None else None,
            district_pred=row['district'],
            municipality_pred=row['municipality'],
            ward_pred=row['ward'],
            event_date_pred=row['event_date_ad'],
            deaths_pred=int(row['deaths']) if row['deaths'] is not None else None,
            missing_pred=int(row['missing']) if row['missing'] is not None else None,
            injured_pred=int(row['injured']) if row['injured'] is not None else None,
            trigger_pred=row['trigger'],
            specificity_reason=row['specificity_reason'],
            specificity_score=float(row['specificity_score']) if row['specificity_score'] is not None else None,
        )
        for row in rows
    ]


def build_manual_pack_sample(rows: list[ManualPackRow], target_en: int, target_np: int, seed: int) -> list[ManualPackRow]:
    """Build a deterministic language-balanced sample spread across years."""

    en_rows = [row for row in rows if row.route_lang == 'en']
    np_rows = [row for row in rows if row.route_lang == 'np']
    selected = []
    selected.extend(_sample_language_rows(en_rows, target_en, seed + 11))
    selected.extend(_sample_language_rows(np_rows, target_np, seed + 29))
    return sorted(selected, key=lambda row: (row.route_lang, row.year, row.url))


def _sample_language_rows(rows: list[ManualPackRow], target: int, seed: int) -> list[ManualPackRow]:
    if len(rows) <= target:
        return sorted(rows, key=lambda row: (row.year, row.url))
    buckets: dict[str, list[ManualPackRow]] = {}
    for row in rows:
        year = row.year or 'unknown'
        buckets.setdefault(year, []).append(row)
    for year, bucket in buckets.items():
        buckets[year] = stable_sample(bucket, len(bucket), seed, key=lambda item: item.url)
    years = sorted(buckets)
    selected: list[ManualPackRow] = []
    while len(selected) < target and any(buckets[year] for year in years):
        for year in years:
            if len(selected) >= target:
                break
            if not buckets[year]:
                continue
            selected.append(buckets[year].pop(0))
    return selected


def row_to_dict(row: ManualPackRow) -> dict[str, Any]:
    """Convert a manual-pack row to CSV-friendly dict output."""

    return {
        'url': row.url,
        'source': row.source,
        'year': row.year,
        'route_lang': row.route_lang,
        'title': normalize_whitespace(row.title),
        'snippet': clean_manual_snippet(row.title, row.snippet),
        'class_pred': row.class_pred,
        'district_pred': row.district_pred,
        'municipality_pred': row.municipality_pred,
        'ward_pred': row.ward_pred,
        'event_date_pred': row.event_date_pred,
        'deaths_pred': row.deaths_pred,
        'missing_pred': row.missing_pred,
        'injured_pred': row.injured_pred,
        'trigger_pred': row.trigger_pred,
        'specificity_reason': row.specificity_reason,
        'specificity_score': row.specificity_score,
        'class_true': '',
        'district_true': '',
        'municipality_true': '',
        'date_true': '',
        'deaths_true': '',
        'trigger_true': '',
        'notes': '',
    }
