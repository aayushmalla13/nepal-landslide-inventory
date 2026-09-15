"""Article parsing helpers."""

from __future__ import annotations

import json
import re
from html import unescape
from html.parser import HTMLParser

from bs4 import BeautifulSoup

from ..sources import SourceDefinition
from .models import ParsedArticle

SOURCE_CONTENT_CLASSES = {
    "kathmandu-post": {"story-element-text", "story-body", "story__content"},
    "himalayan-times": {"entry-content", "post-content", "content-inner", "jeg_inner_content"},
    "online-khabar": {"ok18-single-post-content-wrap", "ok18-post-content-wrap", "entry-content"},
    "onlinekhabar-en": {"ok18-single-post-content-wrap", "ok18-post-content-wrap", "entry-content", "post-content"},
    "myrepublica": {"news-detail-content", "news-description"},
    "setopati": {"editor-box", "news-content"},
    "deshsanchar": {"entry-content", "post-content", "single-post-content"},
    "rajdhani": {"entry-content", "post-content", "elementor-widget-theme-post-content"},
    "nagarik": {"news-content", "content", "content-detail"},
    "nepali-times": {"article-content", "entry-content", "post-content", "prose"},
    "ujyaalo": {"editor-box", "detail-content-box"},
    "nepalpress": {"news-content-area", "news-post-content"},
    "nepalpress-en": {"news-content-area", "news-post-content"},
}
META_PUBLISHED_NAMES = {
    "article:published_time",
    "og:published_time",
    "publish-date",
    "pubdate",
    "date",
    "datepublished",
    "article:published",
    "publishdate",
}
DATE_PATTERN = re.compile(
    r"\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:?\d{2})?)?"
)
JSON_LD_DATE_PATTERN = re.compile(r'"datePublished"\s*:\s*"([^"]+)"', flags=re.IGNORECASE)
JSON_PUBLISH_KEY_CANDIDATES = ('datePublished', 'Published', 'published', 'publishedAt', 'published_at', 'publish_date')
TIME_DATETIME_PATTERN = re.compile(
    r"<time\b[^>]*\bdatetime=[\"']([^\"']+)[\"'][^>]*>",
    flags=re.IGNORECASE,
)
URL_DATE_PATTERN = re.compile(r"/(20\d{2})/(\d{2})/(\d{2})(?:/|$)")
SETOPATI_BS_PATTERN = re.compile(
    r"प्रकाशित\s*मिति\s*:\s*([^<\n]+?\d{4})(?:\s|&nbsp;)*(\d{1,2}:\d{2})?",
    flags=re.IGNORECASE,
)
GENERIC_DATE_TEXT_PATTERN = re.compile(
    r"(?:datePublished|Published|प्रकाशित\s*मिति)\s*[:\"]?\s*([0-9०-९]{4}[-/][0-9०-९]{1,2}[-/][0-9०-९]{1,2}(?:[T\s][0-9०-९:]{4,8}(?:Z|[+-][0-9:]+)?)?)",
    flags=re.IGNORECASE,
)
MONTH_NAME_DATE_PATTERN = re.compile(
    r"(?:(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)(?:day)?|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+\d{1,2}\s+"
    r"(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}",
    flags=re.IGNORECASE,
)
MONTH_DAY_YEAR_PATTERN = re.compile(
    r"(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}",
    flags=re.IGNORECASE,
)

PARSE_NOISE_MARKERS = (
    'firstChild.getAttribute',
    'function(e,t,n)',
    'getAttribute("href")',
    'e.nodeName.toLowerCase()',
    'jQuery',
    'समाचार अदालत/प्रशासन सुरक्षा/अपराध',
    'थप समाचार',
)
RATOPATI_NAV_MARKERS = (
    'समाचार अदालत/प्रशासन सुरक्षा/अपराध',
    'थप समाचार',
)
RATOPATI_FOOTER_MARKERS = (
    '‘सबैको, सबैभन्दा राम्रो’ रातोपाटी डटकम',
    'Bakhundole, Lalitpur',
    '© 2026 Copyright Ratopati News Network',
    '© 2025 Copyright Ratopati News Network',
)


class ArticleHTMLParser(HTMLParser):
    """Minimal HTML parser for article pages."""

    def __init__(self, source_slug: str) -> None:
        super().__init__()
        self.source_slug = source_slug
        self.title: str | None = None
        self.published_date_raw: str | None = None
        self._title_parts: list[str] = []
        self._in_title = False
        self._capture_depth = 0
        self._current_p_depth = 0
        self._paragraph_parts: list[str] = []
        self.paragraphs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "title":
            self._in_title = True
        if tag == "meta":
            self._capture_meta(attributes)
        class_tokens = set(str(attributes.get("class", "")).split())
        if class_tokens & SOURCE_CONTENT_CLASSES.get(self.source_slug, set()):
            self._capture_depth += 1
        if tag == "article":
            self._capture_depth += 1
        if tag == "p" and self._capture_depth > 0:
            self._current_p_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
            if self.title is None:
                self.title = _clean_text(" ".join(self._title_parts))
        if tag == "p" and self._current_p_depth > 0:
            paragraph = _sanitize_paragraph(self.source_slug, _clean_text(" ".join(self._paragraph_parts)))
            if paragraph:
                self.paragraphs.append(paragraph)
            self._paragraph_parts = []
            self._current_p_depth -= 1
        if tag == "article" and self._capture_depth > 0:
            self._capture_depth -= 1
        if tag == "div" and self._capture_depth > 0:
            self._capture_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._title_parts.append(data)
        if self._current_p_depth > 0:
            self._paragraph_parts.append(data)

    def _capture_meta(self, attributes: dict[str, str | None]) -> None:
        property_name = str(attributes.get("property") or attributes.get("name") or "").casefold()
        content = attributes.get("content")
        if content and property_name in META_PUBLISHED_NAMES and self.published_date_raw is None:
            self.published_date_raw = _clean_text(str(content))
        if content and property_name == "og:title" and self.title is None:
            self.title = _clean_text(str(content))


def parse_article_html(source: SourceDefinition, html: str, url: str) -> ParsedArticle:
    """Parse an article page using source-aware and fallback strategies."""

    parser = ArticleHTMLParser(source.slug)
    parser.feed(html)
    published_date_raw = parser.published_date_raw or _extract_published_date(source.slug, html, url)
    paragraphs = list(parser.paragraphs)
    source_paragraphs = _source_container_paragraphs(source.slug, html)
    if source_paragraphs:
        paragraphs = source_paragraphs
    if not paragraphs or _looks_like_parser_noise(paragraphs):
        fallback_paragraphs = _fallback_extract_paragraphs(source.slug, html)
        if fallback_paragraphs:
            paragraphs = fallback_paragraphs
    text = "\n\n".join(paragraphs).strip()
    return ParsedArticle(
        title=parser.title,
        published_date_raw=published_date_raw,
        text=text,
        parse_success=bool(text and parser.title),
    )


def _source_container_paragraphs(source_slug: str, html: str) -> list[str]:
    """Prefer the verified article container for sources with page-wide article tags."""

    selectors = {
        "ujyaalo": (".editor-box",),
        "nepalpress": (".news-content-area", ".news-post-content"),
        "nepalpress-en": (".news-content-area", ".news-post-content"),
    }
    if source_slug not in selectors:
        return []
    soup = BeautifulSoup(html, "html.parser")
    for selector in selectors[source_slug]:
        container = soup.select_one(selector)
        if container is None:
            continue
        paragraphs = [
            _sanitize_paragraph(
                source_slug, _clean_text(paragraph.get_text(" ", strip=True))
            )
            for paragraph in container.find_all("p")
        ]
        cleaned = [
            paragraph for paragraph in paragraphs if paragraph and not _is_noise_paragraph(paragraph)
        ]
        if cleaned:
            return cleaned
    return []


def _sanitize_paragraph(source_slug: str, paragraph: str) -> str:
    """Trim source-specific navigation noise from extracted paragraph text."""

    cleaned = paragraph.strip()
    if not cleaned:
        return ''
    if source_slug == 'ratopati':
        for marker in RATOPATI_NAV_MARKERS:
            if marker in cleaned:
                cleaned = cleaned.split(marker, 1)[0].strip()
        for marker in RATOPATI_FOOTER_MARKERS:
            if marker in cleaned:
                cleaned = cleaned.split(marker, 1)[0].strip()
        cleaned = re.sub(r"\s*\|\s*Nepal's first 24-hour updated news portal - Ratopati.*$", '', cleaned).strip()
    return cleaned


def _is_noise_paragraph(paragraph: str) -> bool:
    """Return True when a paragraph matches common JS/template junk signatures."""

    if len(paragraph) < 60:
        return False
    return any(marker in paragraph for marker in PARSE_NOISE_MARKERS)


def text_looks_like_parser_noise(text: str) -> bool:
    """Return True when stored article text still looks like parser noise."""

    normalized = _clean_text(text)
    if len(normalized) < 60:
        return False
    return any(marker in normalized for marker in PARSE_NOISE_MARKERS)


def _looks_like_parser_noise(paragraphs: list[str]) -> bool:
    """Return True when extracted paragraphs look like JS/template junk instead of article prose."""

    if not paragraphs:
        return False
    if any(_is_noise_paragraph(paragraph) for paragraph in paragraphs[:3]):
        return True
    joined = ' '.join(paragraphs[:3])
    return len(joined) >= 80 and _is_noise_paragraph(joined)


def _fallback_extract_paragraphs(source_slug: str, html: str) -> list[str]:
    """Fallback paragraph extraction that strips script/template noise first."""

    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style", "noscript", "template"]):
        node.decompose()
    paragraphs = [
        _sanitize_paragraph(source_slug, _clean_text(paragraph.get_text(" ", strip=True)))
        for paragraph in soup.find_all("p")
    ]
    return [paragraph for paragraph in paragraphs if paragraph and not _is_noise_paragraph(paragraph)]


def _clean_text(value: str) -> str:
    """Normalize whitespace and HTML entities."""

    return " ".join(unescape(value).split())


def _extract_published_date(source_slug: str, html: str, url: str) -> str | None:
    """Extract a publication date from common HTML patterns."""

    if source_slug in {"ujyaalo", "nepalpress", "nepalpress-en"}:
        source_date = _extract_source_visible_date(source_slug, html)
        if source_date:
            return source_date

    if source_slug == 'myrepublica':
        candidates = (
            _extract_json_ld_date(html),
            _extract_time_datetime(html),
            _extract_soup_date(source_slug, html),
            _extract_url_date(url),
            _extract_iso_date(html),
        )
    else:
        candidates = (
            _extract_time_datetime(html),
            _extract_json_ld_date(html),
            _extract_soup_date(source_slug, html),
            _extract_url_date(url),
        )
        if source_slug not in {'rising-nepal'}:
            candidates = candidates + (_extract_iso_date(html),)
    for candidate in candidates:
        if candidate:
            return candidate
    return None


def _extract_source_visible_date(source_slug: str, html: str) -> str | None:
    """Read publisher-visible dates before unrelated template or advert dates."""

    soup = BeautifulSoup(html, "html.parser")
    selectors = {
        "ujyaalo": (".published-box .date-line", ".published-box"),
        "nepalpress": (".news-detail-header .post-date", ".post-header .post-date", ".post-date"),
        "nepalpress-en": (".news-detail-header .post-date", ".post-header .post-date", ".post-date"),
    }
    for selector in selectors.get(source_slug, ()):
        for node in soup.select(selector):
            text = _clean_text(node.get_text(" ", strip=True))
            date_value = _date_from_visible_text(text)
            if date_value:
                return date_value
            has_bs_year = re.search(r"[०-९]{4}", text)
            has_bs_month = re.search(
                r"(?:बैशाख|वैशाख|जेठ|असार|साउन|भदौ|असोज|कात्तिक|कार्तिक|मंसिर|पुष|पुस|माघ|फागुन|चैत)",
                text,
            )
            if source_slug in {"ujyaalo", "nepalpress"} and has_bs_year and has_bs_month:
                return text
    return None


def _extract_time_datetime(html: str) -> str | None:
    """Extract a datetime value from a <time> tag."""

    match = TIME_DATETIME_PATTERN.search(html)
    if not match:
        return None
    return _normalize_date_candidate(match.group(1))


def _extract_json_ld_date(html: str) -> str | None:
    """Extract datePublished from JSON-LD or inline JSON snippets."""

    for script_match in re.finditer(
        r"<script[^>]*type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
        html,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        raw_json = script_match.group(1).strip()
        if not raw_json:
            continue
        date_value = _date_from_json_blob(raw_json)
        if date_value:
            return date_value
    inline_match = JSON_LD_DATE_PATTERN.search(html)
    if inline_match:
        return _normalize_date_candidate(inline_match.group(1))
    return None


def _date_from_json_blob(raw_json: str) -> str | None:
    """Find datePublished in a JSON or JSON array payload."""

    try:
        payload = json.loads(raw_json)
    except json.JSONDecodeError:
        match = JSON_LD_DATE_PATTERN.search(raw_json)
        return _normalize_date_candidate(match.group(1)) if match else None
    return _walk_for_date_published(payload)


def _walk_for_date_published(value: object) -> str | None:
    """Walk nested JSON objects and return the first datePublished value."""

    if isinstance(value, dict):
        for key in JSON_PUBLISH_KEY_CANDIDATES:
            date_value = value.get(key)
            if isinstance(date_value, str):
                normalized = _normalize_date_candidate(date_value)
                if normalized:
                    return normalized
        for nested_value in value.values():
            nested_date = _walk_for_date_published(nested_value)
            if nested_date:
                return nested_date
    if isinstance(value, list):
        for item in value:
            nested_date = _walk_for_date_published(item)
            if nested_date:
                return nested_date
    return None


def _extract_soup_date(source_slug: str, html: str) -> str | None:
    """Extract dates from source-specific visible publish blocks."""

    soup = BeautifulSoup(html, "html.parser")

    meta_value = _extract_meta_date_from_soup(soup)
    if meta_value:
        return meta_value

    if source_slug == "kathmandu-post":
        kathmandu_post_date = _extract_kathmandu_post_visible_date(soup)
        if kathmandu_post_date:
            return kathmandu_post_date

    if source_slug == "setopati":
        setopati_date = _extract_setopati_visible_date(soup)
        if setopati_date:
            return setopati_date

    if source_slug == "rising-nepal":
        rising_nepal_date = _extract_rising_nepal_visible_date(soup)
        return rising_nepal_date

    for node in soup.find_all(True):
        classes = " ".join(node.get("class", []))
        node_id = node.get("id") or ""
        marker = f"{classes} {node_id}".lower()
        if not any(token in marker for token in ("date", "time", "publish", "author", "meta")):
            continue
        text = _clean_text(node.get_text(" ", strip=True))
        date_value = _date_from_visible_text(text)
        if date_value:
            return date_value
    return None


def _extract_meta_date_from_soup(soup: BeautifulSoup) -> str | None:
    """Extract published dates from generic meta tags."""

    for meta in soup.find_all("meta"):
        key = str(meta.get("property") or meta.get("name") or "").casefold()
        content = meta.get("content")
        if not content:
            continue
        if any(token in key for token in ("publish", "datepublished", "article:published", "time")):
            normalized = _normalize_date_candidate(str(content))
            if normalized and _looks_like_date(normalized):
                return normalized
    return None


def _extract_kathmandu_post_visible_date(soup: BeautifulSoup) -> str | None:
    """Extract Kathmandu Post's visible published-date block."""

    for node in soup.select('.updated-time'):
        text = _clean_text(node.get_text(' ', strip=True))
        if 'Published at' not in text:
            continue
        date_value = _date_from_visible_text(text)
        if date_value:
            return date_value
    return None


def _extract_setopati_visible_date(soup: BeautifulSoup) -> str | None:
    """Extract Setopati's visible BS publish block."""

    for node in soup.select(".published-date .pub-date, .published-date"):
        text = _clean_text(node.get_text(" ", strip=True))
        match = SETOPATI_BS_PATTERN.search(text)
        if not match:
            continue
        date_text = _clean_text(match.group(1))
        time_text = _clean_text(match.group(2) or "")
        return f"{date_text} {time_text}".strip()
    return None


def _extract_rising_nepal_visible_date(soup: BeautifulSoup) -> str | None:
    """Extract Rising Nepal's visible publish block when meta tags are missing."""

    selectors = (
        'time',
        '.jeg_meta_date',
        '.meta-date',
        '.post-date',
        '.entry-date',
        '.jeg_meta_container',
        '.jeg_post_meta',
    )
    for selector in selectors:
        for node in soup.select(selector):
            text = _clean_text(node.get_text(' ', strip=True))
            date_value = _date_from_visible_text(text)
            if date_value:
                return date_value
    return None


def _date_from_visible_text(text: str) -> str | None:
    """Extract a plausible date string from human-visible header text."""

    generic_match = GENERIC_DATE_TEXT_PATTERN.search(text)
    if generic_match:
        return _normalize_date_candidate(generic_match.group(1))
    iso_match = DATE_PATTERN.search(text)
    if iso_match:
        return _normalize_date_candidate(iso_match.group(0))
    month_match = MONTH_NAME_DATE_PATTERN.search(text)
    if month_match:
        return _normalize_date_candidate(month_match.group(0))
    month_day_year_match = MONTH_DAY_YEAR_PATTERN.search(text)
    if month_day_year_match:
        return _normalize_date_candidate(month_day_year_match.group(0))
    return None


def _extract_url_date(url: str) -> str | None:
    """Extract a YYYY-MM-DD date from common article URL patterns."""

    match = URL_DATE_PATTERN.search(url)
    if not match:
        return None
    return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"


def _extract_iso_date(html: str) -> str | None:
    """Fallback to any plausible ISO-like date string in the HTML."""

    match = DATE_PATTERN.search(html)
    if not match:
        return None
    return _normalize_date_candidate(match.group(0))


def _looks_like_date(value: str) -> bool:
    """Return True when a string looks like a publish date."""

    return bool(DATE_PATTERN.search(value) or re.search(r"[०-९]{4}", value))


def _normalize_date_candidate(value: str) -> str | None:
    """Normalize a date candidate and reject empty values."""

    cleaned = _clean_text(value)
    return cleaned or None
