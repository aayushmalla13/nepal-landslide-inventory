"""Small injectable HTTP client for external-source adapters."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .models import utc_now_iso


@dataclass(frozen=True, slots=True)
class HttpResponse:
    url: str
    status: int
    body: bytes
    headers: dict[str, str]
    retrieved_at: str

    @property
    def text(self) -> str:
        content_type = self.headers.get("content-type", "")
        charset = "utf-8"
        if "charset=" in content_type:
            charset = content_type.split("charset=", 1)[1].split(";", 1)[0].strip()
        return self.body.decode(charset, errors="replace")

    def json(self) -> Any:
        return json.loads(self.text)


class ExternalHttpClient:
    """HTTP GET/POST with bounded retries and no hidden authentication."""

    def __init__(
        self,
        *,
        user_agent: str,
        timeout_seconds: float = 30,
        retries: int = 3,
        rate_limit_seconds: float = 0,
    ) -> None:
        self.user_agent = user_agent
        self.timeout_seconds = timeout_seconds
        self.retries = max(1, retries)
        self.rate_limit_seconds = max(0, rate_limit_seconds)

    def request(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        json_body: Any = None,
        method: str | None = None,
    ) -> HttpResponse:
        if params:
            query = urlencode(
                [
                    (key, item)
                    for key, value in params.items()
                    for item in (value if isinstance(value, list) else [value])
                    if item is not None
                ]
            )
            url = f"{url}{'&' if '?' in url else '?'}{query}"
        request_headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json,text/html,application/pdf;q=0.9,*/*;q=0.8",
        }
        request_headers.update(headers or {})
        data = None
        if json_body is not None:
            data = json.dumps(json_body, ensure_ascii=False).encode("utf-8")
            request_headers["Content-Type"] = "application/json"
        chosen_method = method or ("POST" if data is not None else "GET")
        last_error: Exception | None = None
        for attempt in range(self.retries):
            try:
                request = Request(url, data=data, headers=request_headers, method=chosen_method)
                with urlopen(request, timeout=self.timeout_seconds) as response:
                    result = HttpResponse(
                        url=response.geturl(),
                        status=int(response.status),
                        body=response.read(),
                        headers={key.lower(): value for key, value in response.headers.items()},
                        retrieved_at=utc_now_iso(),
                    )
                if self.rate_limit_seconds:
                    time.sleep(self.rate_limit_seconds)
                return result
            except HTTPError as exc:
                last_error = exc
                if exc.code < 500 and exc.code != 429:
                    body = exc.read()
                    return HttpResponse(
                        url,
                        exc.code,
                        body,
                        {key.lower(): value for key, value in exc.headers.items()},
                        utc_now_iso(),
                    )
            except (URLError, TimeoutError, OSError) as exc:
                last_error = exc
            if attempt + 1 < self.retries:
                time.sleep(min(2**attempt, 8))
        raise RuntimeError(
            f"HTTP request failed after {self.retries} attempts: {url}: {last_error}"
        )

    def get_json(self, url: str, **kwargs: Any) -> Any:
        response = self.request(url, **kwargs)
        if not 200 <= response.status < 300:
            raise RuntimeError(f"HTTP {response.status} for {response.url}")
        return response.json()
