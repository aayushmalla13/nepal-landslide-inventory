"""Tests for stale parser refresh support in collect."""

from __future__ import annotations

from pathlib import Path

from landslide_inventory.db import connect_sqlite, initialize_sqlite
from landslide_inventory.scrape.collect import _stale_refresh_discoveries
from landslide_inventory.scrape.models import DiscoveredUrl
from landslide_inventory.scrape.storage import stale_raw_article_urls_for_source
from landslide_inventory.sources import SourceDefinition


def test_stale_raw_article_urls_for_source_returns_parser_noise_rows(tmp_path: Path) -> None:
    database_path = tmp_path / "inventory.sqlite"
    initialize_sqlite(database_path)
    with connect_sqlite(database_path) as connection:
        connection.execute(
            """
            INSERT INTO raw_articles (url, source, title, text, parse_success, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "https://thehimalayantimes.com/nepal/example-noise",
                "himalayan-times",
                "Broken parse",
                '","#"===e.firstChild.getAttribute("href")})||fe("type|href|height|width",function(e,t,n){if(!n)return e.getAttribute(t)}',
                1,
                "2026-04-21T18:00:00+00:00",
            ),
        )
        connection.execute(
            """
            INSERT INTO raw_articles (url, source, title, text, parse_success, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "https://thehimalayantimes.com/nepal/example-clean",
                "himalayan-times",
                "Clean parse",
                "KATHMANDU: Two people were injured in a landslide in Gorkha district.",
                1,
                "2026-04-21T17:00:00+00:00",
            ),
        )
        connection.commit()

    stale_urls = stale_raw_article_urls_for_source(database_path, "himalayan-times")
    assert stale_urls == ["https://thehimalayantimes.com/nepal/example-noise"]


def test_stale_refresh_discoveries_adds_missing_stale_urls(tmp_path: Path) -> None:
    database_path = tmp_path / "inventory.sqlite"
    initialize_sqlite(database_path)
    with connect_sqlite(database_path) as connection:
        connection.execute(
            """
            INSERT INTO raw_articles (url, source, title, text, parse_success, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "https://thehimalayantimes.com/nepal/example-noise",
                "himalayan-times",
                "Broken parse",
                '","#"===e.firstChild.getAttribute("href")})||fe("type|href|height|width",function(e,t,n){if(!n)return e.getAttribute(t)}',
                1,
                "2026-04-21T18:00:00+00:00",
            ),
        )
        connection.commit()

    source = SourceDefinition(
        name="The Himalayan Times",
        slug="himalayan-times",
        language="en",
        base_url="https://thehimalayantimes.com",
        discovery={"primary": "googlenews"},
        entry_points=[],
    )
    discoveries = [
        DiscoveredUrl(
            url="https://thehimalayantimes.com/nepal/already-discovered",
            source="himalayan-times",
            method="tag",
            entry_point="https://thehimalayantimes.com/tag/landslide",
        )
    ]

    refreshes = _stale_refresh_discoveries(database_path, source, discoveries)

    assert len(refreshes) == 1
    assert refreshes[0].url == "https://thehimalayantimes.com/nepal/example-noise"
    assert refreshes[0].method == "refresh_stale"
    assert refreshes[0].entry_point == "https://thehimalayantimes.com"


def test_stale_raw_article_urls_for_source_returns_ratopati_nav_noise_rows(tmp_path: Path) -> None:
    database_path = tmp_path / "inventory.sqlite"
    initialize_sqlite(database_path)
    with connect_sqlite(database_path) as connection:
        connection.execute(
            """
            INSERT INTO raw_articles (url, source, title, text, parse_success, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "https://www.ratopati.com/story/123/example-noise",
                "ratopati",
                "Broken parse",
                "काठमाडौँ । अविरल वर्षाका कारण सडक अवरुद्ध भएको छ । समाचार अदालत/प्रशासन सुरक्षा/अपराध हेडलाइन एक्सक्लुसिभ प्रदेश थप समाचार",
                1,
                "2026-04-21T18:00:00+00:00",
            ),
        )
        connection.commit()

    stale_urls = stale_raw_article_urls_for_source(database_path, "ratopati")
    assert stale_urls == ["https://www.ratopati.com/story/123/example-noise"]
