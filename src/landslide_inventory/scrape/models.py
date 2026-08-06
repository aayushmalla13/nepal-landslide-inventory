"""Data models for scraping."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DiscoveredUrl:
    """Metadata for a discovered article URL."""

    url: str
    source: str
    method: str
    entry_point: str
    query_term: str | None = None
    year_hint: int | None = None


@dataclass(frozen=True)
class FetchResult:
    """HTTP fetch result."""

    url: str
    status_code: int
    text: str
    fetched_at: str


@dataclass(frozen=True)
class ParsedArticle:
    """Parsed article payload."""

    title: str | None
    published_date_raw: str | None
    text: str
    parse_success: bool
