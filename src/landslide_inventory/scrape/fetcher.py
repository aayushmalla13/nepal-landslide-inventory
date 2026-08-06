"""HTTP fetching with retry and polite rate limiting."""

from __future__ import annotations

import http.client
import logging
import socket
import time
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..config import AppConfig
from ..utils import utc_now_iso
from .models import FetchResult

LOGGER = logging.getLogger(__name__)


@dataclass
class HTTPFetcher:
    """Simple HTTP fetcher with rate limiting and retry/backoff."""

    user_agent: str
    timeout_seconds: int
    retries: int
    rate_limit_seconds: float
    _last_request_at: float = 0.0

    @classmethod
    def from_config(cls, config: AppConfig) -> "HTTPFetcher":
        runtime = dict(config.raw["runtime"])
        return cls(
            user_agent=str(runtime["user_agent"]),
            timeout_seconds=int(runtime["timeout_seconds"]),
            retries=int(runtime["retries"]),
            rate_limit_seconds=float(runtime["rate_limit_seconds"]),
        )

    def fetch(self, url: str) -> FetchResult:
        """Fetch a URL with retry/backoff."""

        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            self._respect_rate_limit()
            request = Request(url, headers={"User-Agent": self.user_agent})
            try:
                with urlopen(request, timeout=self.timeout_seconds) as response:
                    body = response.read().decode("utf-8", errors="replace")
                    return FetchResult(
                        url=url,
                        status_code=int(response.status),
                        text=body,
                        fetched_at=utc_now_iso(),
                    )
            except HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")
                return FetchResult(
                    url=url,
                    status_code=int(exc.code),
                    text=body,
                    fetched_at=utc_now_iso(),
                )
            except (http.client.IncompleteRead, TimeoutError, socket.timeout, URLError) as exc:
                last_error = exc
                LOGGER.warning("Fetch attempt %s failed for %s: %s", attempt + 1, url, exc)
                time.sleep(2**attempt)
        raise RuntimeError(f"Failed to fetch {url}: {last_error}")

    def _respect_rate_limit(self) -> None:
        """Sleep if needed to satisfy the configured rate limit."""

        elapsed = time.monotonic() - self._last_request_at
        wait_seconds = self.rate_limit_seconds - elapsed
        if wait_seconds > 0:
            time.sleep(wait_seconds)
        self._last_request_at = time.monotonic()
