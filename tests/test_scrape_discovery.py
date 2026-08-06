"""Tests for listing and supplemental discovery helpers."""

from __future__ import annotations

from landslide_inventory.config import load_config
from landslide_inventory.scrape.discovery import (
    build_ratopati_search_urls,
    build_setopati_search_urls,
    build_source_native_discoveries,
    keyword_match,
    parse_listing_page,
    parse_news_sitemap,
    parse_plain_sitemap,
    parse_sitemap_index,
    repeated_top_urls,
    shard_year,
    best_year_hint,
    should_stop_pagination,
)
from landslide_inventory.scrape.models import FetchResult
from landslide_inventory.sources import load_sources


class StubFetcher:
    """Deterministic fetcher for discovery tests."""

    def __init__(self, payloads: dict[str, str]) -> None:
        self.payloads = payloads

    def fetch(self, url: str) -> FetchResult:
        return FetchResult(url=url, status_code=200, text=self.payloads[url], fetched_at='2026-03-24T00:00:00Z')


def test_parse_listing_page_extracts_article_urls_and_next_link(config_file) -> None:
    config = load_config(config_file)
    source = next(source for source in load_sources(config) if source.slug == 'setopati')
    entry_point = source.entry_points[0]
    html = """
    <html><body>
      <a href="/politics/12345">Story one</a>
      <a href="/tag/577">Tag page</a>
      <a href="/page/2" rel="next">Next</a>
      <span>2021</span>
    </body></html>
    """
    listing = parse_listing_page(html, source, entry_point, 'https://www.setopati.com/tag/577')
    assert listing.urls == ['https://www.setopati.com/politics/12345']
    assert listing.next_url == 'https://www.setopati.com/page/2'
    assert listing.next_method == 'next_link'
    assert listing.year_hints == [2021]


def test_parse_listing_page_falls_back_to_numbered_pagination_for_setopati(config_file) -> None:
    config = load_config(config_file)
    source = next(source for source in load_sources(config) if source.slug == 'setopati')
    entry_point = source.entry_points[0]
    html = """
    <html><body>
      <a href="/news/1001">Story one</a>
      <a href="https://www.setopati.com/tag/577?page=2">2</a>
      <a href="https://www.setopati.com/tag/577?page=3">3</a>
    </body></html>
    """
    listing = parse_listing_page(html, source, entry_point, 'https://www.setopati.com/tag/577?page=1')
    assert listing.urls == ['https://www.setopati.com/news/1001']
    assert listing.next_url == 'https://www.setopati.com/tag/577?page=2'
    assert listing.next_method == 'page_number_fallback'


def test_should_stop_pagination_after_three_empty_new_pages() -> None:
    assert (
        should_stop_pagination(
            page_number=3,
            max_pages=10,
            consecutive_empty_pages=3,
            repeated_top_urls=False,
        )
        is True
    )


def test_should_stop_pagination_when_top_urls_repeat_or_max_pages_reached() -> None:
    assert (
        should_stop_pagination(
            page_number=2,
            max_pages=5,
            consecutive_empty_pages=0,
            repeated_top_urls=True,
        )
        is True
    )
    assert (
        should_stop_pagination(
            page_number=5,
            max_pages=5,
            consecutive_empty_pages=0,
            repeated_top_urls=False,
        )
        is True
    )


def test_repeated_top_urls_detects_same_leading_article_set() -> None:
    assert repeated_top_urls(
        ['https://example.com/a', 'https://example.com/b'],
        ['https://example.com/a', 'https://example.com/b', 'https://example.com/c'],
    ) is True


def test_parse_sitemap_index_and_news_sitemap_extract_expected_rows() -> None:
    index_xml = """
    <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <sitemap><loc>https://example.com/sitemap_1.xml</loc></sitemap>
    </sitemapindex>
    """
    sitemap_xml = """
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">
      <url>
        <loc>https://myrepublica.nagariknetwork.com/news/landslide-buries-house</loc>
        <news:news>
          <news:publication_date>2024-07-11T07:00:00+05:45</news:publication_date>
          <news:title>Landslide buries house</news:title>
        </news:news>
      </url>
    </urlset>
    """
    assert parse_sitemap_index(index_xml) == ['https://example.com/sitemap_1.xml']
    articles = parse_news_sitemap(sitemap_xml)
    assert len(articles) == 1
    assert articles[0].url == 'https://myrepublica.nagariknetwork.com/news/landslide-buries-house'
    assert articles[0].title == 'Landslide buries house'
    assert articles[0].year == 2024


def test_parse_plain_sitemap_and_shard_year_extract_expected_rows() -> None:
    sitemap_xml = """
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url>
        <loc>https://thehimalayantimes.com/nepal/landslide-kills-three</loc>
        <lastmod>2021-07-11T07:00:00+05:45</lastmod>
      </url>
    </urlset>
    """
    articles = parse_plain_sitemap(sitemap_xml)
    assert len(articles) == 1
    assert articles[0].url == 'https://thehimalayantimes.com/nepal/landslide-kills-three'
    assert articles[0].year == 2021
    assert shard_year('https://thehimalayantimes.com/sitemaps/2021/7/sitemap_0.xml?v=1.1') == 2021


def test_keyword_match_applies_include_and_exclude_terms() -> None:
    assert keyword_match('landslide kills three in ilam', ['landslide'], ['political landslide']) is True
    assert keyword_match('political-landslide-victory', ['landslide'], ['political landslide']) is False
    assert keyword_match('debris-flow-reported-in-kaski', ['debris flow'], []) is True


def test_build_search_urls_use_config_terms(config_file) -> None:
    config = load_config(config_file)
    setopati = next(source for source in load_sources(config) if source.slug == 'setopati')
    ratopati = next(source for source in load_sources(config) if source.slug == 'ratopati')
    setopati_urls = build_setopati_search_urls(config, setopati)
    ratopati_urls = build_ratopati_search_urls(config, ratopati)
    assert setopati_urls[0][0] == 'पहिरो'
    assert setopati_urls[0][1] == 'https://www.setopati.com/search?keyword=%E0%A4%AA%E0%A4%B9%E0%A4%BF%E0%A4%B0%E0%A5%8B'
    assert ratopati_urls[0][1] == 'https://www.ratopati.com/search?keyword=%E0%A4%AA%E0%A4%B9%E0%A4%BF%E0%A4%B0%E0%A5%8B&page=1'


def test_myrepublica_sitemap_supplement_filters_to_in_period_keyword_articles(config_file) -> None:
    config = load_config(config_file)
    source = next(source for source in load_sources(config) if source.slug == 'myrepublica')
    fetcher = StubFetcher(
        {
            'https://myrepublica.nagariknetwork.com/sitemap.xml': """
            <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
              <sitemap><loc>https://myrepublica.nagariknetwork.com/storage/sitemap_1.xml</loc></sitemap>
            </sitemapindex>
            """,
            'https://myrepublica.nagariknetwork.com/storage/sitemap_1.xml': """
            <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">
              <url>
                <loc>https://myrepublica.nagariknetwork.com/news/landslide-buries-house</loc>
                <news:news>
                  <news:publication_date>2024-07-11T07:00:00+05:45</news:publication_date>
                  <news:title>Landslide buries house</news:title>
                </news:news>
              </url>
              <url>
                <loc>https://myrepublica.nagariknetwork.com/news/political-landslide-victory</loc>
                <news:news>
                  <news:publication_date>2024-07-12T07:00:00+05:45</news:publication_date>
                  <news:title>Political landslide victory</news:title>
                </news:news>
              </url>
              <url>
                <loc>https://myrepublica.nagariknetwork.com/news/old-landslide</loc>
                <news:news>
                  <news:publication_date>2014-07-11T07:00:00+05:45</news:publication_date>
                  <news:title>Landslide in archive</news:title>
                </news:news>
              </url>
            </urlset>
            """,
        }
    )
    discoveries = build_source_native_discoveries(
        config,
        source,
        fetcher,
        seen_urls=set(),
        max_pages=5,
        max_urls=50,
    )
    assert [discovery.url for discovery in discoveries] == [
        'https://myrepublica.nagariknetwork.com/news/landslide-buries-house'
    ]
    assert discoveries[0].method == 'sitemap'
    assert discoveries[0].year_hint == 2024


def test_setopati_search_supplement_paginates_and_discovers_articles(config_file) -> None:
    config = load_config(config_file)
    source = next(source for source in load_sources(config) if source.slug == 'setopati')
    fetcher = StubFetcher(
        {
            'https://www.setopati.com/search?keyword=%E0%A4%AA%E0%A4%B9%E0%A4%BF%E0%A4%B0%E0%A5%8B': """
            <html><body>
              <span>2024</span>
              <a href="https://www.setopati.com/social/1001">Story one</a>
              <a href="https://www.setopati.com/search?keyword=%E0%A4%AA%E0%A4%B9%E0%A4%BF%E0%A4%B0%E0%A5%8B&amp;page=2" rel="next">Next</a>
            </body></html>
            """,
            'https://www.setopati.com/search?keyword=%E0%A4%AA%E0%A4%B9%E0%A4%BF%E0%A4%B0%E0%A5%8B&page=2': """
            <html><body>
              <span>2023</span>
              <a href="https://www.setopati.com/social/1002">Story two</a>
            </body></html>
            """,
            'https://www.setopati.com/search?keyword=%E0%A4%AD%E0%A5%82%E0%A4%B8%E0%A5%8D%E0%A4%96%E0%A4%B2%E0%A4%A8': '<html><body></body></html>',
            'https://www.setopati.com/search?keyword=%E0%A4%A2%E0%A4%BF%E0%A4%B8%E0%A5%8D%E0%A4%95%E0%A5%8B': '<html><body></body></html>',
            'https://www.setopati.com/search?keyword=%E0%A4%AE%E0%A4%BE%E0%A4%9F%E0%A5%8B+%E0%A4%96%E0%A4%B8%E0%A5%8D%E0%A4%A8%E0%A5%81': '<html><body></body></html>',
        }
    )
    discoveries = build_source_native_discoveries(
        config,
        source,
        fetcher,
        seen_urls=set(),
        max_pages=5,
        max_urls=50,
    )
    assert [discovery.url for discovery in discoveries[:2]] == [
        'https://www.setopati.com/social/1001',
        'https://www.setopati.com/social/1002',
    ]
    assert discoveries[0].method == 'search'
    assert discoveries[0].query_term == 'पहिरो'


def test_himalayan_times_plain_sitemap_supplement_filters_keyword_urls(config_file) -> None:
    config = load_config(config_file)
    source = next(source for source in load_sources(config) if source.slug == 'himalayan-times')
    fetcher = StubFetcher(
        {
            'https://thehimalayantimes.com/sitemaps/sitemap_0.xml': """
            <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
              <sitemap><loc>https://thehimalayantimes.com/sitemaps/2021/7/sitemap_0.xml?v=1.1</loc></sitemap>
            </sitemapindex>
            """,
            'https://thehimalayantimes.com/sitemaps/2021/7/sitemap_0.xml?v=1.1': """
            <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
              <url>
                <loc>https://thehimalayantimes.com/nepal/landslide-kills-three</loc>
                <lastmod>2021-07-11T07:00:00+05:45</lastmod>
              </url>
              <url>
                <loc>https://thehimalayantimes.com/nepal/political-landslide-victory</loc>
                <lastmod>2021-07-12T07:00:00+05:45</lastmod>
              </url>
            </urlset>
            """,
        }
    )
    discoveries = build_source_native_discoveries(
        config,
        source,
        fetcher,
        seen_urls=set(),
        max_pages=5,
        max_urls=50,
    )
    assert [discovery.url for discovery in discoveries] == [
        'https://thehimalayantimes.com/nepal/landslide-kills-three'
    ]


def test_best_year_hint_allows_2026() -> None:
    assert best_year_hint([2022, 2024, 2026]) == 2026
