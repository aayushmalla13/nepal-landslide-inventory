"""Rate-limited responses must be retried, never stored as article text.

615 of 992 himalayan-times rows -- the MEDIAN row from that outlet -- were HTTP
429 pages saved as articles, because the HTTPError branch returned immediately
instead of retrying. Their body was the literal string "You have exceeded the
rate limit. Please try again later." and nothing downstream consulted
http_status to notice.
"""

from __future__ import annotations

import io
from urllib.error import HTTPError

import pytest

from landslide_inventory.scrape.fetcher import (
    MAX_BACKOFF_SECONDS,
    RETRYABLE_STATUS,
    HTTPFetcher,
)

RATE_LIMIT_BODY = b'You have exceeded the rate limit. Please try again later.'


def _fetcher(retries: int = 2) -> HTTPFetcher:
    return HTTPFetcher(user_agent='test', timeout_seconds=1,
                       retries=retries, rate_limit_seconds=0.0)


def _http_error(status: int, retry_after: str | None = None) -> HTTPError:
    headers = {'Retry-After': retry_after} if retry_after else {}
    return HTTPError('http://x/a', status, 'err', headers, io.BytesIO(RATE_LIMIT_BODY))


def test_429_is_retried_not_accepted(monkeypatch) -> None:
    attempts = []

    def fake_urlopen(request, timeout=None):
        attempts.append(1)
        raise _http_error(429)

    monkeypatch.setattr('landslide_inventory.scrape.fetcher.urlopen', fake_urlopen)
    monkeypatch.setattr('landslide_inventory.scrape.fetcher.time.sleep', lambda s: None)

    result = _fetcher(retries=2).fetch('http://x/a')
    assert len(attempts) == 3, 'must retry, not accept the first 429'
    assert result.status_code == 429


def test_exhausted_rate_limit_stores_no_text(monkeypatch) -> None:
    """The critical guarantee: never persist the error page as article text."""

    monkeypatch.setattr('landslide_inventory.scrape.fetcher.urlopen',
                        lambda r, timeout=None: (_ for _ in ()).throw(_http_error(429)))
    monkeypatch.setattr('landslide_inventory.scrape.fetcher.time.sleep', lambda s: None)

    result = _fetcher(retries=1).fetch('http://x/a')
    assert result.text == '', (
        'a rate-limit page must not be stored as article text; that is how 615 '
        'error pages entered the corpus'
    )
    assert 'exceeded the rate limit' not in result.text


def test_a_retry_that_succeeds_returns_the_real_article(monkeypatch) -> None:
    calls = {'n': 0}

    class _Response:
        status = 200
        def read(self): return b'A landslide killed three in Sindhupalchok.'
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def fake_urlopen(request, timeout=None):
        calls['n'] += 1
        if calls['n'] == 1:
            raise _http_error(429)
        return _Response()

    monkeypatch.setattr('landslide_inventory.scrape.fetcher.urlopen', fake_urlopen)
    monkeypatch.setattr('landslide_inventory.scrape.fetcher.time.sleep', lambda s: None)

    result = _fetcher().fetch('http://x/a')
    assert result.status_code == 200
    assert 'Sindhupalchok' in result.text


def test_404_is_not_retried() -> None:
    """Only 'ask again later' statuses retry; a 404 is a final answer."""

    assert 404 not in RETRYABLE_STATUS
    assert 403 not in RETRYABLE_STATUS
    assert 429 in RETRYABLE_STATUS
    assert 503 in RETRYABLE_STATUS


def test_retry_after_header_is_honoured() -> None:
    fetcher = _fetcher()
    assert fetcher._retry_delay(_http_error(429, retry_after='12'), 0) == 12.0


def test_backoff_is_capped() -> None:
    """One hostile host must not stall an entire run."""

    fetcher = _fetcher()
    assert fetcher._retry_delay(_http_error(429, retry_after='99999'), 0) == MAX_BACKOFF_SECONDS
    assert fetcher._retry_delay(_http_error(429), 20) == MAX_BACKOFF_SECONDS


def test_backoff_grows(monkeypatch) -> None:
    fetcher = _fetcher()
    delays = [fetcher._retry_delay(_http_error(429), i) for i in range(3)]
    assert delays == sorted(delays) and delays[0] < delays[-1]
