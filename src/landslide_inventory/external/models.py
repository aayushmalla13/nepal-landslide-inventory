"""Normalized model shared by all external-source adapters."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    """Return a stable UTC timestamp for provenance fields."""

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def clean_text(value: Any) -> str | None:
    """Normalize whitespace and null-like values."""

    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def first_value(payload: dict[str, Any], *paths: str) -> Any:
    """Return the first non-empty value found at a dotted path."""

    for path in paths:
        value: Any = payload
        for part in path.split("."):
            if isinstance(value, dict):
                value = value.get(part)
            else:
                value = None
                break
        if value not in (None, "", [], {}):
            return value
    return None


def as_int(value: Any) -> int | None:
    """Coerce casualty-like values without turning missing into zero."""

    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return int(value)
    match = re.search(r"-?\d+", str(value).replace(",", ""))
    return int(match.group()) if match else None


def as_float(value: Any) -> float | None:
    """Coerce a coordinate to float when possible."""

    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def iso_date(value: Any) -> str | None:
    """Best-effort ISO date normalization while preserving raw date separately."""

    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, int | float):
        # ArcGIS commonly returns epoch milliseconds.
        seconds = float(value) / 1000 if float(value) > 10_000_000_000 else float(value)
        try:
            return datetime.fromtimestamp(seconds, timezone.utc).date().isoformat()
        except (OverflowError, OSError, ValueError):
            return None
    text = str(value).strip()
    match = re.search(
        r"(?P<y>20\d{2})[-/](?P<m>1[0-2]|0?[1-9])[-/]"
        r"(?P<d>3[01]|[12]\d|0?[1-9])(?!\d)",
        text,
    )
    if match:
        try:
            year, month, day = int(match["y"]), int(match["m"]), int(match["d"])
            if year >= 2070:
                from ..preprocess.dates import bs_to_ad

                return bs_to_ad((year, month, day)).isoformat()
            return date(year, month, day).isoformat()
        except ValueError:
            return None
    return None


def stable_json(value: Any) -> str:
    """Serialize raw source data deterministically."""

    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


@dataclass(slots=True)
class ExternalRecord:
    """A provenance-first record from a non-canonical observation system."""

    source: str
    source_family: str
    record_type: str
    source_record_id: str | None = None
    source_url: str | None = None
    title: str | None = None
    text: str | None = None
    published_at: str | None = None
    incident_date_raw: str | None = None
    incident_date_ad: str | None = None
    hazard_type: str | None = None
    country: str | None = "Nepal"
    province: str | None = None
    district: str | None = None
    municipality: str | None = None
    ward: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    deaths: int | None = None
    missing: int | None = None
    injured: int | None = None
    retrieval_medium: str | None = None
    retrieved_at: str = field(default_factory=utc_now_iso)
    raw_payload: Any = field(default_factory=dict)
    record_id: str | None = None
    content_hash: str | None = None

    def finalize(self) -> ExternalRecord:
        """Normalize strings and assign stable identifiers in place."""

        for name in (
            "source",
            "source_family",
            "record_type",
            "source_record_id",
            "source_url",
            "title",
            "text",
            "published_at",
            "incident_date_raw",
            "incident_date_ad",
            "hazard_type",
            "country",
            "province",
            "district",
            "municipality",
            "ward",
            "retrieval_medium",
            "retrieved_at",
        ):
            setattr(self, name, clean_text(getattr(self, name)))
        if not self.incident_date_ad:
            self.incident_date_ad = iso_date(self.incident_date_raw)
        raw = stable_json(self.raw_payload)
        identity = self.source_record_id or self.source_url or raw
        self.record_id = (
            self.record_id
            or hashlib.sha256(f"{self.source}\x1f{identity}".encode()).hexdigest()[:32]
        )
        content = "\x1f".join(filter(None, (self.title, self.text, self.incident_date_ad, raw)))
        self.content_hash = self.content_hash or hashlib.sha256(content.encode("utf-8")).hexdigest()
        return self

    def database_row(self) -> dict[str, Any]:
        """Return values matching the external_records SQLite schema."""

        self.finalize()
        row = asdict(self)
        row["raw_json"] = stable_json(row.pop("raw_payload"))
        return row


def records_to_rows(records: Iterable[ExternalRecord]) -> list[dict[str, Any]]:
    """Finalize an iterable exactly once."""

    return [record.database_row() for record in records]
