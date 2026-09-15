"""Tests for the isolated external-source ingestion layer."""

from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Any

from landslide_inventory.db import connect_sqlite, initialize_sqlite
from landslide_inventory.external.archives import MediaCloudAdapter, _html_fields, _warc_http_body
from landslide_inventory.external.http import HttpResponse
from landslide_inventory.external.models import ExternalRecord, iso_date
from landslide_inventory.external.storage import export_external_records, upsert_external_records
from landslide_inventory.external.structured import ArcGisAdapter, BipadAdapter, RoadClosureAdapter


class FakeClient:
    def __init__(self, payloads: list[Any]) -> None:
        self.payloads = list(payloads)
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def get_json(self, url: str, **kwargs: Any) -> Any:
        self.calls.append((url, kwargs))
        return self.payloads.pop(0)

    def request(self, url: str, **kwargs: Any) -> HttpResponse:
        self.calls.append((url, kwargs))
        payload = self.payloads.pop(0)
        body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        return HttpResponse(
            url,
            200,
            body,
            {"content-type": "text/html; charset=utf-8"},
            "2026-01-01T00:00:00+00:00",
        )


def test_external_record_has_stable_identity_and_preserves_raw_payload() -> None:
    first = ExternalRecord(
        source="bipad",
        source_family="government",
        record_type="incident",
        source_record_id="42",
        raw_payload={"नेपाली": "पहिरो"},
    ).finalize()
    second = ExternalRecord(
        source="bipad",
        source_family="government",
        record_type="incident",
        source_record_id="42",
        raw_payload={"नेपाली": "पहिरो"},
    ).finalize()
    assert first.record_id == second.record_id
    assert first.content_hash == second.content_hash
    assert "पहिरो" in first.database_row()["raw_json"]


def test_external_date_normalization_converts_bikram_sambat() -> None:
    assert iso_date("2081-03-20") == "2024-07-04"
    assert iso_date("2015-06-12T00:00:00+05:45") == "2015-06-12"


def test_bipad_adapter_paginates_and_filters_non_landslides() -> None:
    client = FakeClient(
        [
            {
                "results": [
                    {
                        "id": 12,
                        "title": "Landslide in Myagdi",
                        "incidentOn": "2024-07-01T10:00:00Z",
                        "hazard": 17,
                        "wards": [
                            {
                                "title": "8",
                                "municipality": {
                                    "title": "Beni Municipality",
                                    "district": {
                                        "title": "Myagdi",
                                        "province": {"title": "Gandaki"},
                                    },
                                },
                            }
                        ],
                        "point": {"coordinates": [83.56, 28.35]},
                        "loss": {"peopleDeathCount": 2, "peopleInjuredCount": 1},
                    },
                    {"id": 13, "title": "House fire", "hazard": {"title": "Fire"}},
                ],
                "next": "https://example.test/incidents?page=2",
            },
            {"results": [], "next": None},
        ]
    )
    adapter = BipadAdapter(
        "bipad",
        {"endpoint": "https://example.test/incidents", "max_pages": 3, "landslide_only": True},
        client,  # type: ignore[arg-type]
    )
    records = adapter.collect()
    assert len(records) == 1
    assert records[0].district == "Myagdi"
    assert records[0].municipality == "Beni Municipality"
    assert records[0].ward == "8"
    assert records[0].province == "Gandaki"
    assert records[0].deaths == 2
    assert records[0].longitude == 83.56
    assert records[0].incident_date_ad == "2024-07-01"
    assert len(client.calls) == 2


def test_arcgis_adapter_maps_coolr_and_stops_on_short_page() -> None:
    client = FakeClient(
        [
            {
                "features": [
                    {
                        "attributes": {
                            "objectid": 7,
                            "event_title": "Nepal landslide mapping",
                            "event_date": 1720137600000,
                            "country_name": "Nepal",
                            "landslide_category": "debris flow",
                            "latitude": 27.7,
                            "longitude": 85.3,
                            "source_link": "https://example.test/source",
                        },
                        "geometry": {},
                    }
                ],
                "exceededTransferLimit": False,
            }
        ]
    )
    records = ArcGisAdapter(
        "nasa-coolr",
        {"endpoint": "https://example.test/FeatureServer/0", "batch_size": 100},
        client,  # type: ignore[arg-type]
    ).collect()
    assert len(records) == 1
    assert records[0].country == "Nepal"
    assert records[0].latitude == 27.7
    assert records[0].record_type == "landslide_observation"
    assert client.calls[0][0].endswith("/query")


def test_road_closure_adapter_paginates_and_keeps_landslide_records() -> None:
    client = FakeClient(
        [
            {
                'data': {
                    'data': [
                        {
                            'id': '637',
                            'date_created': '2026-07-23',
                            'date_roadblock_start': '2026-07-22 23:28:00',
                            'road_name': 'Pushpalal Mid Hill Highway',
                            'closure_reason': 'Landslide',
                            'remarks': 'Landslide due to heavy rainfall',
                            'district': 'Dadeldhura',
                            'latitude': '27.2692',
                            'longitude': '88.0314',
                        },
                        {
                            'id': '636',
                            'date_roadblock_start': '2026-07-18 05:00:00',
                            'road_name': 'National Highway',
                            'closure_reason': 'Scheduled maintenance',
                        },
                    ],
                    'total_rows': '2',
                }
            }
        ]
    )
    adapter = RoadClosureAdapter(
        'dor-navigate',
        {
            'endpoint': 'https://example.test/road-closures',
            'public_url': 'https://example.test/dashboard',
            'max_pages': 5,
        },
        client,  # type: ignore[arg-type]
    )
    records = adapter.collect()
    assert len(records) == 1
    assert records[0].source_record_id == '637'
    assert records[0].record_type == 'road_obstruction'
    assert records[0].incident_date_ad == '2026-07-22'
    assert records[0].district == 'Dadeldhura'
    assert records[0].hazard_type == 'landslide'
    assert client.calls[0][1]['json_body']['page'] == 1


def test_external_storage_is_idempotent_and_exports(tmp_path: Path) -> None:
    database_path = tmp_path / "inventory.sqlite"
    initialize_sqlite(database_path)
    original = ExternalRecord(
        source="bipad",
        source_family="government",
        record_type="incident",
        source_record_id="one",
        title="Original",
        raw_payload={"id": "one"},
    )
    updated = ExternalRecord(
        source="bipad",
        source_family="government",
        record_type="incident",
        source_record_id="one",
        title="Updated",
        raw_payload={"id": "one", "revision": 2},
    )
    assert upsert_external_records(database_path, [original]) == 1
    assert upsert_external_records(database_path, [updated]) == 1
    with connect_sqlite(database_path) as connection:
        row = connection.execute("SELECT COUNT(*) count, title FROM external_records").fetchone()
    assert row["count"] == 1
    assert row["title"] == "Updated"
    output = tmp_path / "external.csv"
    assert export_external_records(database_path, output) == 1
    assert "Updated" in output.read_text(encoding="utf-8")


def test_external_export_applies_study_window_but_keeps_undated(tmp_path: Path) -> None:
    database_path = tmp_path / "inventory.sqlite"
    records = [
        ExternalRecord(
            source="bipad",
            source_family="government",
            record_type="incident",
            source_record_id="old",
            incident_date_ad="2014-07-01",
        ),
        ExternalRecord(
            source="bipad",
            source_family="government",
            record_type="incident",
            source_record_id="inside",
            incident_date_ad="2015-07-01",
        ),
        ExternalRecord(
            source="bulletin",
            source_family="government",
            record_type="document",
            source_record_id="undated",
        ),
    ]
    upsert_external_records(database_path, records)
    output = tmp_path / "study.csv"
    count = export_external_records(
        database_path,
        output,
        start_date="2015-01-01",
        end_date="2026-12-31",
    )
    exported = output.read_text(encoding="utf-8")
    assert count == 2
    assert "inside" in exported
    assert "undated" in exported
    assert "old" not in exported


def test_media_cloud_uses_current_token_pagination_without_event_date(monkeypatch) -> None:
    monkeypatch.setenv("MEDIACLOUD_API_KEY", "test-token")
    client = FakeClient(
        [
            {
                "stories": [
                    {
                        "id": "story-1",
                        "title": "Landslide report",
                        "url": "https://example.test/story-1",
                        "publish_date": "2024-07-02",
                    }
                ],
                "pagination_token": "next-page",
            },
            {"stories": [], "pagination_token": None},
        ]
    )
    records = MediaCloudAdapter(
        "media-cloud",
        {
            "endpoint": "https://search.mediacloud.org/api/search/story-list",
            "token_env": "MEDIACLOUD_API_KEY",
            "start": "2015-01-01",
            "end": "2026-12-31",
            "page_delay_seconds": 0,
        },
        client,  # type: ignore[arg-type]
    ).collect()
    assert len(records) == 1
    assert records[0].published_at == "2024-07-02"
    assert records[0].incident_date_ad is None
    assert client.calls[0][1]["headers"]["Authorization"] == "Token test-token"
    assert client.calls[1][1]["params"]["pagination_token"] == "next-page"


def test_common_crawl_warc_range_extracts_embedded_html() -> None:
    html = b"<html><title>Nepal landslide</title><body>Debris flow in Myagdi.</body></html>"
    record = (
        b"WARC/1.0\r\nContent-Type: application/http; msgtype=response\r\n\r\n"
        b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n" + html
    )
    title, text = _html_fields(_warc_http_body(gzip.compress(record)))
    assert title == "Nepal landslide"
    assert text == "Debris flow in Myagdi."
