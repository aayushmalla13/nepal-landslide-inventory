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

# Statuses that mean "ask again later", not "this is the content".
# 429 is the one that mattered: 615 himalayan-times rows were rate-limit pages
# stored as articles because HTTPError returned without retrying.
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})

# Cap the backoff so one hostile host cannot stall a whole run.
MAX_BACKOFF_SECONDS = 60.0


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
                status = int(exc.code)
                # RETRY on rate limiting and server errors.
                #
                # This branch used to return immediately for every HTTPError,
                # so a 429 was treated as the site's final answer and its error
                # page ("You have exceeded the rate limit. Please try again
                # later.", 57 characters) was stored as the article body. That
                # is how 615 of 992 himalayan-times rows -- the MEDIAN row from
                # that outlet -- became error pages masquerading as news, and
                # nothing downstream consulted http_status to notice.
                if status in RETRYABLE_STATUS and attempt < self.retries:
                    delay = self._retry_delay(exc, attempt)
                    LOGGER.warning(
                        "HTTP %s for %s; backing off %.1fs (attempt %s of %s)",
                        status, url, delay, attempt + 1, self.retries,
                    )
                    time.sleep(delay)
                    continue
                if status in RETRYABLE_STATUS:
                    LOGGER.error(
                        "HTTP %s for %s after %s attempts; storing NO text so the "
                        "row is not mistaken for an article", status, url, self.retries + 1,
                    )
                    # Empty text, not the error page. A row with a non-200 status
                    # and no body is unambiguously a failed fetch to re-try later.
                    body = ""
                return FetchResult(
                    url=url,
                    status_code=status,
                    text=body,
                    fetched_at=utc_now_iso(),
                )
            except (http.client.IncompleteRead, TimeoutError, socket.timeout, URLError) as exc:
                last_error = exc
                LOGGER.warning("Fetch attempt %s failed for %s: %s", attempt + 1, url, exc)
                time.sleep(2**attempt)
        raise RuntimeError(f"Failed to fetch {url}: {last_error}")

    def _retry_delay(self, exc: HTTPError, attempt: int) -> float:
        """Seconds to wait, honouring Retry-After when the server sends it.

        A server that says how long to wait is telling you something more
        useful than exponential backoff guesses.
        """

        header = exc.headers.get("Retry-After") if exc.headers else None
        if header:
            try:
                return min(float(header), MAX_BACKOFF_SECONDS)
            except (TypeError, ValueError):
                pass
        return min(2.0 ** (attempt + 1), MAX_BACKOFF_SECONDS)

    def _respect_rate_limit(self) -> None:
        """Sleep if needed to satisfy the configured rate limit."""

        elapsed = time.monotonic() - self._last_request_at
        wait_seconds = self.rate_limit_seconds - elapsed
        if wait_seconds > 0:
            time.sleep(wait_seconds)
        self._last_request_at = time.monotonic()
