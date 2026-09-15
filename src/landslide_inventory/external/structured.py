"""Adapters for JSON, ArcGIS, ReliefWeb, and exported disaster tables."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from .base import ProbeResult, SourceAdapter, configured_headers, contains_landslide
from .models import ExternalRecord, as_float, as_int, clean_text, first_value, iso_date


def _items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("results", "data", "items", "incidents", "features", "documents"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def _coordinates(payload: dict[str, Any]) -> tuple[float | None, float | None]:
    coordinates = first_value(
        payload, "geometry.coordinates", "point.coordinates", "location.point.coordinates"
    )
    if isinstance(coordinates, list | tuple) and len(coordinates) >= 2:
        return as_float(coordinates[0]), as_float(coordinates[1])
    latitude = as_float(
        first_value(payload, "latitude", "lat", "attributes.latitude", "attributes.lat")
    )
    longitude = as_float(
        first_value(payload, "longitude", "lon", "lng", "attributes.longitude", "attributes.lon")
    )
    return longitude, latitude


class GenericJsonAdapter(SourceAdapter):
    """Configurable paginated JSON source used for DRR-style endpoints."""

    def collect(self) -> list[ExternalRecord]:
        endpoint = str(self.config["endpoint"])
        params = dict(self.config.get("params", {}))
        max_pages = int(self.config.get("max_pages", 1))
        page_param = str(self.config.get("page_param", "page"))
        results: list[ExternalRecord] = []
        next_url: str | None = endpoint
        for page in range(1, max_pages + 1):
            page_params = (
                params if page == 1 or next_url != endpoint else {**params, page_param: page}
            )
            payload = self.client.get_json(
                next_url, params=page_params, headers=configured_headers(self.config)
            )
            for item in _items(payload):
                record = self.map_item(item)
                if record:
                    results.append(record)
            next_value = payload.get("next") if isinstance(payload, dict) else None
            if next_value:
                next_url = urljoin(next_url, str(next_value))
                params = {}
            elif page < max_pages and self.config.get("paginate", False):
                next_url = endpoint
            else:
                break
        return results

    def map_item(self, item: dict[str, Any]) -> ExternalRecord | None:
        mapping = self.config.get("mapping", {})

        def mapped(name: str, *defaults: str) -> Any:
            configured = mapping.get(name, [])
            paths = [configured] if isinstance(configured, str) else list(configured)
            return first_value(item, *(paths + list(defaults)))

        title = clean_text(mapped("title", "title", "name", "description", "short_description"))
        text = clean_text(mapped("text", "description", "detail", "body"))
        hazard = clean_text(mapped("hazard_type", "hazard.title", "hazard.name", "hazard", "type"))
        if self.config.get("landslide_only", True) and not contains_landslide(
            " ".join(filter(None, (title, text, hazard)))
        ):
            return None
        longitude, latitude = _coordinates(item)
        raw_date = mapped(
            "incident_date", "incident_on", "occurred_on", "started_on", "event_on", "date"
        )
        return ExternalRecord(
            source=self.source,
            source_family=str(self.config.get("source_family", "government_incident")),
            record_type=str(self.config.get("record_type", "incident")),
            source_record_id=clean_text(mapped("id", "id", "incident_id", "uuid")),
            source_url=clean_text(mapped("url", "url", "detail_url"))
            or self.config.get("public_url"),
            title=title,
            text=text,
            published_at=clean_text(
                mapped("published_at", "published_on", "created_on", "created_at")
            ),
            incident_date_raw=clean_text(raw_date),
            incident_date_ad=iso_date(raw_date),
            hazard_type=hazard,
            country=clean_text(mapped("country", "country.title", "country.name", "country"))
            or "Nepal",
            province=clean_text(mapped("province", "province.title", "province.name", "province")),
            district=clean_text(mapped("district", "district.title", "district.name", "district")),
            municipality=clean_text(
                mapped("municipality", "municipality.title", "municipality.name", "municipality")
            ),
            ward=clean_text(mapped("ward", "ward", "ward_no")),
            longitude=longitude,
            latitude=latitude,
            deaths=as_int(mapped("deaths", "loss.people.death", "people.death", "deaths", "death")),
            missing=as_int(mapped("missing", "loss.people.missing", "people.missing", "missing")),
            injured=as_int(mapped("injured", "loss.people.injured", "people.injured", "injured")),
            retrieval_medium="api",
            raw_payload=item,
        )


class BipadAdapter(GenericJsonAdapter):
    """BIPAD incident API with tolerant field mapping across API revisions."""

    def map_item(self, item: dict[str, Any]) -> ExternalRecord | None:
        """Flatten BIPAD's expanded administrative relationships."""

        normalized = dict(item)
        wards = item.get("wards") or []
        ward = wards[0] if wards and isinstance(wards[0], dict) else {}
        municipality = ward.get("municipality", {})
        municipality = municipality if isinstance(municipality, dict) else {}
        district = municipality.get("district", {})
        district = district if isinstance(district, dict) else {}
        province = district.get("province", {})
        province = province if isinstance(province, dict) else {}
        hazard = item.get("hazard")
        if hazard == 17:
            hazard = "Landslide"
        normalized["bipad"] = {
            "hazard": hazard,
            "ward": ward.get("title"),
            "municipality": municipality.get("title") or municipality.get("titleEn"),
            "district": district.get("title") or district.get("titleEn"),
            "province": province.get("title") or province.get("titleEn"),
        }
        bipad_mapping = {
            "id": ["id"],
            "title": ["title", "titleNe"],
            "text": ["description", "detail"],
            "published_at": ["reportedOn", "createdOn"],
            "incident_date": ["incidentOn"],
            "hazard_type": ["bipad.hazard"],
            "province": ["bipad.province"],
            "district": ["bipad.district"],
            "municipality": ["bipad.municipality"],
            "ward": ["bipad.ward"],
            "deaths": ["loss.peopleDeathCount"],
            "missing": ["loss.peopleMissingCount"],
            "injured": ["loss.peopleInjuredCount"],
        }
        configured_mapping = self.config.get("mapping", {})
        adapter_config = {
            **self.config,
            "mapping": {**bipad_mapping, **configured_mapping},
        }
        return GenericJsonAdapter(self.source, adapter_config, self.client).map_item(normalized)


class DrrPortalAdapter(GenericJsonAdapter):
    """Legacy DRR Portal JSON/export endpoint."""

    pass


class RoadClosureAdapter(SourceAdapter):
    """Department of Roads NAVIGATE road-closure history API."""

    DEFAULT_HAZARD_TERMS = (
        "landslide",
        "mudslide",
        "debris deposited",
        "debris flow",
        "rockfall",
        "rock fall",
        "boulder fall",
        "slope failure",
        "पहिरो",
    )

    def _fetch_page(self, page: int) -> tuple[list[dict[str, Any]], int | None]:
        response = self.client.request(
            str(self.config["endpoint"]),
            json_body={"page": page, **dict(self.config.get("params", {}))},
            headers=configured_headers(self.config),
        )
        if not 200 <= response.status < 300:
            raise RuntimeError(
                f"Road-closure API returned HTTP {response.status}: {response.text[:200]}"
            )
        payload = response.json()
        container = payload.get("data", {}) if isinstance(payload, dict) else {}
        rows = container.get("data", []) if isinstance(container, dict) else []
        items = [row for row in rows if isinstance(row, dict)]
        total_value = container.get("total_rows") if isinstance(container, dict) else None
        try:
            total = int(total_value) if total_value is not None else None
        except (TypeError, ValueError):
            total = None
        return items, total

    def collect(self) -> list[ExternalRecord]:
        max_pages = int(self.config.get("max_pages", 100))
        terms = tuple(self.config.get("hazard_terms", self.DEFAULT_HAZARD_TERMS))
        records: list[ExternalRecord] = []
        rows_seen = 0
        for page in range(1, max_pages + 1):
            items, total = self._fetch_page(page)
            if not items:
                break
            rows_seen += len(items)
            for item in items:
                searchable = " ".join(
                    str(item.get(field) or "")
                    for field in (
                        "closure_reason",
                        "remarks",
                        "efforts_being_made",
                        "road_name",
                    )
                )
                if self.config.get("landslide_only", True) and not contains_landslide(
                    searchable, terms
                ):
                    continue
                normalized = searchable.casefold()
                if any(term in normalized for term in ("rockfall", "rock fall", "boulder")):
                    hazard_type = "rockfall"
                elif any(term in normalized for term in ("debris", "mudslide", "debris flow")):
                    hazard_type = "debris_flow"
                else:
                    hazard_type = "landslide"
                road_name = clean_text(item.get("road_name"))
                reason = clean_text(item.get("closure_reason")) or hazard_type.replace("_", " ")
                details = clean_text(
                    " ".join(
                        str(item.get(field) or "")
                        for field in ("remarks", "efforts_being_made")
                    )
                )
                raw_date = clean_text(item.get("date_roadblock_start"))
                records.append(
                    ExternalRecord(
                        source=self.source,
                        source_family=str(
                            self.config.get("source_family", "official_road_database")
                        ),
                        record_type=str(
                            self.config.get("record_type", "road_obstruction")
                        ),
                        source_record_id=clean_text(item.get("id")),
                        source_url=str(
                            self.config.get(
                                "public_url",
                                "https://navigate.dor.gov.np/app/road-closure-history",
                            )
                        ),
                        title=clean_text(f"{reason} — {road_name or 'Nepal road'}"),
                        text=details,
                        published_at=clean_text(item.get("date_created")),
                        incident_date_raw=raw_date,
                        incident_date_ad=iso_date(raw_date),
                        hazard_type=hazard_type,
                        country="Nepal",
                        district=clean_text(item.get("district")),
                        latitude=as_float(item.get("latitude")),
                        longitude=as_float(item.get("longitude")),
                        retrieval_medium="government_api",
                        raw_payload=item,
                    )
                )
            if total is not None and rows_seen >= total:
                break
        return records

    def probe(self) -> ProbeResult:
        try:
            items, total = self._fetch_page(1)
        except Exception as exc:
            return ProbeResult(self.source, type(self).__name__, False, None, str(exc))
        return ProbeResult(
            self.source,
            type(self).__name__,
            bool(items),
            200,
            f"{len(items)} rows on first page; {total or 'unknown'} total rows",
        )


class ArcGisAdapter(SourceAdapter):
    """ArcGIS FeatureServer adapter, used by NASA COOLR."""

    def collect(self) -> list[ExternalRecord]:
        endpoint = str(self.config["endpoint"]).rstrip("/")
        if not endpoint.endswith("query"):
            endpoint += "/query"
        batch_size = int(self.config.get("batch_size", 1000))
        max_pages = int(self.config.get("max_pages", 10))
        records: list[ExternalRecord] = []
        for page in range(max_pages):
            params = {
                "f": "json",
                "where": self.config.get("where", "1=1"),
                "outFields": "*",
                "returnGeometry": "true",
                "resultOffset": page * batch_size,
                "resultRecordCount": batch_size,
                **self.config.get("params", {}),
            }
            payload = self.client.get_json(
                endpoint, params=params, headers=configured_headers(self.config)
            )
            features = payload.get("features", []) if isinstance(payload, dict) else []
            for feature in features:
                attributes = feature.get("attributes", {})
                merged = {**attributes, "geometry": feature.get("geometry", {})}
                record = self._map_feature(merged)
                if record:
                    records.append(record)
            if len(features) < batch_size and not payload.get("exceededTransferLimit", False):
                break
        return records

    def _map_feature(self, item: dict[str, Any]) -> ExternalRecord | None:
        country = clean_text(first_value(item, "country_name", "country", "Country"))
        if self.config.get("nepal_only", True) and country and country.casefold() != "nepal":
            return None
        hazard = (
            clean_text(first_value(item, "event_type", "landslide_category", "hazard_type"))
            or "landslide"
        )
        longitude, latitude = _coordinates(item)
        geometry = item.get("geometry", {})
        if longitude is None and isinstance(geometry, dict):
            longitude, latitude = as_float(geometry.get("x")), as_float(geometry.get("y"))
        raw_date = first_value(item, "event_date", "eventDate", "date", "Event_Date")
        return ExternalRecord(
            source=self.source,
            source_family=str(self.config.get("source_family", "scientific_observation")),
            record_type=str(self.config.get("record_type", "landslide_observation")),
            source_record_id=clean_text(
                first_value(item, "OBJECTID", "objectid", "event_id", "id")
            ),
            source_url=clean_text(first_value(item, "source_link", "source_url", "url"))
            or self.config.get("public_url"),
            title=clean_text(first_value(item, "event_title", "title", "location_description")),
            text=clean_text(first_value(item, "event_description", "description", "comments")),
            incident_date_raw=clean_text(raw_date),
            incident_date_ad=iso_date(raw_date),
            hazard_type=hazard,
            country=country or "Nepal",
            province=clean_text(first_value(item, "admin_division_name", "province")),
            district=clean_text(first_value(item, "district", "admin2")),
            latitude=latitude,
            longitude=longitude,
            deaths=as_int(first_value(item, "fatality_count", "fatalities", "deaths")),
            retrieval_medium="arcgis_feature_service",
            raw_payload=item,
        )


class ReliefWebAdapter(SourceAdapter):
    """ReliefWeb reports API adapter; appname is supplied via an environment variable."""

    def collect(self) -> list[ExternalRecord]:
        endpoint = str(self.config["endpoint"])
        appname_env = str(self.config.get("appname_env", "RELIEFWEB_APPNAME"))
        import os

        appname = os.getenv(appname_env)
        if not appname:
            raise RuntimeError(f"{appname_env} is required by ReliefWeb")
        limit = int(self.config.get("batch_size", 100))
        max_pages = int(self.config.get("max_pages", 10))
        records: list[ExternalRecord] = []
        for page in range(max_pages):
            body = {
                "limit": limit,
                "offset": page * limit,
                "query": {"value": self.config.get("query", "Nepal landslide")},
                "filter": self.config.get("filter", {"field": "country.name", "value": "Nepal"}),
                "fields": {
                    "include": ["id", "title", "body", "date", "url", "country", "disaster"]
                },
            }
            response = self.client.request(
                endpoint,
                params={"appname": appname},
                json_body=body,
                headers=configured_headers(self.config),
            )
            if not 200 <= response.status < 300:
                raise RuntimeError(
                    f"ReliefWeb returned HTTP {response.status}: {response.text[:200]}"
                )
            payload = response.json()
            items = payload.get("data", [])
            for item in items:
                fields = item.get("fields", {})
                countries = fields.get("country", [])
                country = (
                    countries[0].get("name")
                    if countries and isinstance(countries[0], dict)
                    else "Nepal"
                )
                disasters = fields.get("disaster", [])
                hazard = (
                    disasters[0].get("name")
                    if disasters and isinstance(disasters[0], dict)
                    else "landslide"
                )
                raw_date = (
                    fields.get("date", {}).get("created")
                    if isinstance(fields.get("date"), dict)
                    else fields.get("date")
                )
                records.append(
                    ExternalRecord(
                        source=self.source,
                        source_family="humanitarian_report",
                        record_type="situation_report",
                        source_record_id=clean_text(item.get("id")),
                        source_url=clean_text(fields.get("url")),
                        title=clean_text(fields.get("title")),
                        text=clean_text(fields.get("body")),
                        published_at=clean_text(raw_date),
                        hazard_type=clean_text(hazard),
                        country=clean_text(country),
                        retrieval_medium="api",
                        raw_payload=item,
                    )
                )
            if len(items) < limit:
                break
        return records


class DelimitedExportAdapter(SourceAdapter):
    """CSV/JSON import for DesInventar or an official manually downloaded export."""

    def collect(self) -> list[ExternalRecord]:
        input_path = self.config.get("input_path")
        if input_path:
            path = Path(str(input_path)).expanduser()
            if not path.is_absolute() and self.config.get("config_dir"):
                path = Path(str(self.config["config_dir"])) / path
            body = path.read_bytes()
            source_url = path.resolve().as_uri()
        else:
            response = self.client.request(
                str(self.config["endpoint"]), headers=configured_headers(self.config)
            )
            if not 200 <= response.status < 300:
                raise RuntimeError(f"Export returned HTTP {response.status}")
            body, source_url = response.body, response.url
        if str(input_path or source_url).lower().endswith(".json"):
            payload = json.loads(body.decode("utf-8-sig"))
            items = _items(payload)
        else:
            items = list(csv.DictReader(io.StringIO(body.decode("utf-8-sig", errors="replace"))))
        mapper = GenericJsonAdapter(
            self.source, {**self.config, "endpoint": source_url}, self.client
        )
        return [record for item in items if (record := mapper.map_item(item)) is not None]
