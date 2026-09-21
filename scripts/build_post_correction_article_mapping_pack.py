#!/usr/bin/env python3
"""Build the article-level decision pack for post-correction identity findings."""

from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "outputs"
DATABASE = ROOT / "data" / "raw_sqlite" / "landslide_inventory.sqlite"
RELEASE_DIR = (
    ROOT / "data" / "releases" / "nepal_landslide_inventory_v0.7.0_candidate_20260916"
)
CANONICAL = RELEASE_DIR / "canonical_events_final.csv"
RELEASE_MANIFEST = RELEASE_DIR / "release_manifest.json"
CANDIDATES = OUTPUT / "post_correction_remediation_BATCH_ARTICLE_MAPPING.csv"
REMEDIATION_MANIFEST = OUTPUT / "post_correction_remediation_manifest.json"
ARTICLE_MAP = OUTPUT / "post_correction_article_membership_MAP.csv"
DECISIONS = OUTPUT / "post_correction_article_mapping_DECISIONS.csv"
MANIFEST = OUTPUT / "post_correction_article_mapping_manifest.json"
REPORT = OUTPUT / "post_correction_article_mapping_report.md"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
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


def event_urls(canonical: dict[str, str]) -> list[str]:
    payload = json.loads(canonical["event_payload"])
    urls = [str(url).strip() for url in payload.get("urls", []) if str(url).strip()]
    if not urls and canonical["representative_url"].strip():
        urls = [canonical["representative_url"].strip()]
    if len(urls) != len(set(urls)):
        raise ValueError(f"Duplicate URL in event payload: {canonical['event_id']}")
    return urls


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def load_members(
    connection: sqlite3.Connection,
    event_id: str,
    canonical_by_id: dict[str, dict[str, str]],
) -> tuple[str, list[sqlite3.Row]]:
    canonical = canonical_by_id.get(event_id)
    if canonical is None:
        raise ValueError(f"Canonical event not found in candidate release: {event_id}")
    rows: list[sqlite3.Row] = []
    for url in event_urls(canonical):
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
            raise ValueError(f"Candidate member URL is absent from local corpus: {url}")
        rows.append(row)
    return canonical["dedup_cluster_id"], rows


def build_rows(
    candidates: list[dict[str, str]],
    connection: sqlite3.Connection,
    canonical_by_id: dict[str, dict[str, str]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    article_rows: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    for candidate in candidates:
        cluster_id, members = load_members(
            connection, candidate["event_id"], canonical_by_id
        )
        expected = int(candidate["cluster_article_count"])
        if len(members) != expected:
            raise ValueError(
                f"{candidate['event_id']}: audit says {expected} articles, "
                f"candidate payload has {len(members)}"
            )
        resolution = proposed_resolution(candidate)
        mapping_ids = [
            f"{candidate['queue_id']}-A{index:02d}"
            for index in range(1, len(members) + 1)
        ]
        decisions.append(
            {
                "queue_id": candidate["queue_id"],
                "row_id": candidate["row_id"],
                "sample_role": candidate["sample_role"],
                "correction_layer": candidate["correction_layer"],
                "event_id": candidate["event_id"],
                "cluster_id": cluster_id,
                "article_count": len(members),
                "recommended_actions": candidate["recommended_actions"],
                "proposed_resolution": resolution,
                "audit_notes": candidate["audit_notes"],
                "article_mapping_ids_json": json.dumps(mapping_ids),
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
                    "mapping_id": mapping_ids[index - 1],
                    "queue_id": candidate["queue_id"],
                    "row_id": candidate["row_id"],
                    "sample_role": candidate["sample_role"],
                    "correction_layer": candidate["correction_layer"],
                    "event_id": candidate["event_id"],
                    "cluster_id": cluster_id,
                    "article_index": index,
                    "cluster_article_count": len(members),
                    "proposed_resolution": resolution,
                    "recommended_actions": candidate["recommended_actions"],
                    "audit_notes": candidate["audit_notes"],
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


def verify_inputs() -> None:
    remediation = json.loads(REMEDIATION_MANIFEST.read_text(encoding="utf-8"))
    if sha256(CANDIDATES) != remediation["output_sha256"][CANDIDATES.name]:
        raise ValueError("Article-mapping batch differs from remediation manifest")
    release = json.loads(RELEASE_MANIFEST.read_text(encoding="utf-8"))
    if sha256(CANONICAL) != release["canonical_summary"]["sha256"]:
        raise ValueError("Candidate canonical CSV differs from release manifest")
    database_key = str(DATABASE.relative_to(ROOT))
    if sha256(DATABASE) != release["inputs"][database_key]:
        raise ValueError("Working database differs from the candidate release input")


def render_report(decisions: list[dict[str, Any]], articles: list[dict[str, Any]]) -> str:
    counts = Counter(str(row["proposed_resolution"]) for row in decisions)
    lines = [
        "# Post-correction article-mapping pack",
        "",
        f"Decision rows: {len(decisions)}",
        f"Mapped source articles: {len(articles)}",
        "",
        "| Proposed resolution | Events |",
        "|---|---:|",
    ]
    lines.extend(f"| {name} | {count} |" for name, count in counts.most_common())
    lines.extend(
        [
            "",
            "This is a locked evidence and decision template only. No article,",
            "canonical event, candidate release, or production table was changed.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    verify_inputs()
    candidates = read_csv(CANDIDATES)
    canonical_by_id = {row["event_id"]: row for row in read_csv(CANONICAL)}
    with connect() as connection:
        article_rows, decisions = build_rows(candidates, connection, canonical_by_id)
    if len(decisions) != 67 or len(article_rows) != 85:
        raise ValueError("Unexpected post-correction article-mapping pack dimensions")
    if len({row["mapping_id"] for row in article_rows}) != len(article_rows):
        raise ValueError("Duplicate article mapping ID")
    write_csv(ARTICLE_MAP, article_rows)
    write_csv(DECISIONS, decisions)
    REPORT.write_text(render_report(decisions, article_rows), encoding="utf-8")

    manifest = {
        "audit": "post_correction_article_mapping_v1",
        "candidate_release": RELEASE_DIR.name,
        "decision_rows": len(decisions),
        "mapped_articles": len(article_rows),
        "proposed_resolution_counts": dict(
            Counter(str(row["proposed_resolution"]) for row in decisions)
        ),
        "status": "mapping_pack_only_no_production_changes",
        "input_sha256": {
            str(path.relative_to(ROOT)): sha256(path)
            for path in (CANDIDATES, REMEDIATION_MANIFEST, CANONICAL, RELEASE_MANIFEST, DATABASE)
        },
        "output_sha256": {
            path.name: sha256(path) for path in (ARTICLE_MAP, DECISIONS, REPORT)
        },
    }
    MANIFEST.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"Mapped {len(decisions)} findings to {len(article_rows)} source articles")
    print(f"Wrote {ARTICLE_MAP}")
    print(f"Wrote {DECISIONS}")
    print(f"Wrote {MANIFEST}")
    print(f"Wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
