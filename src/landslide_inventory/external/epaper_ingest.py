"""Review-gated ingestion of e-paper article URLs."""
from __future__ import annotations

import csv
from pathlib import Path
from urllib.parse import urlparse

from ..config import AppConfig
from ..db import initialize_sqlite, connect_sqlite
from ..scrape.fetcher import HTTPFetcher
from ..scrape.models import DiscoveredUrl
from ..scrape.parser import parse_article_html
from ..scrape.storage import upsert_discovered_url, upsert_raw_article
from ..sources import SourceDefinition

METHOD = "external_epaper_review"

def _source(url: str) -> SourceDefinition:
    parsed = urlparse(url)
    return SourceDefinition("Kathmandu Post", "kathmandu-post", "en", f"{parsed.scheme}://{parsed.netloc}", {"primary": METHOD}, [{"kind": METHOD, "url": url, "pagination": "none"}])

def run_epaper_ingest(config: AppConfig) -> dict[str, int]:
    path = config.resolve_path("outputs_dir") / "epaper_review_queue.csv"
    if not path.exists():
        raise FileNotFoundError(path)
    initialize_sqlite(config.sqlite_path)
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fields = list(reader.fieldnames or [])
    for field in ("ingest_status", "ingest_error"):
        if field not in fields: fields.append(field)
    fetcher = HTTPFetcher.from_config(config)
    selected = ingested = failed = 0
    with connect_sqlite(config.sqlite_path) as db:
        existing = {str(r[0]) for r in db.execute("SELECT url FROM raw_articles WHERE method=?", (METHOD,))}
    for row in rows:
        if row.get("review_status", "").strip() != "relevant_event": continue
        url = row.get("article_url", "").strip()
        if not url or url in existing or row.get("ingest_status") == "ingested": continue
        selected += 1
        try:
            result = fetcher.fetch(url)
            source = _source(url)
            parsed = parse_article_html(source, result.text, url)
            if not 200 <= result.status_code < 300 or not parsed.parse_success or len(parsed.text) < 200:
                raise RuntimeError(f"HTTP {result.status_code} or article parse/text too short ({len(parsed.text)})")
            upsert_discovered_url(config.sqlite_path, DiscoveredUrl(url, source.slug, METHOD, "epaper_review_queue", year_hint=int(row["issue_date"][:4]) if row.get("issue_date") else None))
            upsert_raw_article(config.sqlite_path, source.slug, url, result, parsed, METHOD, "epaper_review_queue")
            row["ingest_status"] = "ingested"; row["ingest_error"] = ""
            existing.add(url); ingested += 1
        except Exception as exc:
            row["ingest_status"] = "failed"; row["ingest_error"] = f"{type(exc).__name__}: {exc}"; failed += 1
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
    return {"candidate_rows_selected": selected, "articles_ingested": ingested, "articles_failed": failed}

def run_external_epaper_ingest_stage(config: AppConfig) -> None:
    summary = run_epaper_ingest(config)
    import logging
    logging.getLogger(__name__).info("E-paper article ingestion complete: %s", summary)
