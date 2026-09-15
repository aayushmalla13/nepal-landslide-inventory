"""Adapter contracts and shared source-normalization helpers."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .http import ExternalHttpClient
from .models import ExternalRecord

LANDSLIDE_TERMS = (
    "landslide",
    "mudslide",
    "debris flow",
    "slope failure",
    "पहिरो",
    "भूस्खलन",
    "ढिस्को",
    "माटो खस",
)


def contains_landslide(text: str | None, terms: Iterable[str] = LANDSLIDE_TERMS) -> bool:
    value = (text or "").casefold()
    return any(term.casefold() in value for term in terms)


def configured_headers(config: dict[str, Any]) -> dict[str, str]:
    """Build headers, resolving secret values only from named env variables."""

    headers = {str(key): str(value) for key, value in config.get("headers", {}).items()}
    for header, env_name in config.get("header_env", {}).items():
        value = os.getenv(str(env_name))
        if value:
            headers[str(header)] = value
    if config.get("bearer_token_env"):
        value = os.getenv(str(config["bearer_token_env"]))
        if value:
            headers["Authorization"] = f"Bearer {value}"
    if config.get("cookie_env"):
        value = os.getenv(str(config["cookie_env"]))
        if value:
            headers["Cookie"] = value
    return headers


@dataclass(frozen=True, slots=True)
class ProbeResult:
    source: str
    adapter: str
    ok: bool
    status: int | None
    message: str


class SourceAdapter(ABC):
    """Base class for independently testable external-source collectors."""

    def __init__(self, source: str, config: dict[str, Any], client: ExternalHttpClient) -> None:
        self.source = source
        self.config = config
        self.client = client

    @abstractmethod
    def collect(self) -> list[ExternalRecord]:
        """Fetch and normalize records from this source."""

    def probe(self) -> ProbeResult:
        if not self.config.get("probe_enabled", True):
            return ProbeResult(
                self.source,
                type(self).__name__,
                False,
                None,
                "probe disabled until a verified endpoint is configured",
            )
        for key in ("token_env", "appname_env"):
            env_name = self.config.get(key)
            if env_name and not os.getenv(str(env_name)):
                return ProbeResult(
                    self.source,
                    type(self).__name__,
                    False,
                    None,
                    f"missing environment variable {env_name}",
                )
        input_path = self.config.get("input_path")
        if input_path:
            path = Path(str(input_path)).expanduser()
            if not path.is_absolute() and self.config.get("config_dir"):
                path = Path(str(self.config["config_dir"])) / path
            found = path.is_file()
            return ProbeResult(
                self.source,
                type(self).__name__,
                found,
                None,
                f"local file {'found' if found else 'missing'}: {path}",
            )
        url = (
            self.config.get("endpoint")
            or self.config.get("listing_url")
            or self.config.get("index_url")
            or self.config.get("collections_endpoint")
        )
        listing_urls = self.config.get("listing_urls", [])
        if not url and listing_urls:
            url = listing_urls[0]
        templates = self.config.get("url_templates", [])
        if not url and templates:
            publications = self.config.get("publications", ["kantipur"])
            url = str(templates[0]).format(
                publication=publications[0], date=self.config.get("start", "2015-01-01")
            )
        if not url:
            return ProbeResult(
                self.source, type(self).__name__, False, None, "no endpoint configured"
            )
        try:
            response = self.client.request(str(url), headers=configured_headers(self.config))
        except Exception as exc:  # a probe must report, not abort all sources
            return ProbeResult(self.source, type(self).__name__, False, None, str(exc))
        ok = 200 <= response.status < 400
        return ProbeResult(
            self.source, type(self).__name__, ok, response.status, f"{len(response.body)} bytes"
        )
