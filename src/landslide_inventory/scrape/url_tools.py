"""URL normalization and filtering helpers."""

from __future__ import annotations

from urllib.parse import parse_qsl, quote, unquote, urlencode, urljoin, urlparse, urlunparse

TRACKING_QUERY_PREFIXES = ("utm_",)
TRACKING_QUERY_KEYS = {"fbclid", "gclid", "amp", "output", "click_from"}
REJECT_PATH_PARTS = {
    "page",
    "tag",
    "tags",
    "trend",
    "trends",
    "category",
    "categories",
    "content",
    "segment",
    "pages",
    "from-paper",
    "football",
    "cricket",
    "blog",
    "ghumphir",
    "art-culture",
    "login",
    "signin",
    "search",
    "author",
}


def normalize_url(url: str, base_url: str | None = None) -> str:
    """Normalize article URLs by resolving relative paths and removing tracking noise."""

    candidate = urljoin(base_url or "", url).strip()
    parsed = urlparse(candidate)
    query_items = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key not in TRACKING_QUERY_KEYS and not key.startswith(TRACKING_QUERY_PREFIXES)
    ]
    path = parsed.path.rstrip("/")
    if path.endswith("/amp"):
        path = path[: -len("/amp")]
    path = quote(unquote(path), safe="/%")
    normalized = parsed._replace(
        scheme=parsed.scheme.lower(),
        netloc=parsed.netloc.lower(),
        path=path or "/",
        query=urlencode(query_items, doseq=True),
        fragment="",
    )
    return urlunparse(normalized)


def is_allowed_domain(url: str, allowed_domains: list[str]) -> bool:
    """Return whether the URL host is in the allowed domain set."""

    hostname = urlparse(url).netloc.lower()
    return any(hostname == domain or hostname.endswith(f".{domain}") for domain in allowed_domains)


def looks_like_article_url(url: str, *, allow_single_segment: bool = False) -> bool:
    """Heuristic article URL filter."""

    parsed = urlparse(url)
    path_parts = [part for part in parsed.path.split("/") if part]
    if len(path_parts) < 2 and not allow_single_segment:
        return False
    if path_parts[0].casefold() == 'cdn-cgi':
        return False
    if any(part.casefold() in REJECT_PATH_PARTS for part in path_parts):
        return False
    if parsed.query == "page=1" and len(path_parts) <= 2:
        return False
    return True


def filter_article_url(
    url: str,
    allowed_domains: list[str],
    base_url: str | None = None,
    *,
    allow_single_segment: bool = False,
) -> str | None:
    """Normalize and validate a candidate article URL."""

    normalized = normalize_url(url, base_url=base_url)
    if not is_allowed_domain(normalized, allowed_domains):
        return None
    if not looks_like_article_url(normalized, allow_single_segment=allow_single_segment):
        return None
    return normalized
