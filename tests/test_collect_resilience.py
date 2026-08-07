"""A crawl must survive one bad response.

Reproduces a real failure from 2026-08-07: myRepublica answered a sitemap
request with an HTML error page, ET.fromstring raised

    xml.etree.ElementTree.ParseError: mismatched tag: line 4, column 2

and the whole collect stage died. Every source queued behind myrepublica
collected nothing, and the run had to start over.
"""

from __future__ import annotations

import pytest

from landslide_inventory.scrape.discovery import parse_sitemap_index

VALID_SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://example.com/sitemap_1.xml</loc></sitemap>
  <sitemap><loc>https://example.com/sitemap_2.xml</loc></sitemap>
</sitemapindex>"""

# What the site actually returned: an HTML error page. The <meta> tag is
# unclosed, which is legal HTML and fatal XML -- hence "mismatched tag".
HTML_ERROR_PAGE = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>503 Service Unavailable</title>
</head>
<body><h1>Service Unavailable</h1></body>
</html>"""


def test_valid_sitemap_index_still_parses() -> None:
    assert parse_sitemap_index(VALID_SITEMAP) == [
        'https://example.com/sitemap_1.xml',
        'https://example.com/sitemap_2.xml',
    ]


def test_html_error_page_does_not_raise() -> None:
    """The exact input that killed the run."""

    assert parse_sitemap_index(HTML_ERROR_PAGE) == []


def test_cloudflare_challenge_does_not_raise() -> None:
    assert parse_sitemap_index(
        '<html><head><title>Just a moment...</title></head><body></body></html>') == []


@pytest.mark.parametrize('payload', [
    '', '   ', 'Rate limited. Try again later.', '{"error": "not found"}',
    '<?xml version="1.0"?><unclosed>', 'null',
])
def test_junk_payloads_never_raise(payload: str) -> None:
    """Whatever a site returns, it must not end the crawl."""

    assert parse_sitemap_index(payload) == []


def test_one_failing_source_does_not_stop_the_others() -> None:
    """collect.py catches per-source failures rather than aborting the stage."""

    from pathlib import Path
    source = Path('src/landslide_inventory/scrape/collect.py').read_text(encoding='utf-8')
    assert 'failed_sources' in source, 'per-source failures must be recorded'
    assert 'continue' in source.split('failed_sources.append')[1][:80], (
        'a failing source must be skipped, not allowed to abort the run'
    )
    assert 'FAILED and collected nothing' in source, (
        'failures must be reported loudly at the end; a partial crawl that looks '
        'complete becomes a silent gap in the inventory'
    )
