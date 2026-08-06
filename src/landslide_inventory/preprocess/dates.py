"""Published-date normalization utilities and stage logic."""

from __future__ import annotations

from datetime import date, datetime
import re
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

import nepali_datetime

from ..config import AppConfig
from ..db import connect_sqlite, initialize_sqlite
from ..sources import load_sources

DEVANAGARI_DIGITS = str.maketrans('०१२३४५६७८९', '0123456789')
BS_DATE_PATTERN = re.compile(r'\b(20[7-9]\d)[\-/\.](\d{1,2})[\-/\.](\d{1,2})\b')
BS_MONTH_NAME_PATTERN = re.compile(
    r'(?:आइतबार|सोमबार|मंगलबार|बुधबार|बिहीबार|शुक्रबार|शनिबार)?\s*,?\s*'
    r'(बैशाख|वैशाख|जेठ|असार|साउन|भदौ|असोज|कात्तिक|कार्तिक|मंसिर|पुष|पुस|माघ|फागुन|चैत)\s+'
    r'(\d{1,2})\s*,?\s*(20[7-9]\d)',
)
BS_YEAR_MONTH_NAME_PATTERN = re.compile(
    r'(20[7-9]\d)\s*(बैशाख|वैशाख|जेठ|असार|साउन|भदौ|असोज|कात्तिक|कार्तिक|मंसिर|पुष|पुस|माघ|फागुन|चैत)\s+'
    r'(\d{1,2})(?:\s*गते)?'
)
BS_MONTH_MAP = {
    'बैशाख': 1,
    'वैशाख': 1,
    'जेठ': 2,
    'असार': 3,
    'साउन': 4,
    'भदौ': 5,
    'असोज': 6,
    'कात्तिक': 7,
    'कार्तिक': 7,
    'मंसिर': 8,
    'पुष': 9,
    'पुस': 9,
    'माघ': 10,
    'फागुन': 11,
    'चैत': 12,
}
URL_DATE_PATTERN = re.compile(r'/(20\d{2})/(\d{2})/(\d{2})(?:/|$)')
EN_MONTH_PATTERN = (
    'January|February|March|April|May|June|July|August|September|October|November|December'
)
EN_LEAD_MONTH_DAY_PATTERN = re.compile(
    rf'(?:^|[\s,.;:])(?:[A-Z][A-Za-z.\'-]*(?:\s+[A-Z][A-Za-z.\'-]*)*,\s+)?'
    rf'({EN_MONTH_PATTERN})\s+(\d{{1,2}})(?!,\s*\d{{4}})',
)
BS_DAY_MONTH_PATTERN = re.compile(
    r'(?<!\d)(\d{1,2})\s*(बैशाख|वैशाख|जेठ|असार|साउन|भदौ|असोज|कात्तिक|कार्तिक|मंसिर|पुष|पुस|माघ|फागुन|चैत)(?=(?:,|\s|$))'
)

COMMON_DATE_FORMATS = (
    '%Y-%m-%d',
    '%Y/%m/%d',
    '%Y.%m.%d',
    '%B %d, %Y',
    '%b %d, %Y',
    '%d %B %Y',
    '%d %b %Y',
    '%Y-%m-%d %H:%M:%S',
    '%Y-%m-%d %H:%M',
    '%A, %d %B %Y',
)


def devanagari_to_ascii_digits(text: str) -> str:
    """Translate Devanagari digits to ASCII digits."""

    return text.translate(DEVANAGARI_DIGITS)


def detect_bs_date(text: str) -> tuple[int, int, int] | None:
    """Detect a Bikram Sambat date written numerically or with Nepali month names."""

    normalized = devanagari_to_ascii_digits(text)
    match = BS_DATE_PATTERN.search(normalized)
    if match is not None:
        year, month, day = (int(part) for part in match.groups())
        if 1 <= month <= 12 and 1 <= day <= 32:
            return year, month, day

    month_match = BS_MONTH_NAME_PATTERN.search(normalized)
    if month_match is not None:
        month_name, day_text, year_text = month_match.groups()
        month = BS_MONTH_MAP.get(month_name)
        day = int(day_text)
        if month is not None and 1 <= day <= 32:
            return int(year_text), month, day

    year_first_match = BS_YEAR_MONTH_NAME_PATTERN.search(normalized)
    if year_first_match is None:
        return None
    year_text, month_name, day_text = year_first_match.groups()
    month = BS_MONTH_MAP.get(month_name)
    day = int(day_text)
    if month is None or not (1 <= day <= 32):
        return None
    return int(year_text), month, day


def bs_to_ad(bs_date: tuple[int, int, int]) -> date:
    """Convert a Bikram Sambat date tuple to Gregorian AD date."""

    year, month, day = bs_date
    converted = nepali_datetime.date(year, month, day).to_datetime_date()
    return converted


def extract_date_from_url(url: str) -> str | None:
    """Extract an ISO date from article URLs that encode /YYYY/MM/DD/."""

    match = URL_DATE_PATTERN.search(urlparse(url).path)
    if match is None:
        return None
    year, month, day = match.groups()
    return f'{year}-{month}-{day}'


def extract_year_hint_from_url(url: str) -> int | None:
    """Extract a YYYY hint from article URLs that encode /YYYY/MM/... patterns."""

    parts = [part for part in urlparse(url).path.split('/') if part]
    for index, part in enumerate(parts[:-1]):
        if len(part) == 4 and part.isdigit() and part.startswith('20'):
            next_part = parts[index + 1]
            if len(next_part) == 2 and next_part.isdigit():
                try:
                    return int(part)
                except ValueError:
                    return None
    return None


def normalize_published_date(
    raw_str: str | None,
    source_lang: str,
    *,
    year_hint: int | None = None,
) -> str | None:
    """Normalize a published date string to ISO YYYY-MM-DD."""

    if raw_str is None:
        return None
    text = devanagari_to_ascii_digits(raw_str).strip()
    if not text:
        return None

    bs_date = detect_bs_date(text) if source_lang == 'np' else None
    if bs_date is not None:
        return bs_to_ad(bs_date).isoformat()

    if year_hint is not None:
        hinted = _extract_no_year_date(text, source_lang, year_hint)
        if hinted is not None:
            return hinted

    iso_candidate = _parse_iso_datetime(text)
    if iso_candidate is not None:
        return iso_candidate.isoformat()

    cleaned = _clean_date_text(text)
    for fmt in COMMON_DATE_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def normalize_dates_in_sqlite(config: AppConfig) -> int:
    """Normalize missing published_date_ad values in SQLite and return update count."""

    initialize_sqlite(config.sqlite_path)
    source_lang_map = {source.slug: source.language for source in load_sources(config)}
    pending_rows = list(_pending_raw_articles(config.sqlite_path))
    updated = 0
    with connect_sqlite(config.sqlite_path) as connection:
        for url, source, published_date_raw, published_date_ad, text, year_hint in pending_rows:
            raw_value = published_date_raw
            url_date = extract_date_from_url(url)
            if raw_value is None or not str(raw_value).strip():
                if url_date is not None:
                    raw_value = url_date
                    connection.execute(
                        'UPDATE raw_articles SET published_date_raw = ? WHERE url = ? AND (published_date_raw IS NULL OR TRIM(published_date_raw) = "")',
                        (url_date, url),
                    )
            lang = source_lang_map.get(source, 'en')
            url_year_hint = extract_year_hint_from_url(url)
            effective_year_hint = url_year_hint if url_year_hint is not None else year_hint
            normalized = normalize_published_date(raw_value, lang, year_hint=effective_year_hint)
            text_candidate = _extract_date_from_text(text, lang, effective_year_hint)
            current_year = _iso_year(published_date_ad)
            hinted_year = int(effective_year_hint) if effective_year_hint is not None else None
            if url_date is not None and hinted_year is not None and current_year is not None and current_year != hinted_year:
                raw_from_url = url_date
                if _iso_year(raw_from_url) == hinted_year:
                    normalized = raw_from_url
            raw_text = str(raw_value).strip() if raw_value is not None else ''
            raw_is_missing = not raw_text
            raw_looks_machine = bool(re.fullmatch(r'\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}(?::\d{2})?)?', raw_text))
            if source == 'rising-nepal' and text_candidate is not None:
                normalized = text_candidate
            elif lang == 'np' and text_candidate is not None and (raw_is_missing or raw_looks_machine):
                normalized = text_candidate
            elif hinted_year is not None and current_year is not None and current_year != hinted_year:
                preferred = _prefer_year_matched_candidate((text_candidate, normalized), hinted_year)
                if preferred is not None:
                    normalized = preferred
            elif normalized is None and text_candidate is not None:
                normalized = text_candidate
            if normalized is None:
                continue
            if normalized != (published_date_ad or ''):
                connection.execute(
                    'UPDATE raw_articles SET published_date_ad = ? WHERE url = ?',
                    (normalized, url),
                )
                updated += 1
        connection.commit()
    return updated


def _pending_raw_articles(
    database_path: Path,
) -> Iterable[tuple[str, str, str | None, str | None, str | None, int | None]]:
    """Yield raw articles that still need published_date_ad normalization or repair."""

    with connect_sqlite(database_path) as connection:
        rows = connection.execute(
            '''
            SELECT r.url,
                   r.source,
                   r.published_date_raw,
                   r.published_date_ad,
                   r.text,
                   MAX(d.year_hint) AS year_hint
            FROM raw_articles AS r
            LEFT JOIN discovered_urls AS d
              ON d.url = r.url
            GROUP BY r.url, r.source, r.published_date_raw, r.published_date_ad, r.text
            ORDER BY r.url ASC
            '''
        ).fetchall()
    for row in rows:
        yield (
            str(row['url']),
            str(row['source']),
            row['published_date_raw'],
            row['published_date_ad'],
            row['text'],
            row['year_hint'],
        )


def _parse_iso_datetime(text: str) -> date | None:
    """Parse ISO dates and datetimes, including trailing Z timestamps."""

    candidate = text.replace('Z', '+00:00')
    try:
        return datetime.fromisoformat(candidate).date()
    except ValueError:
        pass
    try:
        return date.fromisoformat(candidate[:10])
    except ValueError:
        return None


def _clean_date_text(text: str) -> str:
    """Clean a raw date string for strptime parsing."""

    cleaned = text.strip()
    cleaned = re.sub(r'\s+', ' ', cleaned)
    cleaned = re.sub(r'\s*,\s*', ', ', cleaned)
    return cleaned



def _extract_date_from_text(text: str | None, source_lang: str, year_hint: int | None) -> str | None:
    """Extract a publish-date candidate from the early article text."""

    if not text:
        return None
    if source_lang == 'np':
        early_window = text[:1500]
        candidate = normalize_published_date(early_window, source_lang, year_hint=year_hint)
        if candidate is not None:
            return candidate
    lead = _lead_window(text)
    return normalize_published_date(lead, source_lang, year_hint=year_hint)


def _lead_window(text: str, limit: int = 280) -> str:
    """Keep date inference anchored to the article lead, not trailing boilerplate."""

    stripped = text.strip()
    if not stripped:
        return ''
    first_paragraph = stripped.split("\n\n", 1)[0]
    return first_paragraph[:limit]


def _extract_no_year_date(text: str, source_lang: str, year_hint: int) -> str | None:
    """Infer month/day-only dates using the discovery year hint."""

    if source_lang == 'np':
        return _infer_bs_no_year_date(text, year_hint)
    return _infer_english_no_year_date(text, year_hint)


def _infer_english_no_year_date(text: str, year_hint: int) -> str | None:
    match = EN_LEAD_MONTH_DAY_PATTERN.search(text)
    if match is None:
        return None
    try:
        return datetime.strptime(
            f"{match.group(1)} {int(match.group(2))} {year_hint}",
            '%B %d %Y',
        ).date().isoformat()
    except ValueError:
        return None


def _infer_bs_no_year_date(text: str, year_hint: int) -> str | None:
    normalized = devanagari_to_ascii_digits(text)
    match = BS_DAY_MONTH_PATTERN.search(normalized)
    if match is None:
        return None
    day = int(match.group(1))
    month = BS_MONTH_MAP.get(match.group(2))
    if month is None or not (1 <= day <= 32):
        return None
    candidates: list[date] = []
    for bs_year in range(year_hint + 55, year_hint + 58):
        try:
            candidate = bs_to_ad((bs_year, month, day))
        except Exception:
            continue
        if abs(candidate.year - year_hint) <= 1:
            candidates.append(candidate)
    if not candidates:
        return None
    for candidate in candidates:
        if candidate.year == year_hint:
            return candidate.isoformat()
    return candidates[0].isoformat()


def _iso_year(value: str | None) -> int | None:
    if not value or len(value) < 4:
        return None
    try:
        return int(value[:4])
    except ValueError:
        return None


def _prefer_year_matched_candidate(candidates: tuple[str | None, ...], year_hint: int) -> str | None:
    for candidate in candidates:
        if _iso_year(candidate) == year_hint:
            return candidate
    return None
