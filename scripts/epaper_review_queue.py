"""Build a human-review queue from issue-level e-paper records.

E-paper issues are evidence containers, not article/event rows. This script
extracts bounded keyword context for review without promoting anything into
the canonical inventory.
"""

from __future__ import annotations

import csv
import re
import sqlite3
from pathlib import Path

TERMS = (
    "landslide", "mudslide", "debris flow", "slope failure", "rockfall",
    "पहिरो", "भूस्खलन", "ढिस्को", "माटो खस",
)


def snippets(text: str, radius: int = 240) -> str:
    hits: list[str] = []
    folded = text.casefold()
    for term in TERMS:
        start = 0
        needle = term.casefold()
        while len(hits) < 8:
            index = folded.find(needle, start)
            if index < 0:
                break
            left = max(0, index - radius)
            right = min(len(text), index + len(term) + radius)
            fragment = re.sub(r"\s+", " ", text[left:right]).strip()
            if fragment and fragment not in hits:
                hits.append(fragment)
            start = index + len(term)
    return " || ".join(hits)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    db_path = root / "data/raw_sqlite/landslide_inventory.sqlite"
    output = root / "data/outputs/epaper_review_queue.csv"
    with sqlite3.connect(db_path) as db:
        db.row_factory = sqlite3.Row
        rows = db.execute(
            """
            SELECT record_id, source_record_id, source_url, title, published_at,
                   text, retrieval_medium
            FROM external_records
            WHERE source='kantipur-epaper' AND record_type='epaper_issue'
            ORDER BY published_at, record_id
            """
        ).fetchall()
    fields = [
        "review_id", "record_id", "issue_date", "issue_title", "issue_url",
        "retrieval_medium", "keyword_snippets", "review_status", "article_url",
        "article_date", "district", "municipality", "event_notes", "reviewer",
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                "review_id": f"epaper:{row['record_id']}",
                "record_id": row["record_id"],
                "issue_date": row["published_at"] or "",
                "issue_title": row["title"] or "",
                "issue_url": row["source_url"] or "",
                "retrieval_medium": row["retrieval_medium"] or "",
                "keyword_snippets": snippets(row["text"] or ""),
                "review_status": "",
                "article_url": "",
                "article_date": "",
                "district": "",
                "municipality": "",
                "event_notes": "",
                "reviewer": "",
            })
    print(f"Wrote {len(rows)} issue rows to {output}")


if __name__ == "__main__":
    main()
