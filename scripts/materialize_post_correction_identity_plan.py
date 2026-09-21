#!/usr/bin/env python3
"""Materialize the validated post-correction identity plan without applying it."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "outputs"
SOURCE_RELEASE = ROOT / "data" / "releases" / "nepal_landslide_inventory_v0.7.0_candidate_20260916"
SOURCE_CANONICAL = SOURCE_RELEASE / "canonical_events_final.csv"
FINAL_DECISIONS = OUTPUT / "post_correction_reconstruction_FINAL_COLLISION_DECISIONS_COMPLETED.csv"
FINAL_VALIDATION = OUTPUT / "post_correction_final_collision_validation.json"
EXISTING_MANIFEST = OUTPUT / "post_correction_existing_collision_outcomes_manifest.json"
EXISTING_NEW = OUTPUT / "post_correction_existing_collision_NEW_CANDIDATES.csv"
EXISTING_MERGES = OUTPUT / "post_correction_existing_collision_MERGES.csv"
EXISTING_EXCLUDED = OUTPUT / "post_correction_existing_collision_EXCLUDED.csv"
EXISTING_BLOCKED = OUTPUT / "post_correction_existing_collision_BLOCKED_CANDIDATES.csv"
MAPPING_DECISIONS = OUTPUT / "post_correction_article_mapping_DECISIONS_COMPLETED.csv"
DATE_EXCLUDED = OUTPUT / "post_correction_reconstruction_DATE_EXCLUDED.csv"
EXCLUDED_ARTICLES = OUTPUT / "post_correction_reconstruction_EXCLUDED_ARTICLES.csv"

PREFIX = "post_correction_identity_plan"
REMOVE_OUTPUT = OUTPUT / f"{PREFIX}_REMOVE_OLD_EVENTS.csv"
NEW_OUTPUT = OUTPUT / f"{PREFIX}_NEW_EVENTS.csv"
MERGE_EXISTING_OUTPUT = OUTPUT / f"{PREFIX}_MERGES_EXISTING.csv"
MERGE_CANDIDATE_OUTPUT = OUTPUT / f"{PREFIX}_MERGES_CANDIDATES.csv"
EXCLUDE_OUTPUT = OUTPUT / f"{PREFIX}_EXCLUDED_CANDIDATES.csv"
BLOCKED_OUTPUT = OUTPUT / f"{PREFIX}_BLOCKED_CANDIDATES.csv"
RETAINED_OUTPUT = OUTPUT / f"{PREFIX}_RETAINED_OLD_EVENTS.csv"
MANIFEST_OUTPUT = OUTPUT / f"{PREFIX}_manifest.json"
REPORT_OUTPUT = OUTPUT / f"{PREFIX}_report.md"


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


def final_blocked_old_ids(
    final_rows: list[dict[str, str]], initially_blocked: set[str]
) -> set[str]:
    """Propagate bundle blocks through candidate-to-candidate dependencies."""
    by_candidate = {row["candidate_event_id"]: row for row in final_rows}
    blocked = set(initially_blocked)
    blocked.update(
        row["old_event_id"] for row in final_rows if row["final_candidate_action"] == "unclear"
    )
    changed = True
    while changed:
        changed = False
        for row in final_rows:
            target_id = row["merge_candidate_event_id"]
            if not target_id:
                continue
            target = by_candidate[target_id]
            if target["old_event_id"] in blocked and row["old_event_id"] not in blocked:
                blocked.add(row["old_event_id"])
                changed = True
    return blocked


def candidate_base(row: dict[str, str]) -> dict[str, str]:
    return {
        key: row.get(key, "")
        for key in (
            "candidate_event_id",
            "queue_id",
            "row_id",
            "old_event_id",
            "old_cluster_id",
            "group_id",
            "resolution",
            "event_date",
            "district",
            "municipality",
            "event_type",
            "hazard_type",
            "deaths",
            "article_mapping_ids_json",
            "article_urls_json",
            "evidence",
        )
    }


def materialize(
    final_rows: list[dict[str, str]],
    existing_new_rows: list[dict[str, str]],
    existing_merge_rows: list[dict[str, str]],
    existing_excluded_rows: list[dict[str, str]],
    existing_blocked_rows: list[dict[str, str]],
    mapping_rows: list[dict[str, str]],
    date_excluded_rows: list[dict[str, str]],
    source_rows: list[dict[str, str]],
) -> dict[str, list[dict[str, str]]]:
    source_by_id = {row["event_id"]: row for row in source_rows}
    final_ids = {row["candidate_event_id"] for row in final_rows}
    eligible_ids = {row["candidate_event_id"] for row in existing_new_rows}
    if final_ids != eligible_ids:
        raise ValueError("Final decisions do not match eligible new candidates")

    mapping_unclear = {
        row["event_id"] for row in mapping_rows if row["final_resolution"] == "unclear"
    }
    upstream_blocked = {row["old_event_id"] for row in existing_blocked_rows}
    blocked_old_ids = final_blocked_old_ids(final_rows, mapping_unclear | upstream_blocked)

    remove: list[dict[str, str]] = []
    retained_old: list[dict[str, str]] = []
    for row in mapping_rows:
        old_id = row["event_id"]
        source = source_by_id.get(old_id)
        if source is None:
            raise ValueError(f"Reviewed old event is absent from source candidate: {old_id}")
        base = {
            "old_event_id": old_id,
            "old_cluster_id": row["cluster_id"],
            "old_event_date": source["event_date_ad"],
            "old_district": source["district"],
            "final_resolution": row["final_resolution"],
            "reviewed_by": row["reviewed_by"],
            "reason": row["review_notes"],
        }
        if old_id in blocked_old_ids:
            if old_id in mapping_unclear:
                blocked_reason = "article_mapping_resolution_unclear"
            elif old_id in upstream_blocked:
                blocked_reason = "existing_event_collision_bundle_unclear"
            else:
                blocked_reason = "final_candidate_collision_bundle_unclear"
            retained_old.append(
                {
                    **base,
                    "blocked_reason": blocked_reason,
                    "production_status": "retain_old_event_bundle_unapplied",
                }
            )
        else:
            remove.append(
                {
                    **base,
                    "production_status": "planned_remove_superseded_event_unapplied",
                }
            )

    new_events: list[dict[str, str]] = []
    candidate_merges: list[dict[str, str]] = []
    excluded: list[dict[str, str]] = []
    blocked_candidates: list[dict[str, str]] = [
        {
            **candidate_base(row),
            "blocked_reason": row.get("blocked_reason", "existing_event_collision_bundle_unclear"),
            "production_status": "blocked_original_event_retained",
        }
        for row in existing_blocked_rows
    ]
    for row in final_rows:
        base = candidate_base(row)
        if row["old_event_id"] in blocked_old_ids:
            blocked_candidates.append(
                {
                    **base,
                    "blocked_reason": "old_event_bundle_blocked_at_final_collision_gate",
                    "production_status": "blocked_original_event_retained",
                }
            )
        elif row["final_candidate_action"] == "new_event":
            new_events.append(
                {
                    **base,
                    "reviewed_by_final": row["reviewed_by_final"],
                    "final_collision_notes": row["final_collision_notes"],
                    "production_status": "planned_new_event_unapplied",
                }
            )
        elif row["final_candidate_action"] == "merge_candidate":
            candidate_merges.append(
                {
                    **base,
                    "merge_candidate_event_id": row["merge_candidate_event_id"],
                    "reviewed_by_final": row["reviewed_by_final"],
                    "final_collision_notes": row["final_collision_notes"],
                    "production_status": "planned_merge_candidate_unapplied",
                }
            )
        elif row["final_candidate_action"] == "exclude_duplicate":
            excluded.append(
                {
                    **base,
                    "exclusion_stage": "final_candidate_collision",
                    "duplicate_of_candidate_event_id": row["merge_candidate_event_id"],
                    "reviewed_by": row["reviewed_by_final"],
                    "review_notes": row["final_collision_notes"],
                    "production_status": "planned_exclude_candidate_unapplied",
                }
            )

    existing_merges: list[dict[str, str]] = []
    for row in existing_merge_rows:
        if row["old_event_id"] in blocked_old_ids:
            blocked_candidates.append(
                {
                    **candidate_base(row),
                    "blocked_reason": "old_event_bundle_blocked_at_final_collision_gate",
                    "production_status": "blocked_original_event_retained",
                }
            )
            continue
        target_id = row["merge_existing_event_id"]
        target = source_by_id.get(target_id)
        if target is None:
            raise ValueError(f"Existing merge target is absent from source: {target_id}")
        if target_id in {item["old_event_id"] for item in remove}:
            raise ValueError(f"Existing merge target is also superseded: {target_id}")
        existing_merges.append(
            {
                **candidate_base(row),
                "merge_existing_event_id": target_id,
                "target_date": target["event_date_ad"],
                "target_district": target["district"],
                "target_municipality": target["municipality"],
                "reviewed_by": row.get("reviewed_by", ""),
                "review_notes": row.get("collision_review_notes", ""),
                "production_status": "planned_merge_existing_unapplied",
            }
        )

    for row in existing_excluded_rows:
        excluded.append(
            {
                **candidate_base(row),
                "exclusion_stage": "existing_event_collision",
                "duplicate_of_candidate_event_id": "",
                "reviewed_by": row.get("reviewed_by", ""),
                "review_notes": row.get("collision_review_notes", ""),
                "production_status": "planned_exclude_candidate_unapplied",
            }
        )
    for row in date_excluded_rows:
        excluded.append(
            {
                **candidate_base(row),
                "event_date": "unclear",
                "exclusion_stage": "date_review",
                "duplicate_of_candidate_event_id": "",
                "reviewed_by": row["reviewed_by"],
                "review_notes": row["review_notes"],
                "production_status": "planned_exclude_candidate_unapplied",
            }
        )

    return {
        "remove": remove,
        "new": new_events,
        "merge_existing": existing_merges,
        "merge_candidate": candidate_merges,
        "excluded": excluded,
        "blocked_candidates": blocked_candidates,
        "retained_old": retained_old,
    }


def verify_inputs() -> None:
    final_validation = json.loads(FINAL_VALIDATION.read_text(encoding="utf-8"))
    if final_validation["status"] != "validated_final_candidate_collisions_unapplied":
        raise ValueError("Final candidate collision gate is not validated")
    if sha256(FINAL_DECISIONS) != final_validation["input_sha256"][FINAL_DECISIONS.name]:
        raise ValueError("Final decisions differ from validated provenance")
    existing_manifest = json.loads(EXISTING_MANIFEST.read_text(encoding="utf-8"))
    for path in (EXISTING_NEW, EXISTING_MERGES, EXISTING_EXCLUDED, EXISTING_BLOCKED):
        if sha256(path) != existing_manifest["output_sha256"][path.name]:
            raise ValueError(f"Existing-collision artifact changed: {path.name}")


def main() -> int:
    verify_inputs()
    paths = (
        FINAL_DECISIONS,
        FINAL_VALIDATION,
        EXISTING_MANIFEST,
        EXISTING_NEW,
        EXISTING_MERGES,
        EXISTING_EXCLUDED,
        EXISTING_BLOCKED,
        MAPPING_DECISIONS,
        DATE_EXCLUDED,
        EXCLUDED_ARTICLES,
        SOURCE_CANONICAL,
    )
    result = materialize(
        read_csv(FINAL_DECISIONS),
        read_csv(EXISTING_NEW),
        read_csv(EXISTING_MERGES),
        read_csv(EXISTING_EXCLUDED),
        read_csv(EXISTING_BLOCKED),
        read_csv(MAPPING_DECISIONS),
        read_csv(DATE_EXCLUDED),
        read_csv(SOURCE_CANONICAL),
    )
    expected = {
        "remove": 61,
        "new": 42,
        "merge_existing": 11,
        "merge_candidate": 0,
        "excluded": 29,
        "blocked_candidates": 11,
        "retained_old": 6,
    }
    actual = {key: len(rows) for key, rows in result.items()}
    if actual != expected:
        raise ValueError(f"Unexpected final identity-plan counts: {actual}")

    base_columns = list(candidate_base({}))
    outputs = {
        REMOVE_OUTPUT: (result["remove"], list(result["remove"][0])),
        NEW_OUTPUT: (
            result["new"],
            base_columns + ["reviewed_by_final", "final_collision_notes", "production_status"],
        ),
        MERGE_EXISTING_OUTPUT: (
            result["merge_existing"],
            base_columns
            + [
                "merge_existing_event_id",
                "target_date",
                "target_district",
                "target_municipality",
                "reviewed_by",
                "review_notes",
                "production_status",
            ],
        ),
        MERGE_CANDIDATE_OUTPUT: (
            result["merge_candidate"],
            base_columns
            + [
                "merge_candidate_event_id",
                "reviewed_by_final",
                "final_collision_notes",
                "production_status",
            ],
        ),
        EXCLUDE_OUTPUT: (
            result["excluded"],
            base_columns
            + [
                "exclusion_stage",
                "duplicate_of_candidate_event_id",
                "reviewed_by",
                "review_notes",
                "production_status",
            ],
        ),
        BLOCKED_OUTPUT: (
            result["blocked_candidates"],
            base_columns + ["blocked_reason", "production_status"],
        ),
        RETAINED_OUTPUT: (result["retained_old"], list(result["retained_old"][0])),
    }
    for path, (rows, columns) in outputs.items():
        write_csv(path, rows, columns)

    source_count = len(read_csv(SOURCE_CANONICAL))
    planned_count = source_count - len(result["remove"]) + len(result["new"])
    manifest = {
        "source_release": SOURCE_RELEASE.name,
        "source_inventory_rows": source_count,
        "superseded_old_events": len(result["remove"]),
        "planned_new_events": len(result["new"]),
        "planned_merges_into_existing": len(result["merge_existing"]),
        "planned_merges_into_candidates": len(result["merge_candidate"]),
        "excluded_reconstruction_candidates": len(result["excluded"]),
        "blocked_reconstruction_candidates": len(result["blocked_candidates"]),
        "reviewed_old_events_retained": len(result["retained_old"]),
        "excluded_article_memberships": len(read_csv(EXCLUDED_ARTICLES)),
        "planned_identity_layer_rows": planned_count,
        "net_identity_layer_delta": planned_count - source_count,
        "input_sha256": {str(path.relative_to(ROOT)): sha256(path) for path in paths},
        "output_sha256": {path.name: sha256(path) for path in outputs},
        "status": (
            "post_correction_identity_plan_unapplied_parser_fixes_and_attribute_gates_pending"
        ),
    }
    MANIFEST_OUTPUT.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    REPORT_OUTPUT.write_text(
        "\n".join(
            [
                "# Post-correction identity plan result",
                "",
                f"Source candidate rows: {source_count}",
                f"Superseded old events: {len(result['remove'])}",
                f"Planned new physical events: {len(result['new'])}",
                f"Candidates merged into existing events: {len(result['merge_existing'])}",
                f"Candidates merged into retained candidates: {len(result['merge_candidate'])}",
                f"Excluded reconstruction candidates: {len(result['excluded'])}",
                f"Blocked reconstruction candidates: {len(result['blocked_candidates'])}",
                f"Reviewed old events retained unchanged: {len(result['retained_old'])}",
                f"Excluded article memberships preserved: {len(read_csv(EXCLUDED_ARTICLES))}",
                f"Provisional identity-layer rows: {planned_count}",
                f"Net identity-layer delta: {planned_count - source_count:+d}",
                "",
                "The plan is validated but unapplied. The three collision-blocked bundles",
                "and three mapping-unclear old events remain unchanged in the source candidate.",
                "Parser fixes and the remaining manual attribute gates must be completed",
                "before assembling and independently validating a new candidate release.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    for path, (rows, _columns) in outputs.items():
        print(f"Wrote {len(rows)} rows to {path}")
    print(f"Wrote {MANIFEST_OUTPUT}")
    print(f"Wrote {REPORT_OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
