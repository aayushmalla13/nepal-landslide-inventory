"""Tests for stale parser refresh support in collect."""

from __future__ import annotations

from pathlib import Path

from landslide_inventory.db import connect_sqlite, initialize_sqlite
from landslide_inventory.scrape.collect import _select_sources, _stale_refresh_discoveries, _year_hint_from_url
from landslide_inventory.scrape.models import DiscoveredUrl
from landslide_inventory.scrape.storage import raw_article_urls_for_source, stale_raw_article_urls_for_source
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
    assert raw_article_urls_for_source(database_path, "himalayan-times") == {
        "https://thehimalayantimes.com/nepal/example-noise",
        "https://thehimalayantimes.com/nepal/example-clean",
    }


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


def test_year_hint_from_url_supports_current_and_historical_years() -> None:
    assert _year_hint_from_url('https://deshsanchar.com/2026/08/10/1214111/', []) == 2026
    assert _year_hint_from_url('https://deshsanchar.com/2017/12/02/545/', []) == 2017


def test_select_sources_accepts_comma_separated_slugs(monkeypatch) -> None:
    sources = [
        SourceDefinition('A', 'a', 'np', 'https://a.test', {'primary': 'x'}, []),
        SourceDefinition('B', 'b', 'np', 'https://b.test', {'primary': 'x'}, []),
    ]
    monkeypatch.setenv('LS_SOURCE', 'b,a')
    assert [source.slug for source in _select_sources(sources)] == ['a', 'b']
