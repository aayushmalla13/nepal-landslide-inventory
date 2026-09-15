"""Listing and source-native discovery helpers."""

from __future__ import annotations

import http.cookiejar
import json
import logging
import re
import socket
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, quote_plus, urlencode, urlparse, urlunparse

from ..config import AppConfig
from ..sources import SourceDefinition, allowed_domains
from .models import DiscoveredUrl
from .url_tools import filter_article_url, normalize_url

LOGGER = logging.getLogger(__name__)
YEAR_PATTERN = re.compile(r"\b(20\d{2})\b")
SITEMAP_NAMESPACE = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
NEWS_NAMESPACE = {
    "sm": "http://www.sitemaps.org/schemas/sitemap/0.9",
    "news": "http://www.google.com/schemas/sitemap-news/0.9",
}
RISING_TOKEN_PATTERN = re.compile(r'name="_token" value="([^"]+)"')


@dataclass(frozen=True)
class ListingParseResult:
    """URLs and next-page metadata extracted from a listing page."""

    urls: list[str]
    next_url: str | None
    year_hints: list[int]
    next_method: str


@dataclass(frozen=True)
class ListingLink:
    """Normalized anchor metadata extracted from a listing page."""

    href: str
    text: str
    rel: str
    in_article: bool


@dataclass(frozen=True)
class SitemapArticle:
    """An article row extracted from a sitemap."""

    url: str
    title: str
    year: int | None


class ListingHTMLParser(HTMLParser):
    """Minimal HTML parser for listing pages."""

    def __init__(self, current_url: str, mode: str) -> None:
        super().__init__()
        self.current_url = current_url
        self.mode = mode
        self.links: list[ListingLink] = []
        self.year_hints: list[int] = []
        self._current_href: str | None = None
        self._link_text_parts: list[str] = []
        self._current_rel: str = ""
        self._current_in_article = False
        self._article_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "article":
            self._article_depth += 1
        if tag == "a" and attributes.get("href"):
            self._current_href = str(attributes["href"])
            # Search-result cards often put the headline in ``title`` or
            # ``aria-label`` while the anchor itself only contains an image.
            # Keeping that text lets opaque article URLs be filtered by the
            # requested keyword without fetching every navigation link.
            accessible_text = attributes.get("title") or attributes.get("aria-label")
            self._link_text_parts = [str(accessible_text)] if accessible_text else []
            self._current_rel = str(attributes.get("rel") or "")
            self._current_in_article = self._article_depth > 0

    def handle_data(self, data: str) -> None:
        if self._current_href is not None:
            self._link_text_parts.append(data)
        for match in YEAR_PATTERN.findall(data):
            self.year_hints.append(int(match))

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._current_href is not None:
            text = " ".join(part.strip() for part in self._link_text_parts if part.strip())
            self.links.append(
                ListingLink(
                    href=self._current_href,
                    text=text.casefold(),
                    rel=self._current_rel.casefold(),
                    in_article=self._current_in_article,
                )
            )
            self._current_href = None
            self._link_text_parts = []
            self._current_rel = ""
            self._current_in_article = False
        if tag == "article" and self._article_depth > 0:
            self._article_depth -= 1


def parse_listing_page(
    html: str,
    source: SourceDefinition,
    entry_point: dict[str, str],
    current_url: str,
) -> ListingParseResult:
    """Parse a listing page into article URLs and optional next-page URL."""

    parser = ListingHTMLParser(current_url=current_url, mode=str(entry_point["pagination"]))
    parser.feed(html)
    filtered_urls: list[str] = []
    seen = set()
    domains = allowed_domains(source)
    for link in parser.links:
        normalized = filter_article_url(link.href, domains, base_url=current_url)
        if normalized is None or normalized in seen:
            continue
        seen.add(normalized)
        filtered_urls.append(normalized)
    next_url, next_method = _detect_next_url(parser.links, entry_point, current_url)
    return ListingParseResult(
        urls=filtered_urls,
        next_url=next_url,
        year_hints=sorted(set(parser.year_hints)),
        next_method=next_method,
    )


def parse_keyword_search_page(
    html: str,
    source: SourceDefinition,
    current_url: str,
    query_term: str,
) -> ListingParseResult:
    """Parse only result links whose anchor headline contains the search term.

    Rajdhani and Deshsanchar use opaque numeric article URLs. URL-keyword
    filtering therefore returns nothing, while accepting every article-shaped
    link pulls in menus, tickers, and unrelated homepage cards. Search-result
    cards are structural ``article`` elements, including full-text matches whose
    headlines do not repeat the term. If that structure is absent, headline
    matching remains a conservative fallback.
    """

    entry_point = {"kind": "search_archive", "url": current_url, "pagination": "next_link"}
    parser = ListingHTMLParser(current_url=current_url, mode="next_link")
    parser.feed(html)
    domains = allowed_domains(source)
    needle = query_term.casefold()
    urls: list[str] = []
    seen: set[str] = set()
    article_links = [link for link in parser.links if link.in_article]
    candidate_links = article_links or [link for link in parser.links if needle in link.text]
    for link in candidate_links:
        normalized = filter_article_url(link.href, domains, base_url=current_url)
        if normalized is None or normalized in seen:
            continue
        seen.add(normalized)
        urls.append(normalized)
    next_url, next_method = _detect_next_url(parser.links, entry_point, current_url)
    return ListingParseResult(
        urls=urls,
        next_url=next_url,
        year_hints=sorted(set(parser.year_hints)),
        next_method=next_method,
    )


def build_google_news_queries(config: AppConfig, source: SourceDefinition) -> list[str]:
    """Build deterministic Google News queries for a source."""

    terms = list(config.raw["keywords"]["terms"][source.language])
    domain = urlparse(source.base_url).netloc
    return [f"{term} site:{domain}" for term in terms]


def build_google_news_discoveries(
    config: AppConfig,
    source: SourceDefinition,
) -> list[DiscoveredUrl]:
    """Create discovery records for Google News queries."""

    discoveries: list[DiscoveredUrl] = []
    for query in build_google_news_queries(config, source):
        url = f"https://news.google.com/rss/search?q={query.replace(' ', '+')}"
        discoveries.append(
            DiscoveredUrl(
                url=url,
                source=source.slug,
                method="googlenews",
                entry_point=url,
                query_term=query,
            )
        )
    return discoveries


def source_native_discovery_mode(source: SourceDefinition) -> str | None:
    """Return the source-specific supplemental discovery mode, if any."""

    configured = source.discovery.get("native_mode")
    if configured:
        return str(configured)

    modes = {
        "myrepublica": "sitemap_news",
        "setopati": "search",
        "himalayan-times": "sitemap_plain",
        "ratopati": "search",
        "rising-nepal": "search_post",
    }
    return modes.get(source.slug)


def build_source_native_discoveries(
    config: AppConfig,
    source: SourceDefinition,
    fetcher,
    seen_urls: set[str],
    max_pages: int,
    max_urls: int,
) -> list[DiscoveredUrl]:
    """Build source-native supplemental discoveries for sources with weak tag coverage."""

    mode = source_native_discovery_mode(source)
    if mode == "sitemap_news":
        return discover_myrepublica_sitemaps(config, source, fetcher, seen_urls, max_urls)
    if mode == "sitemap_plain":
        return discover_himalayan_times_sitemaps(config, source, fetcher, seen_urls, max_urls)
    if mode == "search":
        if source.slug == "setopati":
            return discover_setopati_search(config, source, fetcher, seen_urls, max_pages, max_urls)
        if source.slug == "ratopati":
            return discover_ratopati_search(config, source, fetcher, seen_urls, max_pages, max_urls)
    if mode == "search_post":
        return discover_rising_nepal_search(config, source, fetcher, seen_urls, max_pages, max_urls)
    if mode == "wordpress_search":
        return discover_wordpress_search(config, source, fetcher, seen_urls, max_pages, max_urls)
    if mode == "nagarik_year_search":
        return discover_nagarik_year_search(config, source, fetcher, seen_urls, max_pages, max_urls)
    if mode == "wordpress_rest_search":
        return discover_wordpress_rest_search(
            config, source, fetcher, seen_urls, max_pages, max_urls
        )
    if mode == "ujyaalo_search":
        return discover_ujyaalo_search(
            config, source, fetcher, seen_urls, max_pages, max_urls
        )
    if mode == "sitemap_keyword_urls":
        return discover_sitemap_keyword_urls(config, source, fetcher, seen_urls, max_urls)
    return []


def configured_search_terms(config: AppConfig, source: SourceDefinition) -> list[str]:
    """Return a source-specific bounded term list or the project defaults."""

    configured = source.discovery.get("query_terms")
    if isinstance(configured, list) and configured:
        return [str(term) for term in configured]
    return [str(term) for term in config.raw["keywords"]["terms"][source.language]]


def build_wordpress_search_urls(config: AppConfig, source: SourceDefinition) -> list[tuple[str, str]]:
    """Build WordPress pretty-permalink search URLs for opaque-URL outlets."""

    base = source.base_url.rstrip("/")
    return [
        (term, f"{base}/search/{quote(term, safe='')}/page/1/")
        for term in configured_search_terms(config, source)
    ]


def discover_wordpress_search(
    config: AppConfig,
    source: SourceDefinition,
    fetcher,
    seen_urls: set[str],
    max_pages: int,
    max_urls: int,
) -> list[DiscoveredUrl]:
    """Walk WordPress search results and retain headline-matched articles."""

    if str(source.discovery.get("order", "newest_first")) == "oldest_first":
        return discover_wordpress_search_oldest_first(
            config, source, fetcher, seen_urls, max_pages, max_urls
        )

    discoveries: list[DiscoveredUrl] = []
    pages_used = 0
    for query_term, search_url in build_wordpress_search_urls(config, source):
        current_url: str | None = search_url
        consecutive_empty_pages = 0
        while current_url and pages_used < max_pages and len(discoveries) < max_urls:
            pages_used += 1
            fetch_result = fetcher.fetch(current_url)
            listing = parse_keyword_search_page(fetch_result.text, source, current_url, query_term)
            page_new_urls = 0
            for url in listing.urls:
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                discoveries.append(
                    DiscoveredUrl(
                        url=url,
                        source=source.slug,
                        method="search_archive",
                        entry_point=search_url,
                        query_term=query_term,
                        year_hint=_year_from_url(url),
                    )
                )
                page_new_urls += 1
                if len(discoveries) >= max_urls:
                    break
            consecutive_empty_pages = consecutive_empty_pages + 1 if page_new_urls == 0 else 0
            LOGGER.info(
                "Supplemental discovery page source=%s method=search_archive query=%s page=%s current_url=%s urls_found=%s new_urls_added=%s next_method=%s",
                source.slug,
                query_term,
                pages_used,
                current_url,
                len(listing.urls),
                page_new_urls,
                listing.next_method,
            )
            if consecutive_empty_pages >= 3:
                break
            current_url = listing.next_url
    return discoveries


def discover_wordpress_search_oldest_first(
    config: AppConfig,
    source: SourceDefinition,
    fetcher,
    seen_urls: set[str],
    max_pages: int,
    max_urls: int,
) -> list[DiscoveredUrl]:
    """Walk WordPress search from the final page to prioritize old coverage."""

    discoveries: list[DiscoveredUrl] = []
    pages_used = 0
    for query_term, search_url in build_wordpress_search_urls(config, source):
        first_result = fetcher.fetch(search_url)
        pages_used += 1
        last_page = _wordpress_last_page(first_result.text, search_url)
        consecutive_empty_pages = 0
        for page_number in range(last_page, 0, -1):
            if len(discoveries) >= max_urls:
                break
            current_url = _wordpress_page_url(search_url, page_number)
            if page_number == 1:
                fetch_result = first_result
            else:
                if pages_used >= max_pages:
                    break
                fetch_result = fetcher.fetch(current_url)
                pages_used += 1
            listing = parse_keyword_search_page(fetch_result.text, source, current_url, query_term)
            page_new_urls = 0
            for url in listing.urls:
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                discoveries.append(
                    DiscoveredUrl(
                        url=url,
                        source=source.slug,
                        method="search_archive",
                        entry_point=search_url,
                        query_term=query_term,
                        year_hint=_year_from_url(url),
                    )
                )
                page_new_urls += 1
                if len(discoveries) >= max_urls:
                    break
            consecutive_empty_pages = consecutive_empty_pages + 1 if page_new_urls == 0 else 0
            LOGGER.info(
                "Supplemental discovery page source=%s method=search_archive_oldest query=%s page=%s/%s urls_found=%s new_urls_added=%s",
                source.slug,
                query_term,
                page_number,
                last_page,
                len(listing.urls),
                page_new_urls,
            )
            if consecutive_empty_pages >= 3:
                break
    return discoveries


def _wordpress_last_page(html: str, current_url: str) -> int:
    """Read the largest numbered WordPress search page link."""

    parser = ListingHTMLParser(current_url=current_url, mode="next_link")
    parser.feed(html)
    page_numbers = [
        page
        for link in parser.links
        if (page := _extract_page_number(normalize_url(link.href, base_url=current_url))) is not None
    ]
    return max(page_numbers, default=1)


def _wordpress_page_url(search_url: str, page_number: int) -> str:
    """Replace the page component in a WordPress pretty search URL."""

    return re.sub(r"/page/\d+/?$", f"/page/{page_number}/", search_url)


def build_nagarik_search_url(
    source: SourceDefinition,
    query_term: str,
    year: int,
    offset: int = 0,
) -> str:
    """Build Nagarik's public year-filtered search URL."""

    params: list[tuple[str, str | int]] = [
        ("s", query_term),
        ("ayear", year),
        ("arch_dates", year),
        ("isfl", "true"),
        ("dfrom", f"{year}-01-01"),
        ("dto", f"{year}-12-31"),
    ]
    if offset:
        params.append(("offset", offset))
    return f"{source.base_url.rstrip('/')}/search?{urlencode(params)}"


def discover_nagarik_year_search(
    config: AppConfig,
    source: SourceDefinition,
    fetcher,
    seen_urls: set[str],
    max_pages: int,
    max_urls: int,
) -> list[DiscoveredUrl]:
    """Collect Nagarik search results year by year, oldest first."""

    study_start, study_end = config.study_period
    start_year = int(source.discovery.get("start_year", study_start))
    end_year = int(source.discovery.get("end_year", study_end))
    discoveries: list[DiscoveredUrl] = []
    pages_used = 0
    for year in range(start_year, end_year + 1):
        for query_term in configured_search_terms(config, source):
            offset = 0
            entry_point = build_nagarik_search_url(source, query_term, year)
            while pages_used < max_pages and len(discoveries) < max_urls:
                current_url = build_nagarik_search_url(source, query_term, year, offset)
                pages_used += 1
                fetch_result = fetcher.fetch(current_url)
                listing = parse_keyword_search_page(fetch_result.text, source, current_url, query_term)
                page_new_urls = 0
                for url in listing.urls:
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)
                    discoveries.append(
                        DiscoveredUrl(
                            url=url,
                            source=source.slug,
                            method="year_search",
                            entry_point=entry_point,
                            query_term=query_term,
                            year_hint=year,
                        )
                    )
                    page_new_urls += 1
                    if len(discoveries) >= max_urls:
                        break
                has_next, next_offset = _nagarik_next_page(fetch_result.text)
                LOGGER.info(
                    "Supplemental discovery page source=%s method=year_search query=%s year=%s offset=%s urls_found=%s new_urls_added=%s has_next=%s",
                    source.slug,
                    query_term,
                    year,
                    offset,
                    len(listing.urls),
                    page_new_urls,
                    has_next,
                )
                if not has_next or next_offset <= offset:
                    break
                offset = next_offset
            if pages_used >= max_pages or len(discoveries) >= max_urls:
                break
        if pages_used >= max_pages or len(discoveries) >= max_urls:
            break
    return discoveries


def discover_wordpress_rest_search(
    config: AppConfig,
    source: SourceDefinition,
    fetcher,
    seen_urls: set[str],
    max_pages: int,
    max_urls: int,
) -> list[DiscoveredUrl]:
    """Discover a WordPress site's keyword-search results through its public API."""

    endpoint = str(
        source.discovery.get(
            "api_endpoint", f"{source.base_url.rstrip('/')}/wp-json/wp/v2/posts"
        )
    )
    per_page = min(100, max(1, int(source.discovery.get("api_per_page", 100))))
    discoveries: list[DiscoveredUrl] = []
    pages_used = 0
    domains = allowed_domains(source)
    allow_single_segment = bool(source.discovery.get("allow_single_segment_urls", False))
    search_columns = source.discovery.get("api_search_columns", [])
    if not isinstance(search_columns, list):
        search_columns = [search_columns]
    for query_term in configured_search_terms(config, source):
        page = 1
        while pages_used < max_pages and len(discoveries) < max_urls:
            query_items: list[tuple[str, object]] = [
                ("search", query_term),
                ("per_page", per_page),
                ("page", page),
            ]
            query_items.extend(
                ("search_columns[]", str(column))
                for column in search_columns
                if str(column).strip()
            )
            query = urlencode(query_items)
            current_url = f"{endpoint}?{query}"
            result = fetcher.fetch(current_url)
            try:
                rows = json.loads(result.text)
            except json.JSONDecodeError:
                LOGGER.warning("WordPress API response is not JSON: %s", current_url)
                break
            if not isinstance(rows, list) or not rows:
                break
            pages_used += 1
            added = 0
            for row in rows:
                if not isinstance(row, dict):
                    continue
                link = row.get("link")
                if not isinstance(link, str):
                    continue
                normalized = filter_article_url(
                    link, domains, allow_single_segment=allow_single_segment
                )
                if normalized is None or normalized in seen_urls:
                    continue
                seen_urls.add(normalized)
                date_text = str(row.get("date") or "")
                year = int(date_text[:4]) if date_text[:4].isdigit() else None
                discoveries.append(
                    DiscoveredUrl(
                        url=normalized,
                        source=source.slug,
                        method="wordpress_rest_search",
                        entry_point=endpoint,
                        query_term=query_term,
                        year_hint=year,
                    )
                )
                added += 1
                if len(discoveries) >= max_urls:
                    break
            LOGGER.info(
                "Supplemental discovery page source=%s method=wordpress_rest_search "
                "query=%s page=%s rows=%s new_urls_added=%s",
                source.slug, query_term, page, len(rows), added,
            )
            if len(rows) < per_page:
                break
            page += 1
    return discoveries


def discover_ujyaalo_search(
    config: AppConfig,
    source: SourceDefinition,
    fetcher,
    seen_urls: set[str],
    max_pages: int,
    max_urls: int,
) -> list[DiscoveredUrl]:
    """Walk Ujyaalo's native keyword search with numbered pagination."""

    search_urls = [
        (
            term,
            f"{source.base_url.rstrip('/')}/search?{urlencode({'keyword': term})}",
        )
        for term in configured_search_terms(config, source)
    ]
    return discover_paginated_search(
        config,
        source,
        fetcher,
        seen_urls,
        max_pages,
        max_urls,
        search_urls=search_urls,
        method="ujyaalo_search",
    )


def discover_sitemap_keyword_urls(
    config: AppConfig,
    source: SourceDefinition,
    fetcher,
    seen_urls: set[str],
    max_urls: int,
) -> list[DiscoveredUrl]:
    """Discover keyword-bearing URLs from a configured plain sitemap.

    Some historical sites expose a complete sitemap but no usable server-side
    search. Their ``lastmod`` is often an edit date, not publication date, so
    it is deliberately not used to filter the study period; article parsing
    extracts the publisher date after the bounded candidate set is fetched.
    """

    index_url = str(source.discovery.get("sitemap_url", f"{source.base_url.rstrip('/')}/sitemap.xml"))
    index_result = fetcher.fetch(index_url)
    if index_result.status_code != 200:
        LOGGER.warning("Sitemap %s returned HTTP %s; skipping", index_url, index_result.status_code)
        return []
    sitemap_urls = (
        parse_sitemap_index(index_result.text)
        if "sitemapindex" in index_result.text[:1000].casefold()
        else []
    )
    if not sitemap_urls:
        sitemap_urls = [index_url]
    include_pattern = str(source.discovery.get("sitemap_include", ""))
    if include_pattern:
        matcher = re.compile(include_pattern)
        sitemap_urls = [url for url in sitemap_urls if matcher.search(url)]
    discoveries: list[DiscoveredUrl] = []
    domains = allowed_domains(source)
    include_terms = list(config.raw["keywords"]["terms"][source.language])
    exclude_terms = list(config.raw["keywords"]["exclude"][source.language])
    allow_single_segment = bool(source.discovery.get("allow_single_segment_urls", False))
    for sitemap_url in sitemap_urls:
        if len(discoveries) >= max_urls:
            break
        result = fetcher.fetch(sitemap_url)
        if result.status_code != 200:
            LOGGER.warning("Sitemap %s returned HTTP %s; skipping", sitemap_url, result.status_code)
            continue
        try:
            articles = parse_plain_sitemap(result.text)
        except ET.ParseError:
            LOGGER.warning("Sitemap %s is not a readable URL set; skipping", sitemap_url)
            continue
        added = 0
        for article in articles:
            if len(discoveries) >= max_urls:
                break
            if not keyword_match(article.url, include_terms, exclude_terms):
                continue
            normalized = filter_article_url(
                article.url,
                domains,
                allow_single_segment=allow_single_segment,
            )
            if normalized is None or normalized in seen_urls:
                continue
            seen_urls.add(normalized)
            discoveries.append(
                DiscoveredUrl(
                    url=normalized,
                    source=source.slug,
                    method="sitemap_keyword_urls",
                    entry_point=index_url,
                    year_hint=_year_from_url(normalized),
                )
            )
            added += 1
        LOGGER.info(
            "Supplemental discovery source=%s method=sitemap_keyword_urls "
            "sitemap=%s new_urls_added=%s",
            source.slug, sitemap_url, added,
        )
    return discoveries


def _nagarik_next_page(html: str) -> tuple[bool, int]:
    """Return Nagarik's load-more flag and next offset from a result page."""

    tag_match = re.search(r"<a\b[^>]*\bid=[\"']loadmore[\"'][^>]*>", html, flags=re.IGNORECASE)
    if tag_match is None:
        return False, 0
    tag = tag_match.group(0)
    next_match = re.search(r"\bdata-next=[\"']?([01])", tag, flags=re.IGNORECASE)
    offset_match = re.search(r"\bdata-offset=[\"']?(\d+)", tag, flags=re.IGNORECASE)
    if next_match is None or next_match.group(1) != "1" or offset_match is None:
        return False, 0
    return True, int(offset_match.group(1))


def _year_from_url(url: str) -> int | None:
    match = re.search(r"/(20\d{2})/", urlparse(url).path)
    if match is None:
        return None
    year = int(match.group(1))
    return year if 2015 <= year <= 2026 else None


def build_setopati_search_urls(config: AppConfig, source: SourceDefinition) -> list[tuple[str, str]]:
    """Build deterministic search entry points for Setopati."""

    return _build_search_urls(config, source, template="{base}/search?keyword={term}")


def build_ratopati_search_urls(config: AppConfig, source: SourceDefinition) -> list[tuple[str, str]]:
    """Build deterministic search entry points for Ratopati."""

    return _build_search_urls(config, source, template="{base}/search?keyword={term}&page=1")


def discover_setopati_search(
    config: AppConfig,
    source: SourceDefinition,
    fetcher,
    seen_urls: set[str],
    max_pages: int,
    max_urls: int,
) -> list[DiscoveredUrl]:
    """Supplement Setopati discovery using its paginated search endpoint."""

    return discover_paginated_search(
        config,
        source,
        fetcher,
        seen_urls,
        max_pages,
        max_urls,
        search_urls=build_setopati_search_urls(config, source),
        method="search",
    )


def discover_ratopati_search(
    config: AppConfig,
    source: SourceDefinition,
    fetcher,
    seen_urls: set[str],
    max_pages: int,
    max_urls: int,
) -> list[DiscoveredUrl]:
    """Supplement Ratopati discovery using its search endpoint."""

    return discover_paginated_search(
        config,
        source,
        fetcher,
        seen_urls,
        max_pages,
        max_urls,
        search_urls=build_ratopati_search_urls(config, source),
        method="search",
    )


def discover_paginated_search(
    config: AppConfig,
    source: SourceDefinition,
    fetcher,
    seen_urls: set[str],
    max_pages: int,
    max_urls: int,
    search_urls: list[tuple[str, str]],
    method: str,
) -> list[DiscoveredUrl]:
    """Run paginated GET-based search discovery for a source."""

    discoveries: list[DiscoveredUrl] = []
    for query_term, search_url in search_urls:
        current_url = search_url
        page_number = 1
        previous_page_urls: list[str] = []
        consecutive_empty_pages = 0
        entry_point = {"kind": "search", "url": search_url, "pagination": "next_link"}
        while current_url and len(discoveries) < max_urls:
            fetch_result = fetcher.fetch(current_url)
            listing = parse_listing_page(fetch_result.text, source, entry_point, current_url)
            page_new_urls = 0
            for url in listing.urls:
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                discoveries.append(
                    DiscoveredUrl(
                        url=url,
                        source=source.slug,
                        method=method,
                        entry_point=search_url,
                        query_term=query_term,
                        year_hint=best_year_hint(listing.year_hints),
                    )
                )
                page_new_urls += 1
                if len(discoveries) >= max_urls:
                    break
            repeated = repeated_top_urls(previous_page_urls, listing.urls)
            consecutive_empty_pages = consecutive_empty_pages + 1 if page_new_urls == 0 else 0
            LOGGER.info(
                "Supplemental discovery page source=%s method=%s query=%s page=%s current_url=%s urls_found=%s new_urls_added=%s next_method=%s",
                source.slug,
                method,
                query_term,
                page_number,
                current_url,
                len(listing.urls),
                page_new_urls,
                listing.next_method,
            )
            if should_stop_pagination(
                page_number=page_number,
                max_pages=max_pages,
                consecutive_empty_pages=consecutive_empty_pages,
                repeated_top_urls=repeated,
            ):
                break
            previous_page_urls = list(listing.urls)
            current_url = listing.next_url
            page_number += 1
    return discoveries


def discover_rising_nepal_search(
    config: AppConfig,
    source: SourceDefinition,
    fetcher,
    seen_urls: set[str],
    max_pages: int,
    max_urls: int,
) -> list[DiscoveredUrl]:
    """Supplement Rising Nepal discovery using its CSRF-protected search form."""

    discoveries: list[DiscoveredUrl] = []
    search_url = f"{source.base_url.rstrip('/')}/news-search"
    start_date = str(config.raw["study_period"]["start"])
    end_date = str(config.raw["study_period"]["end"])
    for query_term in list(config.raw["keywords"]["terms"][source.language]):
        opener, html = open_rising_nepal_search(fetcher, search_url, query_term, start_date, end_date)
        current_url = search_url
        page_number = 1
        previous_page_urls: list[str] = []
        consecutive_empty_pages = 0
        entry_point = {"kind": "search_post", "url": search_url, "pagination": "next_link"}
        while html and len(discoveries) < max_urls:
            listing = parse_listing_page(html, source, entry_point, current_url)
            page_new_urls = 0
            for url in listing.urls:
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                discoveries.append(
                    DiscoveredUrl(
                        url=url,
                        source=source.slug,
                        method="search_post",
                        entry_point=search_url,
                        query_term=query_term,
                        year_hint=best_year_hint(listing.year_hints),
                    )
                )
                page_new_urls += 1
                if len(discoveries) >= max_urls:
                    break
            repeated = repeated_top_urls(previous_page_urls, listing.urls)
            consecutive_empty_pages = consecutive_empty_pages + 1 if page_new_urls == 0 else 0
            LOGGER.info(
                "Supplemental discovery page source=%s method=search_post query=%s page=%s current_url=%s urls_found=%s new_urls_added=%s next_method=%s",
                source.slug,
                query_term,
                page_number,
                current_url,
                len(listing.urls),
                page_new_urls,
                listing.next_method,
            )
            if should_stop_pagination(
                page_number=page_number,
                max_pages=max_pages,
                consecutive_empty_pages=consecutive_empty_pages,
                repeated_top_urls=repeated,
            ):
                break
            previous_page_urls = list(listing.urls)
            current_url = listing.next_url
            page_number += 1
            if current_url is None:
                break
            html = fetch_with_opener(fetcher, opener, current_url)
    return discoveries


def open_rising_nepal_search(
    fetcher,
    search_url: str,
    query_term: str,
    start_date: str,
    end_date: str,
) -> tuple[urllib.request.OpenerDirector, str]:
    """Submit the Rising Nepal search form and return a session opener plus HTML."""

    cookie_jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))
    search_html = fetch_with_opener(fetcher, opener, search_url)
    token_match = RISING_TOKEN_PATTERN.search(search_html)
    if token_match is None:
        raise RuntimeError("Could not locate Rising Nepal search CSRF token.")
    payload = urllib.parse.urlencode(
        {
            "_token": token_match.group(1),
            "keywords": query_term,
            "from": start_date,
            "to": end_date,
        }
    ).encode()
    html = fetch_with_opener(
        fetcher,
        opener,
        search_url,
        data=payload,
        extra_headers={"Content-Type": "application/x-www-form-urlencoded", "Referer": search_url},
    )
    return opener, html


def fetch_with_opener(
    fetcher,
    opener: urllib.request.OpenerDirector,
    url: str,
    data: bytes | None = None,
    extra_headers: dict[str, str] | None = None,
) -> str:
    """Fetch a URL through a cookie-aware opener with retry and rate limiting."""

    last_error: Exception | None = None
    headers = {"User-Agent": fetcher.user_agent}
    if extra_headers:
        headers.update(extra_headers)
    for attempt in range(fetcher.retries + 1):
        fetcher._respect_rate_limit()
        request = urllib.request.Request(url, data=data, headers=headers)
        try:
            with opener.open(request, timeout=fetcher.timeout_seconds) as response:
                return response.read().decode("utf-8", errors="replace")
        except HTTPError as exc:
            if exc.code < 500 and exc.code not in {408, 429}:
                raise
            last_error = exc
            LOGGER.warning("Fetch attempt %s failed for %s: %s", attempt + 1, url, exc)
            time.sleep(2**attempt)
        except (TimeoutError, socket.timeout, URLError) as exc:
            last_error = exc
            LOGGER.warning("Fetch attempt %s failed for %s: %s", attempt + 1, url, exc)
            time.sleep(2**attempt)
    raise RuntimeError(f"Failed to fetch {url}: {last_error}")


def discover_myrepublica_sitemaps(
    config: AppConfig,
    source: SourceDefinition,
    fetcher,
    seen_urls: set[str],
    max_urls: int,
) -> list[DiscoveredUrl]:
    """Supplement MyRepublica discovery from its sitemap index."""

    index_url = f"{source.base_url.rstrip('/')}/sitemap.xml"
    include_terms = list(config.raw["keywords"]["terms"][source.language])
    exclude_terms = list(config.raw["keywords"]["exclude"][source.language])
    index_result = fetcher.fetch(index_url)
    if index_result.status_code != 200:
        # Non-200 bodies are error pages, not sitemaps. Parsing one wastes time
        # and produces a confusing XML error far from the real cause.
        LOGGER.warning('Sitemap index %s returned HTTP %s; skipping sitemap discovery',
                       index_url, index_result.status_code)
        return []
    sitemap_urls = ordered_myrepublica_sitemaps(parse_sitemap_index(index_result.text))
    discoveries: list[DiscoveredUrl] = []
    domains = allowed_domains(source)
    start_year, end_year = config.study_period

    for sitemap_url in sitemap_urls:
        if len(discoveries) >= max_urls:
            break
        sitemap_result = fetcher.fetch(sitemap_url)
        if sitemap_result.status_code != 200:
            LOGGER.warning('Sitemap %s returned HTTP %s; skipping it',
                           sitemap_url, sitemap_result.status_code)
            continue
        sitemap_text = sitemap_result.text
        added_from_sitemap = 0
        for article in parse_news_sitemap(sitemap_text):
            if len(discoveries) >= max_urls:
                break
            if article.year is None or not (start_year <= article.year <= end_year):
                continue
            if not keyword_match(f"{article.title} {article.url}", include_terms, exclude_terms):
                continue
            normalized = filter_article_url(article.url, domains)
            if normalized is None or normalized in seen_urls:
                continue
            seen_urls.add(normalized)
            discoveries.append(
                DiscoveredUrl(
                    url=normalized,
                    source=source.slug,
                    method="sitemap",
                    entry_point=index_url,
                    query_term=None,
                    year_hint=article.year,
                )
            )
            added_from_sitemap += 1
        LOGGER.info(
            "Supplemental discovery source=%s method=sitemap sitemap=%s new_urls_added=%s",
            source.slug,
            sitemap_url,
            added_from_sitemap,
        )
    return discoveries


def discover_himalayan_times_sitemaps(
    config: AppConfig,
    source: SourceDefinition,
    fetcher,
    seen_urls: set[str],
    max_urls: int,
) -> list[DiscoveredUrl]:
    """Supplement The Himalayan Times discovery from its sitemap index."""

    index_url = f"{source.base_url.rstrip('/')}/sitemaps/sitemap_0.xml"
    include_terms = list(config.raw["keywords"]["terms"][source.language])
    exclude_terms = list(config.raw["keywords"]["exclude"][source.language])
    domains = allowed_domains(source)
    start_year, end_year = config.study_period
    sitemap_index = fetcher.fetch(index_url).text
    sitemap_urls = [
        url
        for url in parse_sitemap_index(sitemap_index)
        if shard_year(url) is not None and start_year <= shard_year(url) <= end_year
    ]
    discoveries: list[DiscoveredUrl] = []

    for sitemap_url in sitemap_urls:
        if len(discoveries) >= max_urls:
            break
        sitemap_text = fetcher.fetch(sitemap_url).text
        added_from_sitemap = 0
        for article in parse_plain_sitemap(sitemap_text):
            if len(discoveries) >= max_urls:
                break
            if article.year is None or not (start_year <= article.year <= end_year):
                continue
            if not keyword_match(article.url, include_terms, exclude_terms):
                continue
            normalized = filter_article_url(article.url, domains)
            if normalized is None or normalized in seen_urls:
                continue
            seen_urls.add(normalized)
            discoveries.append(
                DiscoveredUrl(
                    url=normalized,
                    source=source.slug,
                    method="sitemap",
                    entry_point=index_url,
                    query_term=None,
                    year_hint=article.year,
                )
            )
            added_from_sitemap += 1
        LOGGER.info(
            "Supplemental discovery source=%s method=sitemap sitemap=%s new_urls_added=%s",
            source.slug,
            sitemap_url,
            added_from_sitemap,
        )
    return discoveries


def parse_sitemap_index(xml_text: str) -> list[str]:
    """Extract sitemap URLs from a sitemap index document.

    Returns an empty list rather than raising when the response is not XML.
    A site under load, behind Cloudflare, or rate-limiting us answers a
    sitemap request with an HTML error page; feeding that to ET.fromstring
    raised ParseError and killed the entire collect stage mid-run, losing every
    source queued after the failure. A sitemap we cannot read is a reason to
    skip that supplemental path, not to abandon the crawl.
    """

    if not xml_text or not xml_text.lstrip().startswith('<'):
        LOGGER.warning('Sitemap index is not XML (starts with %r); skipping sitemap discovery',
                       (xml_text or '')[:40])
        return []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        # Almost always an HTML error page served in place of the sitemap.
        LOGGER.warning('Sitemap index did not parse as XML (%s); skipping sitemap discovery', exc)
        return []
    return [
        str(loc.text).strip()
        for loc in root.findall(".//sm:loc", SITEMAP_NAMESPACE)
        if loc.text and str(loc.text).strip()
    ]


def ordered_myrepublica_sitemaps(sitemap_urls: list[str]) -> list[str]:
    """Order MyRepublica sitemaps deterministically, favoring older archive shards first."""

    def sort_key(url: str) -> tuple[int, str]:
        match = re.search(r"sitemap_(\d+)\.xml$", url)
        if match is not None:
            return (0, f"{int(match.group(1)):04d}")
        return (1, url)

    return sorted(sitemap_urls, key=sort_key)


def parse_news_sitemap(xml_text: str) -> list[SitemapArticle]:
    """Extract article URLs, titles, and publication years from a news sitemap."""

    root = ET.fromstring(xml_text)
    articles: list[SitemapArticle] = []
    for url_node in root.findall(".//sm:url", NEWS_NAMESPACE):
        loc = url_node.find("sm:loc", NEWS_NAMESPACE)
        if loc is None or not loc.text:
            continue
        title = url_node.findtext("news:news/news:title", default="", namespaces=NEWS_NAMESPACE).strip()
        publication_date = url_node.findtext(
            "news:news/news:publication_date",
            default="",
            namespaces=NEWS_NAMESPACE,
        ).strip()
        year = int(publication_date[:4]) if publication_date[:4].isdigit() else None
        articles.append(SitemapArticle(url=str(loc.text).strip(), title=title, year=year))
    return articles


def parse_plain_sitemap(xml_text: str) -> list[SitemapArticle]:
    """Extract article URLs and years from a plain URL set sitemap."""

    root = ET.fromstring(xml_text)
    articles: list[SitemapArticle] = []
    for url_node in root.findall(".//sm:url", SITEMAP_NAMESPACE):
        loc = url_node.find("sm:loc", SITEMAP_NAMESPACE)
        if loc is None or not loc.text:
            continue
        lastmod = url_node.findtext("sm:lastmod", default="", namespaces=SITEMAP_NAMESPACE).strip()
        year = int(lastmod[:4]) if lastmod[:4].isdigit() else None
        articles.append(SitemapArticle(url=str(loc.text).strip(), title="", year=year))
    return articles


def keyword_match(text: str, include_terms: list[str], exclude_terms: list[str]) -> bool:
    """Return whether candidate text matches include terms without excluded phrases."""

    candidate = text.casefold()

    def variants(term: str) -> list[str]:
        lowered = term.casefold()
        return [lowered, lowered.replace(" ", "-"), lowered.replace(" ", "_")]

    if not any(any(variant in candidate for variant in variants(term)) for term in include_terms):
        return False
    return not any(any(variant in candidate for variant in variants(term)) for term in exclude_terms)


def shard_year(url: str) -> int | None:
    """Extract a shard year from a dated sitemap URL."""

    match = re.search(r"/sitemaps/(20\d{2})/", url)
    if match is None:
        return None
    return int(match.group(1))


def best_year_hint(year_hints: list[int]) -> int | None:
    """Choose the most recent in-period year hint from listing content."""

    eligible = [year for year in year_hints if 2015 <= year <= 2026]
    if not eligible:
        return None
    return max(eligible)


def should_stop_pagination(
    page_number: int,
    max_pages: int,
    consecutive_empty_pages: int,
    repeated_top_urls: bool,
) -> bool:
    """Decide whether listing pagination should stop."""

    if page_number >= max_pages:
        return True
    if consecutive_empty_pages >= 3:
        return True
    if repeated_top_urls:
        return True
    return False


def next_page_url(entry_point: dict[str, str], current_url: str, page_number: int) -> str | None:
    """Generate the next listing page URL for explicit pagination patterns."""

    pagination = str(entry_point["pagination"])
    if pagination == "rss" or pagination == "next_link":
        return None
    if pagination == "/page/{page}":
        base = str(entry_point["url"]).rstrip("/")
        return f"{base}/page/{page_number + 1}"
    if pagination == "page":
        parsed = urlparse(current_url)
        query = parse_qs(parsed.query)
        current_page = int(query.get("page", [str(page_number)])[0])
        query["page"] = [str(current_page + 1)]
        return urlunparse(parsed._replace(query=urlencode(query, doseq=True)))
    return None


def repeated_top_urls(previous_urls: list[str], current_urls: list[str], size: int = 5) -> bool:
    """Return whether two pages expose the same leading article URLs."""

    if not previous_urls or not current_urls:
        return False
    compare_size = min(size, len(previous_urls), len(current_urls))
    if compare_size == 0:
        return False
    return previous_urls[:compare_size] == current_urls[:compare_size]


def _detect_next_url(
    links: list[ListingLink],
    entry_point: dict[str, str],
    current_url: str,
) -> tuple[str | None, str]:
    pagination = str(entry_point["pagination"])
    if pagination == "next_link":
        next_link = _find_next_link(links, current_url)
        if next_link is not None:
            return next_link, "next_link"
        fallback = _infer_page_number_link(links, current_url)
        if fallback is not None:
            return fallback, "page_number_fallback"
        return None, "none"

    generated = next_page_url(entry_point, current_url, 1)
    if generated is None:
        return None, "none"
    return generated, "config_pagination"


def _find_next_link(links: list[ListingLink], current_url: str) -> str | None:
    """Find a semantic next-page link from the listing page."""

    markers = {"next", "next page", "older", "older posts", "अर्को", "अर्को पृष्ठ", "→", ">>"}
    for link in links:
        if "next" in link.rel.split():
            return normalize_url(link.href, base_url=current_url)
        if link.text in markers:
            return normalize_url(link.href, base_url=current_url)
    return None


def _infer_page_number_link(links: list[ListingLink], current_url: str) -> str | None:
    """Infer the next page URL from numbered pagination links when no semantic next link exists."""

    current_page = _extract_page_number(current_url) or 1
    current_parsed = urlparse(current_url)
    candidates: list[tuple[int, str]] = []
    for link in links:
        candidate_url = normalize_url(link.href, base_url=current_url)
        if urlparse(candidate_url).netloc != current_parsed.netloc:
            continue
        candidate_page = _extract_page_number(candidate_url)
        if candidate_page is None or candidate_page <= current_page:
            continue
        candidates.append((candidate_page, candidate_url))
    if not candidates:
        return None
    candidates.sort()
    return candidates[0][1]


def _extract_page_number(url: str) -> int | None:
    """Extract a page number from common pagination URL shapes."""

    parsed = urlparse(url)
    query_page = parse_qs(parsed.query).get("page")
    if query_page and query_page[0].isdigit():
        return int(query_page[0])
    match = re.search(r"/page/(\d+)(?:/)?$", parsed.path)
    if match is not None:
        return int(match.group(1))
    return None


def _build_search_urls(config: AppConfig, source: SourceDefinition, template: str) -> list[tuple[str, str]]:
    """Build deterministic search entry points for a source."""

    terms = list(config.raw["keywords"]["terms"][source.language])
    seen: set[str] = set()
    search_urls: list[tuple[str, str]] = []
    for term in terms:
        url = template.format(base=source.base_url.rstrip('/'), term=quote_plus(term))
        if url in seen:
            continue
        seen.add(url)
        search_urls.append((term, url))
    return search_urls
