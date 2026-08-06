"""Source metadata helpers."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse
from typing import Any

from .config import AppConfig, EXPECTED_SOURCE_COUNT


@dataclass(frozen=True)
class SourceDefinition:
    """Normalized source configuration."""

    name: str
    slug: str
    language: str
    base_url: str
    discovery: dict[str, Any]
    entry_points: list[dict[str, Any]]


def load_sources(config: AppConfig) -> list[SourceDefinition]:
    """Load and validate the configured sources."""

    sources = [
        SourceDefinition(
            name=str(source["name"]),
            slug=str(source["slug"]),
            language=str(source["language"]),
            base_url=str(source["base_url"]),
            discovery=dict(source["discovery"]),
            entry_points=[dict(entry_point) for entry_point in source["entry_points"]],
        )
        for source in config.sources
    ]
    if len(sources) != EXPECTED_SOURCE_COUNT:
        raise ValueError(f"Expected exactly {EXPECTED_SOURCE_COUNT} sources, found {len(sources)}.")
    return sources


def source_slugs(sources: list[SourceDefinition]) -> list[str]:
    """Return configured source slugs in deterministic order."""

    return sorted(source.slug for source in sources)


def allowed_domains(source: SourceDefinition) -> list[str]:
    """Return the allowed domains for a source."""

    domains = {_hostname(source.base_url)}
    for entry_point in source.entry_points:
        domains.add(_hostname(str(entry_point["url"])))
    return sorted(domain for domain in domains if domain)


def discovery_entry_points(source: SourceDefinition) -> list[dict[str, Any]]:
    """Return deterministic discovery entry points for a source."""

    return sorted(
        (dict(entry_point) for entry_point in source.entry_points),
        key=lambda item: (str(item["kind"]), str(item["url"])),
    )


def _hostname(url: str) -> str:
    """Extract a normalized hostname from a URL."""

    return urlparse(url).netloc.lower()
