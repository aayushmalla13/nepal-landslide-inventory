"""Adapters for web archives and media-search indexes."""

from __future__ import annotations

import gzip
import json
import os
import time
from typing import Any

from bs4 import BeautifulSoup

from .base import SourceAdapter, configured_headers, contains_landslide
from .models import ExternalRecord, clean_text, first_value


def _html_fields(body: bytes) -> tuple[str | None, str | None]:
    soup = BeautifulSoup(body.decode("utf-8", errors="replace"), "html.parser")
    for node in soup.select("script,style,noscript,nav,footer,header"):
        node.decompose()
    title_node = soup.select_one("h1, title")
    body_node = soup.select_one("article, main, body")
    title = title_node.get_text(" ", strip=True) if title_node else None
    text = body_node.get_text(" ", strip=True) if body_node else soup.get_text(" ", strip=True)
    return clean_text(title), clean_text(text)


def _warc_http_body(record: bytes) -> bytes:
    """Extract the embedded HTTP entity from a Common Crawl WARC range."""

    try:
        record = gzip.decompress(record)
    except gzip.BadGzipFile:
        pass
    _, separator, http_record = record.partition(b"\r\n\r\n")
    if not separator:
        return b""
    _, separator, body = http_record.partition(b"\r\n\r\n")
    return body if separator else b""


class WaybackCdxAdapter(SourceAdapter):
    """Internet Archive CDX discovery records (not duplicated article bodies)."""

    def collect(self) -> list[ExternalRecord]:
        endpoint = str(self.config.get("endpoint", "https://web.archive.org/cdx/search/cdx"))
        fields = ["timestamp", "original", "statuscode", "mimetype", "digest"]
        params: dict[str, Any] = {
            "url": self.config["url_pattern"],
            "output": "json",
            "fl": ",".join(fields),
            "filter": self.config.get("filters", ["statuscode:200", "mimetype:text/html"]),
            "collapse": self.config.get("collapse", "digest"),
            "limit": int(self.config.get("limit", 5000)),
        }
        if self.config.get("from"):
            params["from"] = self.config["from"]
        if self.config.get("to"):
            params["to"] = self.config["to"]
        payload = self.client.get_json(
            endpoint, params=params, headers=configured_headers(self.config)
        )
        if not payload:
            return []
        header, *rows = payload
        records: list[ExternalRecord] = []
        fetch_bodies = bool(self.config.get("fetch_bodies", False))
        body_limit = int(self.config.get("max_body_fetches", 200))
        for row in rows:
            if fetch_bodies and len(records) >= body_limit:
                break
            item = dict(zip(header, row, strict=False))
            timestamp = str(item.get("timestamp", ""))
            original = clean_text(item.get("original"))
            capture_url = (
                f"https://web.archive.org/web/{timestamp}id_/{original}"
                if timestamp and original
                else original
            )
            raw_date = (
                f"{timestamp[:4]}-{timestamp[4:6]}-{timestamp[6:8]}"
                if len(timestamp) >= 8
                else None
            )
            title, text = original, None
            medium = "wayback_cdx"
            if fetch_bodies and capture_url:
                try:
                    response = self.client.request(capture_url, headers=configured_headers(self.config))
                except Exception:
                    # Archive captures are routinely unavailable or TLS-flaky;
                    # keep the metadata record and continue the bounded batch.
                    continue
                if not 200 <= response.status < 300:
                    continue
                title, text = _html_fields(response.body)
                if self.config.get("landslide_only", True) and not contains_landslide(
                    f"{title or ''} {text or ''}"
                ):
                    continue
                medium = "wayback_capture_html"
            records.append(
                ExternalRecord(
                    source=self.source,
                    source_family="web_archive",
                    record_type="archived_url",
                    source_record_id=clean_text(f"{timestamp}:{item.get('digest', '')}:{original}"),
                    source_url=capture_url,
                    title=title,
                    text=text,
                    published_at=raw_date,
                    retrieval_medium=medium,
                    raw_payload=item,
                )
            )
        return records


class CommonCrawlAdapter(SourceAdapter):
    """Common Crawl URL index discovery, with an optional configured index."""

    def collect(self) -> list[ExternalRecord]:
        index_url = self.config.get("index_url")
        if not index_url:
            collection_url = str(
                self.config.get(
                    "collections_endpoint", "https://index.commoncrawl.org/collinfo.json"
                )
            )
            collections = self.client.get_json(collection_url)
            if not collections:
                return []
            index_url = collections[0]["cdx-api"]
        params: dict[str, Any] = {
            "url": self.config["url_pattern"],
            "output": "json",
            "filter": self.config.get("filters", ["status:200", "mime:text/html"]),
            "collapse": self.config.get("collapse", "digest"),
        }
        response = self.client.request(
            str(index_url), params=params, headers=configured_headers(self.config)
        )
        if not 200 <= response.status < 300:
            raise RuntimeError(f"Common Crawl index returned HTTP {response.status}")
        records: list[ExternalRecord] = []
        limit = int(self.config.get("limit", 5000))
        fetch_bodies = bool(self.config.get("fetch_bodies", False))
        body_limit = int(self.config.get("max_body_fetches", 200))
        for line in response.text.splitlines()[:limit]:
            if fetch_bodies and len(records) >= body_limit:
                break
            if not line.strip():
                continue
            item = json.loads(line)
            timestamp = str(item.get("timestamp", ""))
            raw_date = (
                f"{timestamp[:4]}-{timestamp[4:6]}-{timestamp[6:8]}"
                if len(timestamp) >= 8
                else None
            )
            title, text = clean_text(item.get("url")), None
            medium = "common_crawl_index"
            if fetch_bodies:
                filename = item.get("filename")
                offset = int(item.get("offset", 0))
                length = int(item.get("length", 0))
                if not filename or length <= 0:
                    continue
                warc_url = f"https://data.commoncrawl.org/{filename}"
                try:
                    warc_response = self.client.request(
                        warc_url,
                        headers={
                            **configured_headers(self.config),
                            "Range": f"bytes={offset}-{offset + length - 1}",
                        },
                    )
                except Exception:
                    continue
                if warc_response.status not in (200, 206):
                    continue
                title, text = _html_fields(_warc_http_body(warc_response.body))
                if self.config.get("landslide_only", True) and not contains_landslide(
                    f"{title or ''} {text or ''}"
                ):
                    continue
                medium = "common_crawl_warc"
            records.append(
                ExternalRecord(
                    source=self.source,
                    source_family="web_archive",
                    record_type="crawl_capture",
                    source_record_id=clean_text(f"{item.get('digest', '')}:{item.get('url', '')}"),
                    source_url=clean_text(item.get("url")),
                    title=title,
                    text=text,
                    published_at=raw_date,
                    retrieval_medium=medium,
                    raw_payload=item,
                )
            )
        return records

    def probe(self):
        self.config.setdefault(
            "collections_endpoint", "https://index.commoncrawl.org/collinfo.json"
        )
        return super().probe()


class MediaCloudAdapter(SourceAdapter):
    """Media Cloud story search; the token is read from an environment variable."""

    def collect(self) -> list[ExternalRecord]:
        token_env = str(self.config.get("token_env", "MEDIACLOUD_API_KEY"))
        token = os.getenv(token_env)
        if not token:
            raise RuntimeError(f"{token_env} is required by Media Cloud")
        endpoint = str(self.config["endpoint"])
        headers = {**configured_headers(self.config), "Authorization": f"Token {token}"}
        params = {
            "q": self.config.get("query", "landslide Nepal OR पहिरो"),
            "start": self.config.get("start"),
            "end": self.config.get("end"),
            "platform": self.config.get("platform", "onlinenews-mediacloud"),
            "page_size": int(self.config.get("batch_size", 100)),
            **self.config.get("params", {}),
        }
        if self.config.get("collection_ids"):
            params["cs"] = ",".join(str(value) for value in self.config["collection_ids"])
        if self.config.get("source_ids"):
            params["ss"] = ",".join(str(value) for value in self.config["source_ids"])
        records: list[ExternalRecord] = []
        max_pages = int(self.config.get("max_pages", 10))
        for _ in range(max_pages):
            payload = self.client.get_json(endpoint, params=params, headers=headers)
            items = payload.get("stories") or []
            for item in items:
                raw_date = first_value(item, "publish_date", "published_at", "date")
                records.append(
                    ExternalRecord(
                        source=self.source,
                        source_family="media_index",
                        record_type="indexed_story",
                        source_record_id=clean_text(
                            first_value(item, "id", "story_id", "stories_id")
                        ),
                        source_url=clean_text(first_value(item, "url", "link")),
                        title=clean_text(first_value(item, "title", "name")),
                        text=clean_text(first_value(item, "text", "description")),
                        published_at=clean_text(raw_date),
                        hazard_type="landslide",
                        country="Nepal",
                        retrieval_medium="media_search_api",
                        raw_payload=item,
                    )
                )
            next_value = payload.get("pagination_token")
            if not next_value or not items:
                break
            params["pagination_token"] = str(next_value)
            delay = float(self.config.get("page_delay_seconds", 30))
            if delay:
                time.sleep(delay)
        return records
