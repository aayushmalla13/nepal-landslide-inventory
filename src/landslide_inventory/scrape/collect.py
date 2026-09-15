"""Scraping stage orchestration."""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path

from ..config import AppConfig
from ..db import initialize_sqlite
from ..sources import discovery_entry_points, load_sources
from ..utils import ensure_directory
from .discovery import (
    build_google_news_discoveries,
    build_source_native_discoveries,
    parse_listing_page,
    repeated_top_urls,
    should_stop_pagination,
)
from .fetcher import HTTPFetcher
from .models import DiscoveredUrl
from .parser import parse_article_html
from .storage import (
    count_discovered_urls_for_source,
    discovered_urls_for_source,
    raw_article_urls_for_source,
    stale_raw_article_urls_for_source,
    upsert_discovered_url,
    upsert_raw_article,
    write_coverage_report,
)

LOGGER = logging.getLogger(__name__)


def run_collect_stage(config: AppConfig) -> None:
    """Run hybrid discovery and raw article fetching."""

    for directory in config.data_directories():
        ensure_directory(directory)
    database_path = config.sqlite_path
    initialize_sqlite(database_path)
    fetcher = HTTPFetcher.from_config(config)
    sources = _select_sources(load_sources(config))

    failed_sources: list[tuple[str, str]] = []

    for source in sources:
        total_before = count_discovered_urls_for_source(database_path, source.slug)
        fetched_urls = raw_article_urls_for_source(database_path, source.slug)
        stale_urls = set(stale_raw_article_urls_for_source(database_path, source.slug))
        LOGGER.info('Collecting source %s', source.slug)
        try:
            discoveries, new_discovered = _discover_source(config, source, fetcher, database_path)
        except Exception as exc:  # noqa: BLE001 - one bad source must not end the crawl
            # A crawl is a long, partly unreliable operation over eight
            # independent sites. Letting one site's malformed response abort the
            # whole stage throws away every source queued behind it, and the
            # work already done is not resumable in one command. Record the
            # failure, keep going, and report it at the end.
            LOGGER.error('Source %s failed during discovery: %s: %s',
                         source.slug, type(exc).__name__, exc)
            failed_sources.append((source.slug, f'{type(exc).__name__}: {exc}'))
            continue
        stale_refreshes = _stale_refresh_discoveries(database_path, source, discoveries)
        if stale_refreshes:
            LOGGER.info('Source %s stale refresh queue=%s', source.slug, len(stale_refreshes))
            discoveries.extend(stale_refreshes)
        fetched_this_run = 0
        skipped_existing = 0
        for discovered in discoveries:
            upsert_discovered_url(database_path, discovered)
            if discovered.method == 'googlenews':
                continue
            if discovered.url in fetched_urls and discovered.url not in stale_urls:
                skipped_existing += 1
                continue
            fetch_result = fetcher.fetch(discovered.url)
            parsed = parse_article_html(source, fetch_result.text, discovered.url)
            upsert_raw_article(
                database_path,
                source=source.slug,
                url=discovered.url,
                fetch_result=fetch_result,
                parsed=parsed,
                method=discovered.method,
                entry_point=discovered.entry_point,
            )
            fetched_this_run += 1
            if fetched_this_run % 50 == 0:
                LOGGER.info(
                    'Source %s fetch progress: fetched_this_run=%s queued=%s skipped_existing=%s',
                    source.slug,
                    fetched_this_run,
                    len(discoveries),
                    skipped_existing,
                )
        total_after = count_discovered_urls_for_source(database_path, source.slug)
        LOGGER.info(
            'Source %s summary: total discovered=%s, new discovered this run=%s, fetched_this_run=%s, skipped_existing=%s',
            source.slug,
            total_after,
            max(total_after - total_before, new_discovered),
            fetched_this_run,
            skipped_existing,
        )

    report_path = config.resolve_path('outputs_dir') / 'coverage_report.csv'
    write_coverage_report(database_path, report_path)
    LOGGER.info('Coverage report written to %s', report_path)

    if failed_sources:
        # Loud, and at the end where it will actually be seen. A partial crawl
        # that looks complete is worse than one that failed outright, because
        # the missing source silently becomes a gap in the inventory.
        LOGGER.warning('%d of %d sources FAILED and collected nothing this run:',
                       len(failed_sources), len(sources))
        for slug, reason in failed_sources:
            LOGGER.warning('    %-18s %s', slug, reason)
        LOGGER.warning('The other sources completed. Re-run --stage collect to retry the '
                       'failures; discovery is idempotent, so completed work is not repeated.')


def _discover_source(
    config: AppConfig,
    source,
    fetcher: HTTPFetcher,
    database_path: Path,
) -> tuple[list[DiscoveredUrl], int]:
    """Collect discoveries for a source and return discoveries plus new-url count."""

    runtime = dict(config.raw['runtime'])
    max_pages = int(source.discovery.get('max_pages', runtime['max_pages_per_entry_point']))
    max_urls = int(source.discovery.get('max_urls', runtime['max_urls_per_source']))
    existing_urls = discovered_urls_for_source(database_path, source.slug)
    discoveries: list[DiscoveredUrl] = []
    discovered_url_set: set[str] = set()
    yielded_urls: set[str] = set()
    new_discovered = 0

    for entry_point in discovery_entry_points(source):
        method = str(entry_point['kind'])
        if method == 'source_native':
            continue
        if method == 'googlenews':
            for discovered in build_google_news_discoveries(config, source):
                if discovered.url in discovered_url_set:
                    continue
                discoveries.append(discovered)
                discovered_url_set.add(discovered.url)
                if discovered.url not in existing_urls and discovered.url not in yielded_urls:
                    new_discovered += 1
                    yielded_urls.add(discovered.url)
            continue

        current_url = str(entry_point['url'])
        page_number = 1
        previous_page_urls: list[str] = []
        consecutive_empty_pages = 0
        while current_url and len(discoveries) < max_urls:
            fetch_result = fetcher.fetch(current_url)
            listing = parse_listing_page(fetch_result.text, source, entry_point, current_url)
            page_discoveries: list[DiscoveredUrl] = []
            page_new_urls = 0
            for url in listing.urls:
                if url in discovered_url_set:
                    continue
                discovery = DiscoveredUrl(
                    url=url,
                    source=source.slug,
                    method=method,
                    entry_point=str(entry_point['url']),
                    year_hint=_year_hint_from_url(url, listing.year_hints),
                )
                page_discoveries.append(discovery)
                discovered_url_set.add(url)
                if url not in existing_urls and url not in yielded_urls:
                    page_new_urls += 1
                    yielded_urls.add(url)
            discoveries.extend(page_discoveries)
            new_discovered += page_new_urls
            repeated = repeated_top_urls(previous_page_urls, listing.urls)
            consecutive_empty_pages = consecutive_empty_pages + 1 if page_new_urls == 0 else 0
            LOGGER.info(
                'Discovery page source=%s page=%s current_url=%s urls_found=%s new_urls_added=%s next_method=%s',
                source.slug,
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

    remaining_capacity = max(0, max_urls - len(discoveries))
    if remaining_capacity > 0:
        supplemental = build_source_native_discoveries(
            config,
            source,
            fetcher,
            seen_urls=discovered_url_set,
            max_pages=max_pages,
            max_urls=remaining_capacity,
        )
        for discovered in supplemental:
            discoveries.append(discovered)
            if discovered.url not in existing_urls and discovered.url not in yielded_urls:
                new_discovered += 1
                yielded_urls.add(discovered.url)

    return discoveries[:max_urls], new_discovered


def _stale_refresh_discoveries(
    database_path: Path,
    source,
    discoveries: list[DiscoveredUrl],
) -> list[DiscoveredUrl]:
    """Return discovered URLs that should be refetched because stored text looks corrupted."""

    seen_urls = {discovered.url for discovered in discoveries}
    refreshes: list[DiscoveredUrl] = []
    for url in stale_raw_article_urls_for_source(database_path, source.slug):
        if url in seen_urls:
            continue
        refreshes.append(
            DiscoveredUrl(
                url=url,
                source=source.slug,
                method='refresh_stale',
                entry_point=source.base_url,
                year_hint=_year_hint_from_url(url, []),
            )
        )
    return refreshes


def _year_hint_from_url(url: str, year_hints: list[int]) -> int | None:
    """Choose a year hint from listing context or URL path."""

    match = re.search(r'(?:/|-)(20\d{2})(?:/|-)', url)
    if match is not None:
        year = int(match.group(1))
        if 2015 <= year <= 2026:
            return year
    if year_hints:
        eligible = [year for year in year_hints if 2015 <= year <= 2026]
        if eligible:
            return max(eligible)
    return None


def _select_sources(sources):
    """Apply the optional comma-separated LS_SOURCE collection selector."""

    raw_selector = os.getenv('LS_SOURCE', '').strip()
    if not raw_selector:
        return sources
    requested = {slug.strip() for slug in raw_selector.split(',') if slug.strip()}
    selected = [source for source in sources if source.slug in requested]
    missing = sorted(requested - {source.slug for source in selected})
    if missing:
        raise ValueError(f"Unknown LS_SOURCE slug(s): {', '.join(missing)}")
    LOGGER.info('Source selector active: %s', ', '.join(source.slug for source in selected))
    return selected
