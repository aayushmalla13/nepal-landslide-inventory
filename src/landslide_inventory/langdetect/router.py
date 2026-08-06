"""Language routing stage helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from langdetect import DetectorFactory, LangDetectException, detect

from ..config import AppConfig
from ..db import connect_sqlite, initialize_sqlite
from ..sources import load_sources
from ..utils import utc_now_iso

DetectorFactory.seed = 0
DEVANAGARI_START = ord("ऀ")
DEVANAGARI_END = ord("ॿ")


@dataclass(frozen=True)
class LanguageRouteResult:
    """Structured article routing decision."""

    devanagari_ratio: float
    langdetect_label: str
    route_lang: str
    mixed_flag: bool


def devanagari_ratio(text: str) -> float:
    """Return the share of alphabetic characters written in Devanagari."""

    letters = [character for character in text if character.isalpha()]
    if not letters:
        return 0.0
    devanagari_letters = [
        character
        for character in letters
        if DEVANAGARI_START <= ord(character) <= DEVANAGARI_END
    ]
    return len(devanagari_letters) / len(letters)


def route_language(text: str, config: AppConfig, source_lang_hint: str | None = None) -> LanguageRouteResult:
    """Route article text to the English or Nepali extraction path."""

    thresholds = dict(config.raw['language_detection'])
    devanagari_threshold = float(thresholds['devanagari_threshold'])
    mixed_lower = float(thresholds['mixed_lower'])
    mixed_upper = float(thresholds['mixed_upper'])

    ratio = devanagari_ratio(text)
    detected_label = detect_language_label(text)
    normalized_hint = normalize_route_label(source_lang_hint)

    if ratio > devanagari_threshold:
        return LanguageRouteResult(ratio, detected_label, 'np', False)
    if mixed_lower <= ratio <= mixed_upper:
        return LanguageRouteResult(ratio, detected_label, 'np', True)

    detected_route = normalize_route_label(detected_label)
    route_lang = detected_route or normalized_hint or 'en'
    return LanguageRouteResult(ratio, detected_label, route_lang, False)


def detect_language_label(text: str) -> str:
    """Return a best-effort langdetect label for article text."""

    sample = ' '.join(text.split())[:10000]
    if len(sample) < 20:
        return 'unknown'
    try:
        return str(detect(sample))
    except LangDetectException:
        return 'unknown'


def normalize_route_label(label: str | None) -> str | None:
    """Map source or detector labels to the pipeline's en/np route labels."""

    if label is None:
        return None
    normalized = str(label).strip().casefold()
    if normalized in {'np', 'ne', 'hi'}:
        return 'np'
    if normalized in {'en', 'english'}:
        return 'en'
    return None


def run_language_stage(config: AppConfig) -> int:
    """Populate the article_lang table from raw_articles."""

    initialize_sqlite(config.sqlite_path)
    source_lang_map = {source.slug: source.language for source in load_sources(config)}
    rows = list(_article_rows(config.sqlite_path))
    computed_at = utc_now_iso()
    with connect_sqlite(config.sqlite_path) as connection:
        for url, source, text in rows:
            result = route_language(text or '', config, source_lang_hint=source_lang_map.get(source))
            connection.execute(
                """
                INSERT INTO article_lang (
                    url, source, devanagari_ratio, langdetect_label, route_lang, mixed_flag, computed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(url) DO UPDATE SET
                    source = excluded.source,
                    devanagari_ratio = excluded.devanagari_ratio,
                    langdetect_label = excluded.langdetect_label,
                    route_lang = excluded.route_lang,
                    mixed_flag = excluded.mixed_flag,
                    computed_at = excluded.computed_at
                """,
                (
                    url,
                    source,
                    result.devanagari_ratio,
                    result.langdetect_label,
                    result.route_lang,
                    int(result.mixed_flag),
                    computed_at,
                ),
            )
        connection.commit()
    return len(rows)


def _article_rows(database_path: Path) -> Iterable[tuple[str, str, str | None]]:
    """Yield article rows to route in deterministic order."""

    with connect_sqlite(database_path) as connection:
        rows = connection.execute(
            """
            SELECT url, source, text
            FROM raw_articles
            ORDER BY url ASC
            """
        ).fetchall()
    for row in rows:
        yield str(row['url']), str(row['source']), row['text']
