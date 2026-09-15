"""Tests for review-gated assisted article ingestion."""

from __future__ import annotations

from pathlib import Path

from landslide_inventory.config import load_config
from landslide_inventory.db import connect_sqlite, initialize_sqlite
from landslide_inventory.external.ingest import (
    ASSISTED_METHOD,
    ingest_reviewed_candidates,
    run_external_ingest_stage,
    source_for_candidate,
)
from landslide_inventory.run import STAGE_HANDLERS, resolve_stage_name
from landslide_inventory.scrape.models import FetchResult
from landslide_inventory.validation.locked_test_set import DESIGN_VERSION, load_frame

ARTICLE_HTML = """
<html><head>
<meta property="og:title" content="Verified Mugu landslide article">
<meta property="article:published_time" content="2026-08-09T07:00:00+05:45">
</head><body><article>
<p>A landslide in Chhayanath Rara Municipality in Mugu killed eight people and
left another person missing after prolonged rainfall. Police and local rescue
teams reached the affected settlement and moved displaced families to a nearby
school while the search continued through the following day.</p>
</article></body></html>
"""


class FakeFetcher:
    def __init__(self) -> None:
        self.urls: list[str] = []

    def fetch(self, url: str) -> FetchResult:
        self.urls.append(url)
        return FetchResult(
            url=url,
            status_code=200,
            text=ARTICLE_HTML,
            fetched_at="2026-08-09T00:00:00+00:00",
        )


def _insert_candidate(config, *, status: str, suffix: str) -> str:
    candidate_id = f"candidate-{suffix}"
    with connect_sqlite(config.sqlite_path) as connection:
        connection.execute(
            """
            INSERT INTO external_news_candidates (
                candidate_id, seed_id, seed_match_status, seed_event_date,
                seed_district, seed_municipality, seed_deaths, provider,
                query_scope, query, result_id, result_url, source_name,
                source_home_url, title, published_at, retrieved_at,
                review_status, resolved_url
            ) VALUES (?, ?, 'unmatched', '2022-10-10', 'Mugu',
                      'Chhayanath Rara', 8, 'google-news-rss', 'district_en',
                      'query', ?, ?, 'The Kathmandu Post',
                      'https://kathmandupost.com', 'Mugu landslide',
                      '2022-10-11T00:00:00+00:00',
                      '2026-08-09T00:00:00+00:00', ?, ?)
            """,
            (
                candidate_id,
                f"seed-{suffix}",
                f"result-{suffix}",
                f"https://news.google.test/{suffix}",
                status,
                f"https://kathmandupost.com/karnali/{suffix}",
            ),
        )
        connection.commit()
    return candidate_id


def test_ingest_accepts_only_relevant_event_and_is_idempotent(config_file: Path) -> None:
    config = load_config(config_file)
    initialize_sqlite(config.sqlite_path)
    accepted = _insert_candidate(config, status="relevant_event", suffix="accepted")
    rejected = _insert_candidate(config, status="relevant_district", suffix="rejected")
    fetcher = FakeFetcher()

    summary = ingest_reviewed_candidates(config, fetcher)

    assert summary["publisher_urls_ingested"] == 1
    assert fetcher.urls == ["https://kathmandupost.com/karnali/accepted"]
    with connect_sqlite(config.sqlite_path) as connection:
        raw = connection.execute("SELECT * FROM raw_articles").fetchone()
        accepted_row = connection.execute(
            "SELECT * FROM external_news_candidates WHERE candidate_id=?", (accepted,)
        ).fetchone()
        rejected_row = connection.execute(
            "SELECT * FROM external_news_candidates WHERE candidate_id=?", (rejected,)
        ).fetchone()
    assert raw["source"] == "kathmandu-post"
    assert raw["method"] == ASSISTED_METHOD
    assert raw["published_date_raw"] == "2022-10-11T00:00:00+00:00"
    assert accepted_row["ingest_status"] == "ingested"
    assert rejected_row["ingest_status"] == "not_ingested"

    second_fetcher = FakeFetcher()
    second = ingest_reviewed_candidates(config, second_fetcher)
    assert second["candidate_rows_selected"] == 0
    assert second_fetcher.urls == []


def test_unconfigured_publisher_gets_stable_domain_slug(config_file: Path) -> None:
    config = load_config(config_file)
    source = source_for_candidate(
        config,
        resolved_url="https://english.khabarhub.com/2022/07/275787/",
        source_name="Khabarhub",
    )
    assert source.slug == "khabarhub"


def test_locked_v3_frame_excludes_bipad_assisted_articles(config_file: Path) -> None:
    config = load_config(config_file)
    initialize_sqlite(config.sqlite_path)
    with connect_sqlite(config.sqlite_path) as connection:
        connection.executemany(
            """
            INSERT INTO raw_articles (
                url, source, title, published_date_ad, text, method
            ) VALUES (?, 'test', 'title', '2022-10-10', 'article text', ?)
            """,
            [
                ("https://example.test/native", "tag"),
                ("https://example.test/assisted", ASSISTED_METHOD),
            ],
        )
        connection.commit()
        frame = load_frame(connection)
    assert DESIGN_VERSION == "v3"
    assert [row.url for row in frame] == ["https://example.test/native"]


def test_external_ingest_stage_is_registered() -> None:
    assert resolve_stage_name("ingest_external") == "external_ingest"
    assert STAGE_HANDLERS["external_ingest"] is run_external_ingest_stage
