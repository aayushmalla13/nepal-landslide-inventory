"""Listing and source-native discovery helpers."""

from __future__ import annotations

import http.cookiejar
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
from urllib.parse import parse_qs, quote_plus, urlencode, urlparse, urlunparse

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

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "a" and attributes.get("href"):
            self._current_href = str(attributes["href"])
            self._link_text_parts = []
            self._current_rel = str(attributes.get("rel") or "")

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
                )
            )
            self._current_href = None
            self._link_text_parts = []
            self._current_rel = ""


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
    return []


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
