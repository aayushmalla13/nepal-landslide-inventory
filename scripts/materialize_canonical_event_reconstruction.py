#!/usr/bin/env python3
"""Materialize validated article-mapping decisions as unapplied correction inputs."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "outputs"
COMPLETED = OUTPUT / "canonical_event_article_mapping_DECISIONS_COMPLETED.csv"
TEMPLATE = OUTPUT / "canonical_event_article_mapping_DECISIONS.csv"
ARTICLE_MAP = OUTPUT / "canonical_event_article_membership_MAP.csv"
VALIDATION = OUTPUT / "canonical_event_article_mapping_validation.json"
GROUPS_OUTPUT = OUTPUT / "canonical_event_reconstruction_GROUPS.csv"
EXCLUSIONS_OUTPUT = OUTPUT / "canonical_event_reconstruction_EXCLUDED_ARTICLES.csv"
MANIFEST_OUTPUT = OUTPUT / "canonical_event_reconstruction_manifest.json"
REPORT_OUTPUT = OUTPUT / "canonical_event_reconstruction_report.md"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]], columns: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def candidate_event_id(old_event_id: str, group: dict) -> str:
    identity = json.dumps(
        {
            "old_event_id": old_event_id,
            "group_id": group["group_id"],
            "event_date": group["event_date"],
            "district": group["district"],
            "article_mapping_ids": sorted(group["article_mapping_ids"]),
            "evidence": group["evidence"],
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return f"candidate_{hashlib.sha256(identity.encode('utf-8')).hexdigest()[:16]}"


def materialize(
    decisions: list[dict[str, str]],
    mapping_rows: list[dict[str, str]],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    mapping_by_id = {row["mapping_id"]: row for row in mapping_rows}
    groups_output: list[dict[str, object]] = []
    exclusions_output: list[dict[str, object]] = []
    for decision in decisions:
        groups = json.loads(decision["final_event_groups_json"] or "[]")
        excluded_ids = json.loads(decision["excluded_article_mapping_ids_json"] or "[]")
        for group in groups:
            member_ids = list(group["article_mapping_ids"])
            urls = [mapping_by_id[value]["article_url"] for value in member_ids]
            groups_output.append(
                {
                    "candidate_event_id": candidate_event_id(decision["event_id"], group),
                    "candidate_id": decision["candidate_id"],
                    "old_event_id": decision["event_id"],
                    "old_cluster_id": decision["cluster_id"],
                    "group_id": group["group_id"],
                    "resolution": decision["final_resolution"],
                    "event_date": group["event_date"],
                    "district": group["district"],
                    "municipality": group["municipality"],
                    "event_type": group["event_type"],
                    "hazard_type": group["hazard_type"],
                    "deaths": group["deaths"],
                    "article_mapping_ids_json": json.dumps(member_ids, ensure_ascii=False),
                    "article_urls_json": json.dumps(urls, ensure_ascii=False),
                    "evidence": group["evidence"],
                    "reviewed_by": decision["reviewed_by"],
                    "review_notes": decision["review_notes"],
                    "production_status": "candidate_unapplied_collision_check_required",
                }
            )
        for mapping_id in excluded_ids:
            source = mapping_by_id[mapping_id]
            exclusions_output.append(
                {
                    "mapping_id": mapping_id,
                    "candidate_id": decision["candidate_id"],
                    "old_event_id": decision["event_id"],
                    "old_cluster_id": decision["cluster_id"],
                    "article_url": source["article_url"],
                    "source": source["source"],
                    "title": source["title"],
                    "final_resolution": decision["final_resolution"],
                    "reviewed_by": decision["reviewed_by"],
                    "review_notes": decision["review_notes"],
                    "production_status": "candidate_unapplied",
                }
            )
    return groups_output, exclusions_output


def main() -> None:
    validation = json.loads(VALIDATION.read_text(encoding="utf-8"))
    if sha256(COMPLETED) != validation["inputs"][COMPLETED.name]:
        raise ValueError("Completed mapping decisions differ from validation provenance.")
    if sha256(TEMPLATE) != validation["inputs"][TEMPLATE.name]:
        raise ValueError("Decision template differs from validation provenance.")
    if sha256(ARTICLE_MAP) != validation["inputs"][ARTICLE_MAP.name]:
        raise ValueError("Article membership map differs from validation provenance.")

    groups, exclusions = materialize(read_csv(COMPLETED), read_csv(ARTICLE_MAP))
    if len(groups) != validation["retained_event_groups"]:
        raise ValueError("Materialized group count differs from validated group count.")
    if len({row["candidate_event_id"] for row in groups}) != len(groups):
        raise ValueError("Candidate event IDs are not unique.")
    write_csv(GROUPS_OUTPUT, groups, list(groups[0]))
    write_csv(EXCLUSIONS_OUTPUT, exclusions, list(exclusions[0]))

    manifest = {
        "replaced_old_events": validation["decision_rows"],
        "excluded_old_events": validation["excluded_clusters"],
        "reconstructed_event_candidates": len(groups),
        "excluded_article_memberships": len(exclusions),
        "net_candidate_event_delta": len(groups) - validation["decision_rows"],
        "inputs": {
            COMPLETED.name: sha256(COMPLETED),
            TEMPLATE.name: sha256(TEMPLATE),
            ARTICLE_MAP.name: sha256(ARTICLE_MAP),
            VALIDATION.name: sha256(VALIDATION),
        },
        "outputs": {
            GROUPS_OUTPUT.name: sha256(GROUPS_OUTPUT),
            EXCLUSIONS_OUTPUT.name: sha256(EXCLUSIONS_OUTPUT),
        },
        "status": "unapplied_collision_check_required",
    }
    MANIFEST_OUTPUT.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    REPORT_OUTPUT.write_text(
        "\n".join(
            [
                "# Canonical event reconstruction candidates",
                "",
                f"Original audited events replaced: {validation['decision_rows']}",
                f"Original events excluded entirely: {validation['excluded_clusters']}",
                f"Reconstructed physical-event candidates: {len(groups)}",
                f"Excluded source-article memberships: {len(exclusions)}",
                f"Provisional event-count delta: {len(groups) - validation['decision_rows']:+d}",
                "",
                "These candidates are not production events. They require collision matching",
                "against the unaffected frozen inventory before any release is rebuilt.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"Wrote {len(groups)} event candidates to {GROUPS_OUTPUT}")
    print(f"Wrote {len(exclusions)} excluded memberships to {EXCLUSIONS_OUTPUT}")
    print(f"Wrote {MANIFEST_OUTPUT}")
    print(f"Wrote {REPORT_OUTPUT}")


if __name__ == "__main__":
    main()
