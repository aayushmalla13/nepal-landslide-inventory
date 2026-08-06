"""Tests for URL filtering helpers."""

from __future__ import annotations

from landslide_inventory.scrape.url_tools import filter_article_url, normalize_url


def test_normalize_url_strips_tracking_and_amp_suffix() -> None:
    assert (
        normalize_url(
            'https://kathmandupost.com/national/2021/07/14/story/amp?utm_source=x&fbclid=y'
        )
        == 'https://kathmandupost.com/national/2021/07/14/story'
    )


def test_filter_article_url_rejects_disallowed_domain() -> None:
    assert (
        filter_article_url(
            'https://example.org/news/2021/story',
            allowed_domains=['kathmandupost.com'],
        )
        is None
    )


def test_filter_article_url_rejects_tag_pages() -> None:
    assert (
        filter_article_url(
            'https://www.ratopati.com/tag/797?page=1',
            allowed_domains=['ratopati.com'],
        )
        is None
    )


def test_filter_article_url_rejects_setopati_tag_pagination_pages() -> None:
    assert (
        filter_article_url(
            'https://www.setopati.com/tag/577?page=2',
            allowed_domains=['setopati.com'],
        )
        is None
    )


def test_normalize_url_percent_encodes_spaces_in_paths() -> None:
    assert (
        normalize_url('https://thehimalayantimes.com/news archives/landslide-claims-nine-lives-in-jajarkot-village')
        == 'https://thehimalayantimes.com/news%20archives/landslide-claims-nine-lives-in-jajarkot-village'
    )


def test_filter_article_url_rejects_onlinekhabar_content_pages() -> None:
    assert (
        filter_article_url(
            'https://www.onlinekhabar.com/content/nepalbeauty',
            allowed_domains=['onlinekhabar.com'],
        )
        is None
    )


def test_filter_article_url_rejects_onlinekhabar_segment_pages() -> None:
    assert (
        filter_article_url(
            'https://www.onlinekhabar.com/segment/cooperative-crisis',
            allowed_domains=['onlinekhabar.com'],
        )
        is None
    )


def test_filter_article_url_rejects_kathmandupost_pages() -> None:
    assert (
        filter_article_url(
            'https://kathmandupost.com/pages/about-us',
            allowed_domains=['kathmandupost.com'],
        )
        is None
    )


def test_filter_article_url_rejects_ratopati_segment_pages() -> None:
    assert (
        filter_article_url(
            'https://www.ratopati.com/segment/12th-anniversay-special',
            allowed_domains=['ratopati.com'],
        )
        is None
    )


def test_filter_article_url_rejects_ratopati_football_pages() -> None:
    assert (
        filter_article_url(
            'https://www.ratopati.com/football/euro-cup-2024',
            allowed_domains=['ratopati.com'],
        )
        is None
    )


def test_filter_article_url_rejects_setopati_from_paper_pages() -> None:
    assert (
        filter_article_url(
            'https://www.setopati.com/from-paper/62569',
            allowed_domains=['setopati.com'],
        )
        is None
    )


def test_filter_article_url_rejects_cdn_cgi_paths() -> None:
    assert (
        filter_article_url(
            'https://www.ratopati.com/cdn-cgi/l/email-protection',
            allowed_domains=['ratopati.com'],
        )
        is None
    )


def test_filter_article_url_rejects_ratopati_cricket_pages() -> None:
    assert (
        filter_article_url(
            'https://www.ratopati.com/cricket/icc-mens-t20-world-cup-2024',
            allowed_domains=['ratopati.com'],
        )
        is None
    )



def test_filter_article_url_rejects_setopati_blog_pages() -> None:
    assert (
        filter_article_url(
            'https://www.setopati.com/blog/240771',
            allowed_domains=['setopati.com'],
        )
        is None
    )



def test_filter_article_url_rejects_setopati_ghumphir_pages() -> None:
    assert (
        filter_article_url(
            'https://www.setopati.com/ghumphir/ghumphir-experience/308041',
            allowed_domains=['setopati.com'],
        )
        is None
    )



def test_filter_article_url_rejects_kathmandupost_art_culture_pages() -> None:
    assert (
        filter_article_url(
            'https://kathmandupost.com/art-culture/2026/03/25/bhaktapur-film-festival-spotlights-emerging-nepali-cinema',
            allowed_domains=['kathmandupost.com'],
        )
        is None
    )
