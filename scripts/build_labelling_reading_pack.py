#!/usr/bin/env python3
"""Build a self-contained reading pack for a locked or development label file.

Why this exists
---------------
``locked_test_set_v*_LABEL_HERE.csv`` carries only a short snippet, so an
annotator has to open several hundred URLs to label it. Many of those articles
are years old and some sources have since removed them, which makes the label
set slowly less labellable over time and introduces an avoidable failure mode
mid-way through a labelling session.

This writes a companion file holding the stored article text for each row, keyed
by ``row_id``, so labelling can be done entirely offline from two files side by
side.

It is deliberately a **separate** file. ``score_locked`` verifies that the
protected article metadata in the working label file still matches the blank
reference, so the label file itself must not be touched. Nothing here reads,
writes or reveals any prediction.

Usage::

    PYTHONPATH=src python3 scripts/build_labelling_reading_pack.py \\
        --labels data/outputs/locked_test_set_v7_LABEL_HERE.csv
"""

from __future__ import annotations

import argparse
import csv
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Enough of the article to decide class, district, date, deaths and trigger.
# Nepali disaster copy puts all of that in the first few paragraphs; the tail is
# usually boilerplate or unrelated syndicated items.
TEXT_CHARS = 2500

BOILERPLATE = re.compile(
    r'(?:Subscribe|Login|Resize Text Size|Small Medium Large|Listen)\b[^\n]{0,200}'
)


def tidy(text: str) -> str:
    """Collapse whitespace and strip the site chrome that leads many articles."""

    cleaned = BOILERPLATE.sub(' ', text or '')
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned[:TEXT_CHARS]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--labels", required=True, help="the *_LABEL_HERE.csv file to build a pack for"
    )
    parser.add_argument("--database", default="data/raw_sqlite/landslide_inventory.sqlite")
    parser.add_argument("--out", default="", help="defaults to <labels stem>_reading_pack.csv")
    args = parser.parse_args()

    csv.field_size_limit(sys.maxsize)
    labels_path = ROOT / args.labels
    with labels_path.open("rt", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        print(f"no rows in {labels_path}")
        return 1

    connection = sqlite3.connect(ROOT / args.database)
    connection.row_factory = sqlite3.Row
    texts = {
        row["url"]: row["text"]
        for row in connection.execute("SELECT url, text FROM raw_articles")
    }

    out_name = args.out or labels_path.name.replace("_LABEL_HERE.csv", "_reading_pack.csv")
    out_path = labels_path.with_name(out_name)
    missing = 0
    with out_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["row_id", "route_lang", "source", "year", "url", "title", "article_text"],
        )
        writer.writeheader()
        for row in rows:
            text = texts.get(row.get("url", ""))
            if not text:
                missing += 1
            writer.writerow(
                {
                    "row_id": row.get("row_id", ""),
                    "route_lang": row.get("route_lang", ""),
                    "source": row.get("source", ""),
                    "year": row.get("year", ""),
                    "url": row.get("url", ""),
                    "title": row.get("title", ""),
                    "article_text": tidy(text or ""),
                }
            )

    print(f"wrote {out_path.relative_to(ROOT)} ({len(rows)} rows, {missing} without stored text)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
