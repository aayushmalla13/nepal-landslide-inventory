"""HTML, RSS, official notice, bulletin, and e-paper adapters."""

from __future__ import annotations

import hashlib
import io
import re
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from .base import SourceAdapter, configured_headers, contains_landslide
from .models import ExternalRecord, clean_text, iso_date

DATE_PATTERNS = (
    r"20\d{2}[-/]\d{1,2}[-/]\d{1,2}",
    r"\d{4}[-/]\d{1,2}[-/]\d{1,2}",  # may be Bikram Sambat; preserved as raw only
)


def _extract_date(text: str) -> str | None:
    for pattern in DATE_PATTERNS:
        match = re.search(pattern, text)
        if match:
            return match.group()
    return None


def _extract_pdf_text(body: bytes) -> str | None:
    """Extract PDF text when pypdf is installed; image-only issues remain metadata records."""

    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(body))
        text = " ".join(page.extract_text() or "" for page in reader.pages)
        return clean_text(text)
    except Exception:  # optional parser failures must not abort a multi-year archive run
        return None


def _feed_value(entry: ET.Element, *names: str) -> str | None:
    for name in names:
        node = entry.find(name)
        if node is None:
            node = entry.find(f"{{*}}{name}")
        if node is not None:
            return clean_text(node.text or node.attrib.get("href"))
    return None


class HtmlDocumentsAdapter(SourceAdapter):
    """Generic official bulletin/news/notice listing and detail collector."""

    def collect(self) -> list[ExternalRecord]:
        seeds = self.config.get("listing_urls") or [self.config.get("listing_url")]
        listing_urls = [str(url) for url in seeds if url]
        headers = configured_headers(self.config)
        links: list[str] = []
        allowed_domains = set(self.config.get("allowed_domains", []))
        link_pattern = re.compile(str(self.config.get("link_pattern", ".*")))
        max_listing_pages = int(self.config.get("max_listing_pages", 10))
        visited_listings: set[str] = set()
        while listing_urls and len(visited_listings) < max_listing_pages:
            listing_url = listing_urls.pop(0)
            if listing_url in visited_listings:
                continue
            visited_listings.add(listing_url)
            response = self.client.request(listing_url, headers=headers)
            if not 200 <= response.status < 300:
                continue
            soup = BeautifulSoup(response.text, "html.parser")
            for anchor in soup.select(str(self.config.get("link_selector", "a[href]"))):
                href = anchor.get("href")
                if not href:
                    continue
                url = urljoin(response.url, href)
                if allowed_domains and urlparse(url).netloc not in allowed_domains:
                    continue
                anchor_text = anchor.get_text(" ", strip=True)
                if link_pattern.search(url) and (
                    not self.config.get("filter_listing_links", False)
                    or contains_landslide(f"{anchor_text} {url}")
                ):
                    links.append(url)
            next_selector = str(
                self.config.get("next_selector", "a[rel=next], .pagination .next a, a.next")
            )
            next_anchor = soup.select_one(next_selector)
            if next_anchor and next_anchor.get("href"):
                next_url = urljoin(response.url, next_anchor["href"])
                if not allowed_domains or urlparse(next_url).netloc in allowed_domains:
                    listing_urls.append(next_url)
        unique_links = list(dict.fromkeys(links))[: int(self.config.get("max_documents", 500))]
        records: list[ExternalRecord] = []
        for url in unique_links:
            response = self.client.request(url, headers=headers)
            if not 200 <= response.status < 300:
                continue
            content_type = response.headers.get("content-type", "")
            if "pdf" in content_type or response.body.startswith(b"%PDF"):
                title = url.rsplit("/", 1)[-1]
                text = _extract_pdf_text(response.body)
                medium = "pdf"
            else:
                soup = BeautifulSoup(response.text, "html.parser")
                for node in soup.select("script,style,noscript,nav,footer,header"):
                    node.decompose()
                title_node = soup.select_one(str(self.config.get("title_selector", "h1, title")))
                body_node = soup.select_one(
                    str(
                        self.config.get(
                            "body_selector", "article, main, .entry-content, .post-content, body"
                        )
                    )
                )
                title = title_node.get_text(" ", strip=True) if title_node else None
                text = (
                    body_node.get_text(" ", strip=True)
                    if body_node
                    else soup.get_text(" ", strip=True)
                )
                medium = "html"
            if self.config.get("landslide_only", True) and not contains_landslide(
                f"{title or ''} {text or ''} {url}"
            ):
                continue
            raw_date = _extract_date(f"{title or ''} {text or ''} {url}")
            date_role = self.config.get("date_role", "published")
            records.append(
                ExternalRecord(
                    source=self.source,
                    source_family=str(self.config.get("source_family", "government_bulletin")),
                    record_type=str(self.config.get("record_type", "official_document")),
                    source_record_id=hashlib.sha256(url.encode("utf-8")).hexdigest()[:24],
                    source_url=url,
                    title=clean_text(title),
                    text=clean_text(text),
                    published_at=raw_date,
                    incident_date_raw=raw_date if date_role == "incident" else None,
                    incident_date_ad=iso_date(raw_date) if date_role == "incident" else None,
                    hazard_type="landslide",
                    country="Nepal",
                    retrieval_medium=medium,
                    raw_payload={"url": url, "content_type": content_type},
                )
            )
        return records


class NdrrmaBulletinAdapter(HtmlDocumentsAdapter):
    pass


class NepalPoliceAdapter(HtmlDocumentsAdapter):
    pass


class ArmedPoliceAdapter(HtmlDocumentsAdapter):
    pass


class RoadNoticeAdapter(HtmlDocumentsAdapter):
    pass


class RssAdapter(SourceAdapter):
    """RSS/Atom support for official agency feeds and alert feeds."""

    def collect(self) -> list[ExternalRecord]:
        endpoint = str(self.config["endpoint"])
        response = self.client.request(endpoint, headers=configured_headers(self.config))
        if not 200 <= response.status < 300:
            raise RuntimeError(f"Feed returned HTTP {response.status}")
        root = ET.fromstring(response.body)
        records: list[ExternalRecord] = []
        entries = root.findall(".//item") + root.findall(".//{*}entry")
        for entry in entries:
            title = _feed_value(entry, "title")
            text = _feed_value(entry, "description", "summary", "content")
            if self.config.get("landslide_only", True) and not contains_landslide(
                f"{title or ''} {text or ''}"
            ):
                continue
            link = _feed_value(entry, "link")
            raw_date = _feed_value(entry, "pubDate", "published", "updated")
            records.append(
                ExternalRecord(
                    source=self.source,
                    source_family=str(self.config.get("source_family", "official_feed")),
                    record_type=str(self.config.get("record_type", "feed_item")),
                    source_record_id=_feed_value(entry, "guid", "id") or link,
                    source_url=link,
                    title=title,
                    text=text,
                    published_at=raw_date,
                    hazard_type="landslide",
                    retrieval_medium="rss_atom",
                    raw_payload={"title": title, "link": link, "published": raw_date},
                )
            )
        return records


class KantipurEpaperAdapter(SourceAdapter):
    """Date-based e-paper issue retrieval with session-cookie support."""

    def collect(self) -> list[ExternalRecord]:
        start = date.fromisoformat(str(self.config["start"]))
        end = date.fromisoformat(str(self.config["end"]))
        max_documents = int(self.config.get("max_documents", 100))
        publications = list(self.config.get("publications", ["kantipur", "kathmandupost"]))
        templates = list(
            self.config.get(
                "url_templates", ["https://epaper.ekantipur.com/{publication}/download/{date}"]
            )
        )
        headers = configured_headers(self.config)
        records: list[ExternalRecord] = []
        current = start
        while current <= end and len(records) < max_documents:
            if not self.config.get("monsoon_only", False) or current.month in set(
                self.config.get("months", [6, 7, 8, 9])
            ):
                for publication in publications:
                    for template in templates:
                        url = str(template).format(
                            publication=publication, date=current.isoformat()
                        )
                        try:
                            response = self.client.request(url, headers=headers)
                        except Exception:
                            # Individual issue dates frequently return 5xx or
                            # timeout; skip that date and continue the bounded
                            # historical scan.
                            continue
                        if response.status in (401, 402, 403):
                            cookie_env = self.config.get("cookie_env", "KANTIPUR_EPAPER_COOKIE")
                            raise RuntimeError(
                                f"e-paper access requires a valid session; set {cookie_env}"
                            )
                        if not 200 <= response.status < 300 or len(response.body) < int(
                            self.config.get("minimum_bytes", 1000)
                        ):
                            continue
                        content_type = response.headers.get("content-type", "")
                        text = None
                        if "pdf" in content_type or response.body.startswith(b"%PDF"):
                            text = _extract_pdf_text(response.body)
                        elif "html" in content_type:
                            soup = BeautifulSoup(response.text, "html.parser")
                            text = soup.get_text(" ", strip=True)
                        if (
                            text
                            and self.config.get("landslide_only", True)
                            and not contains_landslide(text)
                        ):
                            continue
                        records.append(
                            ExternalRecord(
                                source=self.source,
                                source_family="news_archive",
                                record_type="epaper_issue",
                                source_record_id=f"{publication}:{current.isoformat()}",
                                source_url=response.url,
                                title=f"{publication} e-paper {current.isoformat()}",
                                text=clean_text(text),
                                published_at=current.isoformat(),
                                incident_date_raw=None,
                                incident_date_ad=None,
                                country="Nepal",
                                retrieval_medium="epaper_pdf"
                                if "pdf" in content_type
                                else "epaper_html",
                                raw_payload={
                                    "publication": publication,
                                    "issue_date": current.isoformat(),
                                    "content_type": content_type,
                                },
                            )
                        )
                        break
                    if len(records) >= max_documents:
                        break
            current += timedelta(days=1)
        return records
