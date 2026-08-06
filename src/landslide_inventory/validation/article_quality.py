"""Detect rows in ``raw_articles`` that are not articles.

Why this module exists
----------------------
Review section 4.4 flagged that the crawler ingests navigation pages, citing
``kathmandupost.com/national/province-no-2`` titled "Madhesh Province - The
Kathmandu Post".

Measuring it turned up something larger that the review did not catch:

**615 of the 992 himalayan-times rows are HTTP 429 rate-limit error pages,
stored as articles.** Their body is the literal string "You have exceeded the
rate limit. Please try again later." (57 characters), their title is empty, and
``http_status = 429``. They went through the whole pipeline as if they were
news. The himalayan-times body-length distribution is median 57 characters --
the *median* row from that outlet is an error page.

Fifty class-1 events rest on a himalayan-times row with under 200 characters of
body, i.e. they were classified from a title alone.

Two corrections to the review, both measured
--------------------------------------------
1. **Kathmandu Post is not mostly section pages.** 9 of 75 KP rows are section
   landing pages; the other 66 are real articles with a median 4,496-character
   body -- they are simply not about landslides. The KP problem is archive
   depth (every KP row is from 2026), not garbage.

2. **The 485 "2026" rows are not carrying the scrape date.** Their
   ``published_date_raw`` values are real timestamps ("2026-03-24 18:03:16")
   and the published month matches the fetched month. They are genuinely recent
   articles. The real issue is that ``config.yaml`` admits 2015-2026 while the
   README and paper_metadata claim 2015-2024 (review section 3.5).

Policy
------
This module **flags and reports**; it does not delete. Deleting rows from
``raw_articles`` would destroy the collection record and make the coverage
report a lie. Non-articles should be excluded downstream by
``is_ingestible_article``, and the counts should be disclosed in the methods
section as collection loss.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import re
from typing import Any, Iterable, Sequence

from ..config import AppConfig
from ..db import connect_sqlite
from ..utils import ensure_directory
from .common import iso_now, write_csv

LOGGER = logging.getLogger(__name__)

# Bodies that are server responses rather than content. Matched against the
# start of the body so a genuine article quoting one of these is not caught.
ERROR_BODY_MARKERS = (
    'you have exceeded the rate limit',
    'too many requests',
    'access denied',
    '403 forbidden',
    '404 not found',
    'page not found',
    'service unavailable',
    'are you a robot',
    'enable javascript',
    'your browser is not supported',
)

# URL shapes that address a section index rather than a story. Every real
# article URL in this corpus carries either a dated path segment
# (/2026/03/24/) or a numeric story id.
SECTION_URL_PATTERN = re.compile(
    r'/(?:national|category|categories|tag|tags|topic|topics|author|authors|search|page|archive)/?$'
    r'|/province-no-\d+/?$'
    r'|/(?:food|sports|money|opinion|columns|health|football)/[a-z-]+/?$',
    re.IGNORECASE,
)

ARTICLE_URL_PATTERN = re.compile(
    r'/\d{4}/\d{2}/\d{2}/'          # dated path: /2026/03/24/slug
    r'|/(?:story|news|content|detail)/\d+'  # numeric story id
    r'|/\d{6,}',                    # bare numeric id
    re.IGNORECASE,
)

# Titles that name a section rather than a story.
SECTION_TITLE_PATTERN = re.compile(
    r'^\s*(?:[A-Za-z]+\s+)?(?:Province|National\s+Security|Recipes|Food|Sports|Opinion|Columns|Money|Health)'
    r'(?:\s*-\s*(?:The\s+)?[A-Za-z ]+)?\s*$',
    re.IGNORECASE,
)

# Below this, a "body" cannot support event extraction; classification would
# rest on the title alone.
MIN_BODY_CHARS = 200

REPORT_COLUMNS = ['url', 'source', 'verdict', 'reason', 'http_status', 'body_chars', 'title']


@dataclass(frozen=True)
class QualityVerdict:
    is_article: bool
    reason: str


def classify_raw_article(
    url: str,
    title: str | None,
    text: str | None,
    http_status: int | None,
    parse_success: int | None,
) -> QualityVerdict:
    """Decide whether a ``raw_articles`` row is usable as an article.

    Checks run cheapest-and-most-decisive first. ``http_status`` is the
    strongest signal available and was not being consulted at all -- a 429 page
    is not a news article no matter what its body says.
    """

    body = (text or '').strip()
    heading = (title or '').strip()
    body_head = body[:200].casefold()

    if http_status is not None and int(http_status) != 200:
        return QualityVerdict(False, f'http_{int(http_status)}')
    if any(marker in body_head for marker in ERROR_BODY_MARKERS):
        return QualityVerdict(False, 'error_page_body')
    if not heading:
        return QualityVerdict(False, 'no_title')
    if SECTION_TITLE_PATTERN.match(heading):
        return QualityVerdict(False, 'section_title')
    if SECTION_URL_PATTERN.search(url) and not ARTICLE_URL_PATTERN.search(url):
        return QualityVerdict(False, 'section_url')
    if len(body) < MIN_BODY_CHARS:
        # Not necessarily junk -- some outlets publish genuine short briefs --
        # but an event cannot be responsibly extracted from this, so it is
        # separated out rather than silently trusted.
        return QualityVerdict(False, 'body_too_short')
    if parse_success is not None and int(parse_success) == 0:
        return QualityVerdict(False, 'parse_failed')
    return QualityVerdict(True, 'ok')


def is_ingestible_article(
    url: str,
    title: str | None,
    text: str | None,
    http_status: int | None,
    parse_success: int | None = None,
) -> bool:
    """Gate for the extraction stage. True only for rows that are real articles."""

    return classify_raw_article(url, title, text, http_status, parse_success).is_article


def scan_corpus(connection) -> list[dict[str, Any]]:
    """Classify every raw article. Returns one record per row."""

    query = """
        SELECT url, source, COALESCE(title, '') AS title, COALESCE(text, '') AS text,
               http_status, parse_success
        FROM raw_articles
        ORDER BY url
    """
    records: list[dict[str, Any]] = []
    for record in connection.execute(query):
        item = dict(record)
        verdict = classify_raw_article(
            item['url'], item['title'], item['text'], item['http_status'], item['parse_success']
        )
        records.append({
            'url': item['url'],
            'source': item['source'],
            'verdict': 'article' if verdict.is_article else 'not_article',
            'reason': verdict.reason,
            'http_status': item['http_status'],
            'body_chars': len(item['text'] or ''),
            'title': ' '.join((item['title'] or '').split())[:150],
        })
    return records


def summarize(records: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate by source and reason for the methods-section disclosure."""

    by_source: dict[str, dict[str, int]] = {}
    by_reason: dict[str, int] = {}
    for record in records:
        bucket = by_source.setdefault(record['source'], {'total': 0, 'article': 0, 'not_article': 0})
        bucket['total'] += 1
        bucket[record['verdict']] += 1
        if record['verdict'] == 'not_article':
            by_reason[record['reason']] = by_reason.get(record['reason'], 0) + 1
    return {
        'total': len(records),
        'article': sum(1 for r in records if r['verdict'] == 'article'),
        'not_article': sum(1 for r in records if r['verdict'] == 'not_article'),
        'by_reason': dict(sorted(by_reason.items(), key=lambda kv: -kv[1])),
        'by_source': dict(sorted(by_source.items(), key=lambda kv: -kv[1]['not_article'])),
    }


def run_article_quality_stage(config: AppConfig) -> dict[str, Any]:
    """Write the non-article report. Flags only -- deletes nothing."""

    outputs_dir = config.resolve_path('outputs_dir')
    ensure_directory(outputs_dir)
    report_path = outputs_dir / 'raw_article_quality.csv'

    with connect_sqlite(config.sqlite_path) as connection:
        records = scan_corpus(connection)

    write_csv(report_path, REPORT_COLUMNS, records)
    summary = summarize(records)
    summary['generated_at'] = iso_now()
    summary['report'] = str(report_path)

    LOGGER.info(
        'Article quality: %d of %d rows are not usable articles (%.1f%%)',
        summary['not_article'], summary['total'],
        100.0 * summary['not_article'] / max(summary['total'], 1),
    )
    for reason, count in summary['by_reason'].items():
        LOGGER.info('  reason=%-20s %d', reason, count)
    for source, counts in summary['by_source'].items():
        if counts['not_article']:
            LOGGER.warning(
                '  %-18s %d/%d unusable (%.0f%%)',
                source, counts['not_article'], counts['total'],
                100.0 * counts['not_article'] / max(counts['total'], 1),
            )
    return summary
