"""Tests for external-to-canonical gap analysis."""

from __future__ import annotations

import json
import csv
from datetime import date
from pathlib import Path

from landslide_inventory.config import load_config
from landslide_inventory.db import connect_sqlite, initialize_sqlite
from landslide_inventory.external.match import (
    _integer,
    load_canonical_news,
    run_external_match_stage,
)
from landslide_inventory.external.models import ExternalRecord
from landslide_inventory.external.storage import upsert_external_records
from landslide_inventory.run import STAGE_HANDLERS, resolve_stage_name


def test_integer_preserves_casualty_counts() -> None:
    assert _integer(2) == 2
    assert _integer("3") == 3
    assert _integer("") is None
    assert _integer("unknown") is None


def test_bipad_assisted_articles_are_excluded_from_bipad_agreement(config_file: Path) -> None:
    config = load_config(config_file)
    initialize_sqlite(config.sqlite_path)
    with connect_sqlite(config.sqlite_path) as connection:
        for suffix, method in (("native", "tag"), ("assisted", "external_seed_bipad")):
            url = f"https://example.test/{suffix}"
            connection.execute(
                "INSERT INTO raw_articles (url, source, method) VALUES (?, 'test', ?)",
                (url, method),
            )
            connection.execute(
                """
                INSERT INTO canonical_events (
                    event_id, dedup_cluster_id, event_date_ad, district, event_payload
                ) VALUES (?, ?, '2024-07-10', 'Dhading', ?)
                """,
                (
                    suffix,
                    f"cluster-{suffix}",
                    json.dumps({"representative_url": url, "urls": [url]}),
                ),
            )
        connection.commit()

    events, _details = load_canonical_news(
        config.sqlite_path,
        date(2015, 1, 1),
        date(2026, 12, 31),
    )

    assert [event.event_id for event in events] == ["native"]


def _insert_news(config) -> None:
    with connect_sqlite(config.sqlite_path) as connection:
        connection.execute(
            """
            INSERT INTO canonical_events (
                event_id, dedup_cluster_id, event_date_ad, district, municipality,
                event_payload
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "news-1",
                "cluster-1",
                "2024-07-10",
                "Dhading",
                "Benighat Rorang Rural Municipality",
                json.dumps({"representative_url": "https://example.test/news-1"}),
            ),
        )
        # This mutable-DB-only event must never enter the released comparison.
        connection.execute(
            """
            INSERT INTO canonical_events (
                event_id, dedup_cluster_id, event_date_ad, district, municipality,
                event_payload
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "db-only",
                "cluster-db-only",
                "2024-07-11",
                "Dhading",
                "Gajuri Rural Municipality",
                json.dumps({"representative_url": "https://example.test/db-only"}),
            ),
        )
        connection.execute(
            """
            INSERT INTO article_events (
                extracted_event_id, article_url, event_class, event_payload,
                url, source, title, class, event_date_ad, district,
                municipality, deaths
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "article-1",
                "https://example.test/news-1",
                1,
                "{}",
                "https://example.test/news-1",
                "test",
                "Dhading landslide",
                1,
                "2024-07-10",
                "Dhading",
                "Benighat Rorang",
                1,
            ),
        )
        connection.commit()


def test_external_match_stage_writes_gaps_and_groups_coolr(config_file: Path) -> None:
    config = load_config(config_file)
    config.raw["external_sources"] = {"matching": {"permutations": 2}}
    initialize_sqlite(config.sqlite_path)
    _insert_news(config)
    canonical_path = config.resolve_path("outputs_dir") / "canonical_events_final.csv"
    canonical_path.parent.mkdir(parents=True, exist_ok=True)
    with canonical_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "event_id", "event_date_ad", "district", "municipality", "deaths",
                "missing", "injured", "representative_title", "representative_url",
                "event_payload",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "event_id": "news-1",
                "event_date_ad": "2024-07-10",
                "district": "Dhading",
                "municipality": "Benighat Rorang",
                "deaths": 1,
                "representative_title": "Dhading landslide",
                "representative_url": "https://example.test/news-1",
                "event_payload": json.dumps(
                    {"urls": ["https://example.test/news-1"]}
                ),
            }
        )
    config.raw.setdefault("analysis", {})["canonical_events_path"] = str(canonical_path)
    records = [
        ExternalRecord(
            source="bipad",
            source_family="government_incident",
            record_type="incident",
            source_record_id="b1",
            incident_date_ad="2024-07-10",
            district="Dhading",
            municipality="Benighat Rorang",
            deaths=1,
            title="Matching BIPAD incident",
            raw_payload={"hazard": 17},
        ),
        ExternalRecord(
            source="bipad",
            source_family="government_incident",
            record_type="incident",
            source_record_id="b2",
            incident_date_ad="2024-08-20",
            district="Myagdi",
            municipality="Beni",
            deaths=2,
            title="Unmatched BIPAD incident",
            raw_payload={"hazard": 17},
        ),
        ExternalRecord(
            source="bipad",
            source_family="government_incident",
            record_type="incident",
            source_record_id="b3",
            incident_date_ad="2024-07-14",
            district="Dhading",
            municipality="Gajuri",
            deaths=0,
            title="Weak date-window candidate",
            raw_payload={"hazard": 17},
        ),
        ExternalRecord(
            source="nasa-coolr",
            source_family="scientific_observation",
            record_type="landslide_observation",
            source_record_id="c1",
            incident_date_ad="2022-10-13",
            latitude=29.1,
            longitude=81.8,
            raw_payload={
                "event_title": "Automated Nepal inventory",
                "source_name": "Kathmandu Post",
                "method": "Automatic",
                "landslide_category": "landslide",
                "location_description": "Karnali Province, Nepal",
                "citation": "Example citation",
            },
        ),
        ExternalRecord(
            source="nasa-coolr",
            source_family="scientific_observation",
            record_type="landslide_observation",
            source_record_id="c2",
            incident_date_ad="2022-10-13",
            latitude=29.2,
            longitude=81.9,
            raw_payload={
                "event_title": "Automated Nepal inventory",
                "source_name": "Kathmandu Post",
                "method": "Automatic",
                "landslide_category": "landslide",
                "location_description": "Karnali Province, Nepal",
                "citation": "Example citation",
            },
        ),
    ]
    upsert_external_records(config.sqlite_path, records)

    run_external_match_stage(config)

    output_dir = config.resolve_path("outputs_dir")
    seeds = (output_dir / "external_search_seeds.csv").read_text(encoding="utf-8")
    assert "Unmatched BIPAD incident" in seeds
    assert "Weak date-window candidate" in seeds
    assert "Matching BIPAD incident" not in seeds
    coolr = (output_dir / "external_coolr_inventories.csv").read_text(encoding="utf-8")
    assert "Automated Nepal inventory" in coolr
    assert ",2," in coolr
    report = (output_dir / "external_match_report.md").read_text(encoding="utf-8")
    assert "Canonical news events: 1" in report
    assert "Frozen canonical CSV SHA-256:" in report
    assert "BIPAD clusters with a strong A/B match: 1" in report
    assert "Mapped polygon features: 2" in report
    agreement = json.loads((output_dir / "external_agreement.json").read_text(encoding="utf-8"))
    assert agreement["comparison_end"] == "2024-08-20"
    assert agreement["layer2_overlap"]["news_total"] == 1
    assert agreement["canonical_input"]["path"] == "data/outputs/canonical_events_final.csv"


def test_external_match_stage_is_registered() -> None:
    assert resolve_stage_name("match_external") == "external_match"
    assert STAGE_HANDLERS["external_match"] is run_external_match_stage
