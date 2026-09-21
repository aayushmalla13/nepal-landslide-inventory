#!/usr/bin/env python3
"""Materialize validated post-correction mapping decisions as an unapplied plan."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "outputs"
COMPLETED = OUTPUT / "post_correction_article_mapping_DECISIONS_COMPLETED.csv"
TEMPLATE = OUTPUT / "post_correction_article_mapping_DECISIONS.csv"
ARTICLE_MAP = OUTPUT / "post_correction_article_membership_MAP.csv"
VALIDATION = OUTPUT / "post_correction_article_mapping_validation.json"
GROUPS_OUTPUT = OUTPUT / "post_correction_reconstruction_GROUPS.csv"
EXCLUSIONS_OUTPUT = OUTPUT / "post_correction_reconstruction_EXCLUDED_ARTICLES.csv"
UNRESOLVED_OUTPUT = OUTPUT / "post_correction_reconstruction_UNRESOLVED.csv"
MANIFEST_OUTPUT = OUTPUT / "post_correction_reconstruction_manifest.json"
REPORT_OUTPUT = OUTPUT / "post_correction_reconstruction_report.md"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
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


def candidate_event_id(old_event_id: str, group: dict[str, Any]) -> str:
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
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
    return f"postcorr_candidate_{digest}"


def materialize(
    decisions: list[dict[str, str]],
    mapping_rows: list[dict[str, str]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    mapping_by_id = {row["mapping_id"]: row for row in mapping_rows}
    groups_output: list[dict[str, Any]] = []
    exclusions_output: list[dict[str, Any]] = []
    unresolved_output: list[dict[str, Any]] = []
    for decision in decisions:
        if decision["final_resolution"] == "unclear":
            unresolved_output.append(
                {
                    "queue_id": decision["queue_id"],
                    "row_id": decision["row_id"],
                    "sample_role": decision["sample_role"],
                    "correction_layer": decision["correction_layer"],
                    "old_event_id": decision["event_id"],
                    "old_cluster_id": decision["cluster_id"],
                    "article_mapping_ids_json": decision["article_mapping_ids_json"],
                    "reviewed_by": decision["reviewed_by"],
                    "review_notes": decision["review_notes"],
                    "production_status": "unresolved_original_event_retained",
                }
            )
            continue

        groups = json.loads(decision["final_event_groups_json"] or "[]")
        excluded_ids = json.loads(decision["excluded_article_mapping_ids_json"] or "[]")
        for group in groups:
            member_ids = list(group["article_mapping_ids"])
            urls = [mapping_by_id[value]["article_url"] for value in member_ids]
            groups_output.append(
                {
                    "candidate_event_id": candidate_event_id(decision["event_id"], group),
                    "queue_id": decision["queue_id"],
                    "row_id": decision["row_id"],
                    "sample_role": decision["sample_role"],
                    "correction_layer": decision["correction_layer"],
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
                    "production_status": (
                        "candidate_unapplied_date_and_collision_checks_required"
                    ),
                }
            )
        for mapping_id in excluded_ids:
            source = mapping_by_id[mapping_id]
            exclusions_output.append(
                {
                    "mapping_id": mapping_id,
                    "queue_id": decision["queue_id"],
                    "row_id": decision["row_id"],
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
    return groups_output, exclusions_output, unresolved_output


def verify_validation_provenance(validation: dict[str, Any]) -> None:
    for path in (COMPLETED, TEMPLATE, ARTICLE_MAP):
        if sha256(path) != validation["inputs"][path.name]:
            raise ValueError(f"Mapping input differs from validation provenance: {path.name}")
    if validation["status"] != "validated_mapping_decisions_not_yet_applied":
        raise ValueError("Mapping validation does not have the expected status")


def main() -> int:
    validation = json.loads(VALIDATION.read_text(encoding="utf-8"))
    verify_validation_provenance(validation)
    decisions = read_csv(COMPLETED)
    groups, exclusions, unresolved = materialize(decisions, read_csv(ARTICLE_MAP))
    if len(groups) != validation["retained_event_groups"]:
        raise ValueError("Materialized group count differs from validated group count")
    if len(unresolved) != validation["unresolved_clusters"]:
        raise ValueError("Materialized unresolved count differs from validation")
    if len({row["candidate_event_id"] for row in groups}) != len(groups):
        raise ValueError("Candidate event IDs are not unique")

    write_csv(GROUPS_OUTPUT, groups, list(groups[0]))
    write_csv(EXCLUSIONS_OUTPUT, exclusions, list(exclusions[0]))
    write_csv(UNRESOLVED_OUTPUT, unresolved, list(unresolved[0]))
    resolved_old_events = validation["decision_rows"] - validation["unresolved_clusters"]
    unclear_dates = sum(str(row["event_date"]).lower() == "unclear" for row in groups)
    manifest = {
        "decision_rows": validation["decision_rows"],
        "resolved_old_events": resolved_old_events,
        "unresolved_old_events_retained": len(unresolved),
        "excluded_old_events": validation["excluded_clusters"],
        "reconstructed_event_candidates": len(groups),
        "reconstructed_candidates_with_unclear_date": unclear_dates,
        "excluded_article_memberships": len(exclusions),
        "net_candidate_event_delta": len(groups) - resolved_old_events,
        "input_sha256": {
            path.name: sha256(path)
            for path in (COMPLETED, TEMPLATE, ARTICLE_MAP, VALIDATION)
        },
        "output_sha256": {
            path.name: sha256(path)
            for path in (GROUPS_OUTPUT, EXCLUSIONS_OUTPUT, UNRESOLVED_OUTPUT)
        },
        "status": "unapplied_date_and_collision_checks_required",
    }
    MANIFEST_OUTPUT.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    REPORT_OUTPUT.write_text(
        "\n".join(
            [
                "# Post-correction reconstruction candidates",
                "",
                f"Validated decision rows: {validation['decision_rows']}",
                f"Resolved old events: {resolved_old_events}",
                f"Unresolved old events retained unchanged: {len(unresolved)}",
                f"Old events excluded entirely: {validation['excluded_clusters']}",
                f"Reconstructed physical-event candidates: {len(groups)}",
                f"Candidates with unclear date: {unclear_dates}",
                f"Excluded source-article memberships: {len(exclusions)}",
                f"Provisional event-count delta: {len(groups) - resolved_old_events:+d}",
                "",
                "These rows are not production events. Resolve unclear dates and match",
                "all candidates against unaffected inventory events before rebuilding.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"Wrote {len(groups)} event candidates to {GROUPS_OUTPUT}")
    print(f"Wrote {len(exclusions)} excluded memberships to {EXCLUSIONS_OUTPUT}")
    print(f"Wrote {len(unresolved)} unresolved events to {UNRESOLVED_OUTPUT}")
    print(f"Wrote {MANIFEST_OUTPUT}")
    print(f"Wrote {REPORT_OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
