"""Tests for bounded discovery from external incident seeds."""

from __future__ import annotations

import csv
from pathlib import Path

from landslide_inventory.config import load_config
from landslide_inventory.db import connect_sqlite, initialize_sqlite
from landslide_inventory.external.discover import (
    SearchSeed,
    build_seed_queries,
    discover_seed_candidates,
    run_external_discover_stage,
)
from landslide_inventory.external.http import HttpResponse
from landslide_inventory.run import STAGE_HANDLERS, resolve_stage_name

RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <item>
    <title>Fatal landslide reported in Panchthar - Example News</title>
    <link>https://news.google.com/rss/articles/example-one?oc=5</link>
    <guid isPermaLink="false">example-one</guid>
    <pubDate>Wed, 20 Oct 2021 07:00:00 GMT</pubDate>
    <source url="https://example.com">Example News</source>
  </item>
</channel></rss>"""


class FakeClient:
    def __init__(self, body: str = RSS) -> None:
        self.body = body
        self.urls: list[str] = []

    def request(self, url: str, **_kwargs) -> HttpResponse:
        self.urls.append(url)
        return HttpResponse(
            url=url,
            status=200,
            body=self.body.encode(),
            headers={"content-type": "application/rss+xml; charset=utf-8"},
            retrieved_at="2026-08-09T00:00:00+00:00",
        )


def _write_seeds(path: Path) -> None:
    fields = [
        "match_status",
        "priority",
        "bipad_cluster_id",
        "event_date",
        "search_date_from",
        "search_date_to",
        "district",
        "municipality",
        "deaths",
        "title",
    ]
    rows = [
        {
            "match_status": "unmatched",
            "priority": "high",
            "bipad_cluster_id": "bipad-1",
            "event_date": "2021-10-19",
            "search_date_from": "2021-10-16",
            "search_date_to": "2021-10-22",
            "district": "Panchthar",
            "municipality": "Miklajung",
            "deaths": "23",
            "title": "BIPAD incident",
        },
        {
            "match_status": "unmatched",
            "priority": "standard",
            "bipad_cluster_id": "bipad-2",
            "event_date": "2021-10-20",
            "search_date_from": "2021-10-17",
            "search_date_to": "2021-10-23",
            "district": "Ilam",
            "municipality": "Illam Municipality",
            "deaths": "0",
            "title": "Lower priority incident",
        },
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_build_seed_queries_has_narrow_and_district_fallbacks() -> None:
    seed = SearchSeed(
        seed_id="b1",
        match_status="unmatched",
        priority="high",
        event_date="2021-10-19",
        search_date_from="2021-10-16",
        search_date_to="2021-10-22",
        district="Panchthar",
        municipality="Miklajung",
        deaths=23,
        title=None,
    )
    queries = build_seed_queries(seed)
    assert [scope for scope, _query in queries] == [
        "municipality_en",
        "district_en",
        "district_np",
    ]
    assert all("after:2021-10-15 before:2021-10-23" in query for _scope, query in queries)


def test_discovery_is_bounded_deduplicated_and_preserves_review(config_file: Path) -> None:
    config = load_config(config_file)
    config.raw["external_sources"] = {
        "matching": {
            "seed_discovery": {
                "max_seeds": 1,
                "statuses": ["unmatched"],
                "priorities": ["high"],
                "max_results_per_query": 5,
            }
        }
    }
    initialize_sqlite(config.sqlite_path)
    _write_seeds(config.resolve_path("outputs_dir") / "external_search_seeds.csv")
    client = FakeClient()

    summary = discover_seed_candidates(config, client)

    assert summary == {
        "seeds_selected": 1,
        "queries_run": 3,
        "seeds_with_results": 1,
        "seeds_without_results": 0,
        "candidates_this_run": 1,
        "candidates_stored_this_run": 1,
        "candidates_exported_total": 1,
    }
    assert len(client.urls) == 3
    with connect_sqlite(config.sqlite_path) as connection:
        row = connection.execute("SELECT * FROM external_news_candidates").fetchone()
        connection.execute(
            """UPDATE external_news_candidates
               SET review_status='accepted', resolved_url='https://example.com/article'
               WHERE candidate_id=?""",
            (row["candidate_id"],),
        )
        connection.commit()

    discover_seed_candidates(config, FakeClient())

    with connect_sqlite(config.sqlite_path) as connection:
        reviewed = connection.execute("SELECT * FROM external_news_candidates").fetchone()
    assert reviewed["review_status"] == "accepted"
    assert reviewed["resolved_url"] == "https://example.com/article"
    exported = (
        config.resolve_path("outputs_dir") / "external_news_candidates.csv"
    ).read_text(encoding="utf-8")
    assert "Fatal landslide reported in Panchthar" in exported
    assert "https://example.com/article" in exported


def test_external_discover_stage_is_registered() -> None:
    assert resolve_stage_name("discover_external") == "external_discover"
    assert STAGE_HANDLERS["external_discover"] is run_external_discover_stage
