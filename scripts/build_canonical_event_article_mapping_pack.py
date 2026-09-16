#!/usr/bin/env python3
"""Map audited correction candidates to canonical source-article membership."""

from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "outputs"
DATABASE = ROOT / "data" / "raw_sqlite" / "landslide_inventory.sqlite"
RELEASE_DIR = ROOT / "data" / "releases" / "nepal_landslide_inventory_v0.6.0_v7_20260915"
FROZEN_CANONICAL = RELEASE_DIR / "canonical_events_final.csv"
RELEASE_MANIFEST = RELEASE_DIR / "release_manifest.json"
CANDIDATES = OUTPUT / "canonical_event_correction_BATCH_ARTICLE_MAPPING.csv"
CORRECTION_SUMMARY = OUTPUT / "canonical_event_correction_summary.json"
ARTICLE_MAP = OUTPUT / "canonical_event_article_membership_MAP.csv"
DECISIONS = OUTPUT / "canonical_event_article_mapping_DECISIONS.csv"
MANIFEST = OUTPUT / "canonical_event_article_mapping_manifest.json"
REPORT = OUTPUT / "canonical_event_article_mapping_report.md"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def proposed_resolution(candidate: dict[str, str]) -> str:
    actions = set(candidate["recommended_actions"].split(";"))
    size = int(candidate["cluster_article_count"])
    if "exclude_false_event" in actions:
        return "exclude_cluster"
    if "review_event_granularity" in actions or "review_duplicate_merge" in actions:
        return "manual_membership_review"
    if size == 1 and "split_or_exclude_aggregate" in actions:
        return "decompose_source_article"
    if "recluster_articles" in actions and "split_or_exclude_aggregate" in actions:
        return "recluster_and_decompose"
    if "recluster_articles" in actions:
        return "recluster_articles"
    return "manual_membership_review"


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def load_members(
    connection: sqlite3.Connection,
    event_id: str,
    frozen_by_id: dict[str, dict[str, str]],
) -> tuple[str, list[sqlite3.Row]]:
    canonical = frozen_by_id.get(event_id)
    if canonical is None:
        raise ValueError(f"Canonical event not found in frozen release: {event_id}")
    cluster_id = canonical["dedup_cluster_id"]
    payload = json.loads(canonical["event_payload"])
    urls = [str(url) for url in payload.get("urls", [])]
    if not urls and canonical.get("representative_url"):
        urls = [canonical["representative_url"]]
    rows: list[sqlite3.Row] = []
    for url in urls:
        row = connection.execute(
            """
            SELECT r.url AS article_url, COALESCE(e.source, r.source) AS source,
                   COALESCE(e.title, r.title) AS title, e.route_lang, e.class,
                   e.event_date_ad, e.published_date_ad, e.district, e.province,
                   e.municipality, e.ward, e.place_name_raw, e.deaths, e.missing,
                   e.injured, e.trigger, e.specificity_ok, e.specificity_reason,
                   e.specificity_score, e.location_consistent, e.location_reason,
                   e.in_nepal, e.scope_reason, r.published_date_raw, r.text,
                   COALESCE(c.exclude_from_canonical, 0) AS already_excluded,
                   c.correction_action AS existing_correction_action
            FROM raw_articles r
            LEFT JOIN article_events e ON e.article_url = r.url
            LEFT JOIN reviewed_article_corrections c ON c.url = r.url
            WHERE r.url = ?
            ORDER BY e.extracted_event_id
            LIMIT 1
            """,
            (url,),
        ).fetchone()
        if row is None:
            raise ValueError(f"Frozen member URL is absent from the article corpus: {url}")
        rows.append(row)
    return cluster_id, rows


def build_rows(
    candidates: list[dict[str, str]],
    connection: sqlite3.Connection,
    frozen_by_id: dict[str, dict[str, str]],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    article_rows: list[dict[str, object]] = []
    decisions: list[dict[str, object]] = []
    for candidate in candidates:
        cluster_id, members = load_members(connection, candidate["event_id"], frozen_by_id)
        expected = int(candidate["cluster_article_count"])
        if len(members) != expected:
            raise ValueError(
                f"{candidate['event_id']}: audit says {expected} articles, database has {len(members)}."
            )
        resolution = proposed_resolution(candidate)
        urls = [str(member["article_url"]) for member in members]
        decisions.append(
            {
                "candidate_id": candidate["candidate_id"],
                "row_id": candidate["row_id"],
                "event_id": candidate["event_id"],
                "cluster_id": cluster_id,
                "article_count": len(members),
                "recommended_actions": candidate["recommended_actions"],
                "proposed_resolution": resolution,
                "adjudication_notes": candidate["adjudication_notes"],
                "article_urls_json": json.dumps(urls, ensure_ascii=False),
                "final_resolution": "",
                "final_event_count": "",
                "final_event_groups_json": "",
                "excluded_article_mapping_ids_json": "",
                "reviewed_by": "",
                "review_notes": "",
            }
        )
        for index, member in enumerate(members, start=1):
            article_rows.append(
                {
                    "mapping_id": f"{candidate['candidate_id']}-A{index:02d}",
                    "candidate_id": candidate["candidate_id"],
                    "row_id": candidate["row_id"],
                    "event_id": candidate["event_id"],
                    "cluster_id": cluster_id,
                    "article_index": index,
                    "cluster_article_count": len(members),
                    "proposed_resolution": resolution,
                    "recommended_actions": candidate["recommended_actions"],
                    "adjudication_notes": candidate["adjudication_notes"],
                    "article_url": member["article_url"],
                    "source": member["source"],
                    "title": member["title"],
                    "route_lang": member["route_lang"],
                    "event_class": member["class"],
                    "event_date_ad": member["event_date_ad"],
                    "published_date_ad": member["published_date_ad"],
                    "published_date_raw": member["published_date_raw"],
                    "district": member["district"],
                    "province": member["province"],
                    "municipality": member["municipality"],
                    "ward": member["ward"],
                    "place_name_raw": member["place_name_raw"],
                    "deaths": member["deaths"],
                    "missing": member["missing"],
                    "injured": member["injured"],
                    "trigger": member["trigger"],
                    "specificity_ok": member["specificity_ok"],
                    "specificity_reason": member["specificity_reason"],
                    "specificity_score": member["specificity_score"],
                    "location_consistent": member["location_consistent"],
                    "location_reason": member["location_reason"],
                    "in_nepal": member["in_nepal"],
                    "scope_reason": member["scope_reason"],
                    "already_excluded": member["already_excluded"],
                    "existing_correction_action": member["existing_correction_action"],
                    "article_text": member["text"],
                    "final_article_action": "",
                    "final_event_groups": "",
                    "review_notes": "",
                }
            )
    return article_rows, decisions


def main() -> None:
    correction_summary = json.loads(CORRECTION_SUMMARY.read_text(encoding="utf-8"))
    expected_hash = correction_summary["outputs"][CANDIDATES.name]
    if sha256(CANDIDATES) != expected_hash:
        raise ValueError("Article-mapping batch differs from the correction summary manifest.")
    release_manifest = json.loads(RELEASE_MANIFEST.read_text(encoding="utf-8"))
    expected_canonical_hash = next(
        item["sha256"] for item in release_manifest["files"]
        if item["file"] == FROZEN_CANONICAL.name
    )
    if sha256(FROZEN_CANONICAL) != expected_canonical_hash:
        raise ValueError("Frozen canonical CSV differs from its release manifest.")
    candidates = read_csv(CANDIDATES)
    frozen_by_id = {row["event_id"]: row for row in read_csv(FROZEN_CANONICAL)}
    with connect() as connection:
        article_rows, decisions = build_rows(candidates, connection, frozen_by_id)
    write_csv(ARTICLE_MAP, article_rows)
    write_csv(DECISIONS, decisions)

    resolution_counts = Counter(str(row["proposed_resolution"]) for row in decisions)
    result = {
        "candidate_events": len(decisions),
        "mapped_articles": len(article_rows),
        "proposed_resolution_counts": dict(resolution_counts),
        "inputs": {
            CANDIDATES.name: sha256(CANDIDATES),
            CORRECTION_SUMMARY.name: sha256(CORRECTION_SUMMARY),
            str(FROZEN_CANONICAL.relative_to(ROOT)): sha256(FROZEN_CANONICAL),
            str(RELEASE_MANIFEST.relative_to(ROOT)): sha256(RELEASE_MANIFEST),
            str(DATABASE.relative_to(ROOT)): sha256(DATABASE),
        },
        "outputs": {
            ARTICLE_MAP.name: sha256(ARTICLE_MAP),
            DECISIONS.name: sha256(DECISIONS),
        },
        "status": "mapping_pack_only_no_production_changes",
    }
    MANIFEST.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# Canonical event article-mapping pack",
        "",
        f"Candidate events: {len(decisions)}",
        f"Mapped source articles: {len(article_rows)}",
        "",
        "| Proposed resolution | Events |",
        "|---|---:|",
    ]
    for name, count in resolution_counts.most_common():
        lines.append(f"| {name} | {count} |")
    lines.extend(
        [
            "",
            "This is a provenance and decision pack only. No source article, cluster,",
            "canonical event, or frozen release has been changed.",
            "",
        ]
    )
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Mapped {len(decisions)} candidates to {len(article_rows)} source articles.")
    print(f"Wrote {ARTICLE_MAP}")
    print(f"Wrote {DECISIONS}")
    print(f"Wrote {MANIFEST}")
    print(f"Wrote {REPORT}")


if __name__ == "__main__":
    main()
