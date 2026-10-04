#!/usr/bin/env python3
"""Build an unapplied, corpus-wide v1.2 event-typing repair plan.

The v1.1 candidate inherited already-populated typing columns from v1.0, so
the export completeness gate could not detect that the current classifier had
never been applied.  This script recomputes every release row from the frozen
article corpus.  It does not modify or promote a release.

Human-reviewed event/hazard corrections remain authoritative.  Granularity,
article role, and extraction basis are always recomputed because those fields
were not part of the v1.1 structured-attribute review.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import inspect
import json
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any

from landslide_inventory.unify import event_typing as typing_module
from landslide_inventory.unify.event_typing import (
    GRANULARITY_MULTI,
    GRANULARITY_ROUNDUP,
    classify_event_type,
)
from landslide_inventory.unify.event_typing_stage import refine_hazard_from_members


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RELEASE = (
    ROOT / "data/releases/nepal_landslide_inventory_v1.1.0_candidate_20260928"
)
DEFAULT_ARTICLE_DB = (
    ROOT
    / "data/releases/nepal_landslide_inventory_v1.0.0_candidate_20260927"
    / "landslide_inventory.sqlite"
)
DEFAULT_PLAN = ROOT / "data/outputs/v12_global_typing_plan.csv"
DEFAULT_SUMMARY = ROOT / "data/outputs/v12_global_typing_plan_summary.json"

PLAN_COLUMNS = [
    "event_id",
    "representative_url",
    "cluster_article_count",
    "old_event_type",
    "new_event_type",
    "old_hazard_type",
    "new_hazard_type",
    "old_event_granularity",
    "new_event_granularity",
    "old_article_role",
    "new_article_role",
    "old_extraction_basis",
    "new_extraction_basis",
    "typing_reason",
    "event_type_source",
    "hazard_type_source",
    "changed_fields_json",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PLAN_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def classifier_sha256() -> str:
    source = inspect.getsource(typing_module).encode("utf-8")
    return hashlib.sha256(source).hexdigest()


def parse_urls(row: dict[str, str]) -> list[str]:
    try:
        payload = json.loads(row.get("event_payload") or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError(f"{row['event_id']}: invalid event_payload") from exc
    urls = payload.get("urls") or [row.get("representative_url", "")]
    if not isinstance(urls, list):
        raise ValueError(f"{row['event_id']}: payload urls are not a list")
    clean = [str(url).strip() for url in urls if str(url).strip()]
    if not clean:
        raise ValueError(f"{row['event_id']}: no article URL available for retyping")
    return list(dict.fromkeys(clean))


def reviewed_fields(application_log: Path) -> dict[str, set[str]]:
    reviewed: dict[str, set[str]] = {}
    for row in read_csv(application_log):
        if row.get("action") != "correct_attributes":
            continue
        event_id = row.get("event_id", "").strip()
        try:
            fields = json.loads(row.get("changed_fields_json") or "[]")
        except json.JSONDecodeError as exc:
            raise ValueError(f"{event_id}: invalid changed_fields_json") from exc
        reviewed.setdefault(event_id, set()).update(str(field) for field in fields)
    return reviewed


def load_articles(database: Path, urls: set[str]) -> dict[str, dict[str, Any]]:
    placeholders = ",".join("?" for _ in urls)
    query = f"""
        SELECT ae.url, ae.title, COALESCE(r.text, '') AS text
        FROM article_events AS ae
        LEFT JOIN raw_articles AS r ON r.url = ae.url
        WHERE ae.url IN ({placeholders})
    """
    with sqlite3.connect(database) as connection:
        connection.row_factory = sqlite3.Row
        records = connection.execute(query, tuple(sorted(urls))).fetchall()
    articles = {str(record["url"]): dict(record) for record in records}
    missing = sorted(urls - set(articles))
    if missing:
        raise ValueError(f"Frozen article corpus lacks {len(missing)} URLs: {missing[:3]}")
    return articles


def optional_int(raw: str) -> int | None:
    value = (raw or "").strip()
    return int(value) if value else None


def cluster_typing(
    row: dict[str, str], articles: dict[str, dict[str, Any]], urls: list[str]
):
    representative_url = row.get("representative_url", "").strip() or urls[0]
    representative = articles[representative_url]
    result = classify_event_type(
        representative.get("title"),
        representative.get("text"),
        optional_int(row.get("deaths", "")),
        optional_int(row.get("missing", "")),
        optional_int(row.get("injured", "")),
    )
    member_types = [
        classify_event_type(article.get("title"), article.get("text"))
        for article in (articles[url] for url in urls)
    ]
    result = refine_hazard_from_members(
        result, {member.hazard_type for member in member_types}
    )
    granularities = {member.event_granularity for member in member_types}
    if GRANULARITY_ROUNDUP in granularities:
        result = result.__class__(
            result.event_type,
            result.extraction_basis,
            result.reason,
            result.hazard_type,
            GRANULARITY_ROUNDUP,
            result.article_role,
        )
    elif GRANULARITY_MULTI in granularities:
        result = result.__class__(
            result.event_type,
            result.extraction_basis,
            result.reason,
            result.hazard_type,
            GRANULARITY_MULTI,
            result.article_role,
        )
    return result


def build_plan(
    release_rows: list[dict[str, str]],
    articles: dict[str, dict[str, Any]],
    human_reviewed: dict[str, set[str]],
) -> list[dict[str, Any]]:
    plan: list[dict[str, Any]] = []
    for row in release_rows:
        urls = parse_urls(row)
        result = cluster_typing(row, articles, urls)
        protected = human_reviewed.get(row["event_id"], set())
        new_event_type = (
            row["event_type"] if "event_type" in protected else result.event_type
        )
        new_hazard_type = (
            row["hazard_type"] if "hazard_type" in protected else result.hazard_type
        )
        new_values = {
            "event_type": new_event_type,
            "hazard_type": new_hazard_type,
            "event_granularity": result.event_granularity,
            "article_role": result.article_role,
            "extraction_basis": result.extraction_basis,
        }
        changed = [field for field, value in new_values.items() if row.get(field, "") != value]
        plan.append(
            {
                "event_id": row["event_id"],
                "representative_url": row["representative_url"],
                "cluster_article_count": len(urls),
                "old_event_type": row.get("event_type", ""),
                "new_event_type": new_event_type,
                "old_hazard_type": row.get("hazard_type", ""),
                "new_hazard_type": new_hazard_type,
                "old_event_granularity": row.get("event_granularity", ""),
                "new_event_granularity": result.event_granularity,
                "old_article_role": row.get("article_role", ""),
                "new_article_role": result.article_role,
                "old_extraction_basis": row.get("extraction_basis", ""),
                "new_extraction_basis": result.extraction_basis,
                "typing_reason": result.reason,
                "event_type_source": (
                    "human_review" if "event_type" in protected else "classifier"
                ),
                "hazard_type_source": (
                    "human_review" if "hazard_type" in protected else "classifier"
                ),
                "changed_fields_json": json.dumps(changed, separators=(",", ":")),
            }
        )
    return plan


def summarize(plan: list[dict[str, Any]]) -> dict[str, Any]:
    changed = [row for row in plan if row["changed_fields_json"] != "[]"]
    return {
        "status": "unapplied_v12_global_typing_plan",
        "rows": len(plan),
        "rows_changed": len(changed),
        "classifier_sha256": classifier_sha256(),
        "new_event_types": dict(Counter(row["new_event_type"] for row in plan)),
        "new_hazard_types": dict(Counter(row["new_hazard_type"] for row in plan)),
        "new_event_granularities": dict(
            Counter(row["new_event_granularity"] for row in plan)
        ),
        "new_article_roles": dict(Counter(row["new_article_role"] for row in plan)),
        "human_event_type_overrides": sum(
            row["event_type_source"] == "human_review" for row in plan
        ),
        "human_hazard_type_overrides": sum(
            row["hazard_type_source"] == "human_review" for row in plan
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-dir", type=Path, default=DEFAULT_RELEASE)
    parser.add_argument("--article-db", type=Path, default=DEFAULT_ARTICLE_DB)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    args = parser.parse_args()

    release_csv = args.release_dir / "canonical_events_final.csv"
    application_log = args.release_dir / "correction_application_log.csv"
    release_rows = read_csv(release_csv)
    urls = {url for row in release_rows for url in parse_urls(row)}
    plan = build_plan(
        release_rows,
        load_articles(args.article_db, urls),
        reviewed_fields(application_log),
    )
    write_csv(args.plan, plan)
    summary = summarize(plan)
    summary["inputs"] = {
        "release_csv": str(release_csv),
        "release_csv_sha256": sha256(release_csv),
        "article_db": str(args.article_db),
        "article_db_sha256": sha256(args.article_db),
        "application_log": str(application_log),
        "application_log_sha256": sha256(application_log),
    }
    summary["plan_sha256"] = sha256(args.plan)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
