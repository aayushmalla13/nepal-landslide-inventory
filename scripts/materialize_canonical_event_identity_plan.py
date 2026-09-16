#!/usr/bin/env python3
"""Materialize validated collision decisions as an unapplied identity release plan."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "outputs"
RELEASE_DIR = ROOT / "data" / "releases" / "nepal_landslide_inventory_v0.6.0_v7_20260915"
COLLISION_COMPLETED = OUTPUT / "canonical_event_reconstruction_FINAL_COLLISION_DECISIONS_COMPLETED.csv"
COLLISION_VALIDATION = OUTPUT / "canonical_event_collision_decisions_validation.json"
MAPPING_COMPLETED = OUTPUT / "canonical_event_article_mapping_DECISIONS_COMPLETED.csv"
DATE_EXCLUDED = OUTPUT / "canonical_event_reconstruction_DATE_EXCLUDED.csv"
FROZEN_CANONICAL = RELEASE_DIR / "canonical_events_final.csv"
REMOVE_OUTPUT = OUTPUT / "canonical_event_identity_plan_REMOVE_OLD_EVENTS.csv"
NEW_OUTPUT = OUTPUT / "canonical_event_identity_plan_NEW_EVENTS.csv"
MERGE_OUTPUT = OUTPUT / "canonical_event_identity_plan_MERGES.csv"
EXCLUDE_OUTPUT = OUTPUT / "canonical_event_identity_plan_EXCLUDED_CANDIDATES.csv"
MANIFEST_OUTPUT = OUTPUT / "canonical_event_identity_plan_manifest.json"
REPORT_OUTPUT = OUTPUT / "canonical_event_identity_plan_report.md"


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


def materialize(
    collision_rows: list[dict[str, str]],
    mapping_rows: list[dict[str, str]],
    frozen_rows: list[dict[str, str]],
    date_excluded_rows: list[dict[str, str]],
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    frozen_by_id = {row["event_id"]: row for row in frozen_rows}
    remove_rows: list[dict[str, object]] = []
    for row in mapping_rows:
        frozen = frozen_by_id[row["event_id"]]
        remove_rows.append(
            {
                "old_event_id": row["event_id"],
                "old_cluster_id": row["cluster_id"],
                "old_event_date": frozen["event_date_ad"],
                "old_district": frozen["district"],
                "final_resolution": row["final_resolution"],
                "reviewed_by": row["reviewed_by"],
                "reason": row["review_notes"],
                "production_status": "planned_remove_superseded_event",
            }
        )

    new_rows: list[dict[str, object]] = []
    merge_rows: list[dict[str, object]] = []
    excluded_rows: list[dict[str, object]] = []
    for row in collision_rows:
        action = row["final_collision_action"]
        base = {
            "candidate_event_id": row["candidate_event_id"],
            "old_event_id": row["old_event_id"],
            "event_date": row["event_date"],
            "district": row["district"],
            "municipality": row["municipality"],
            "event_type": row["event_type"],
            "hazard_type": row["hazard_type"],
            "deaths": row["deaths"],
            "article_mapping_ids_json": row["article_mapping_ids_json"],
            "article_urls_json": row["article_urls_json"],
            "evidence": row["evidence"],
            "reviewed_by": row["reviewed_by_collision"],
            "review_notes": row["collision_review_notes"],
        }
        if action == "new_event":
            new_rows.append({**base, "production_status": "planned_new_event"})
        elif action == "merge_existing":
            target = frozen_by_id[row["merge_target_event_id"]]
            merge_rows.append(
                {
                    **base,
                    "merge_target_event_id": row["merge_target_event_id"],
                    "target_date": target["event_date_ad"],
                    "target_district": target["district"],
                    "target_municipality": target["municipality"],
                    "target_representative_url": target["representative_url"],
                    "production_status": "planned_merge_existing",
                }
            )
        else:
            excluded_rows.append(
                {
                    **base,
                    "exclusion_stage": "collision_review",
                    "final_collision_action": action,
                    "production_status": "planned_exclude_candidate",
                }
            )
    for row in date_excluded_rows:
        excluded_rows.append(
            {
                "candidate_event_id": row["candidate_event_id"],
                "old_event_id": row["old_event_id"],
                "event_date": "unclear",
                "district": row["district"],
                "municipality": "",
                "event_type": "",
                "hazard_type": "",
                "deaths": "",
                "article_mapping_ids_json": "",
                "article_urls_json": "",
                "evidence": row["evidence"],
                "reviewed_by": row["reviewed_by"],
                "review_notes": row["review_notes"],
                "exclusion_stage": "date_review",
                "final_collision_action": "exclude_candidate",
                "production_status": "planned_exclude_candidate",
            }
        )
    return remove_rows, new_rows, merge_rows, excluded_rows


def main() -> None:
    validation = json.loads(COLLISION_VALIDATION.read_text(encoding="utf-8"))
    if validation["unresolved_rows"]:
        raise ValueError("Collision decisions remain unresolved.")
    if sha256(COLLISION_COMPLETED) != validation["inputs"][COLLISION_COMPLETED.name]:
        raise ValueError("Completed collision decisions differ from validation provenance.")
    frozen = read_csv(FROZEN_CANONICAL)
    mapping = read_csv(MAPPING_COMPLETED)
    missing = {row["event_id"] for row in mapping} - {row["event_id"] for row in frozen}
    if missing:
        raise ValueError(f"Superseded events are absent from frozen inventory: {sorted(missing)}")
    outputs = materialize(
        read_csv(COLLISION_COMPLETED), mapping, frozen, read_csv(DATE_EXCLUDED)
    )
    remove_rows, new_rows, merge_rows, excluded_rows = outputs
    write_csv(REMOVE_OUTPUT, remove_rows, list(remove_rows[0]))
    write_csv(NEW_OUTPUT, new_rows, list(new_rows[0]))
    write_csv(MERGE_OUTPUT, merge_rows, list(merge_rows[0]))
    write_csv(EXCLUDE_OUTPUT, excluded_rows, list(excluded_rows[0]))
    planned_count = len(frozen) - len(remove_rows) + len(new_rows)
    manifest = {
        "frozen_inventory_rows": len(frozen),
        "superseded_old_events": len(remove_rows),
        "planned_new_events": len(new_rows),
        "planned_merges_into_existing": len(merge_rows),
        "excluded_reconstruction_candidates": len(excluded_rows),
        "planned_identity_layer_rows": planned_count,
        "net_identity_layer_delta": planned_count - len(frozen),
        "inputs": {
            COLLISION_COMPLETED.name: sha256(COLLISION_COMPLETED),
            COLLISION_VALIDATION.name: sha256(COLLISION_VALIDATION),
            MAPPING_COMPLETED.name: sha256(MAPPING_COMPLETED),
            DATE_EXCLUDED.name: sha256(DATE_EXCLUDED),
            str(FROZEN_CANONICAL.relative_to(ROOT)): sha256(FROZEN_CANONICAL),
        },
        "outputs": {
            REMOVE_OUTPUT.name: sha256(REMOVE_OUTPUT),
            NEW_OUTPUT.name: sha256(NEW_OUTPUT),
            MERGE_OUTPUT.name: sha256(MERGE_OUTPUT),
            EXCLUDE_OUTPUT.name: sha256(EXCLUDE_OUTPUT),
        },
        "status": "identity_plan_unapplied_attribute_gates_pending",
    }
    MANIFEST_OUTPUT.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    REPORT_OUTPUT.write_text(
        "\n".join(
            [
                "# Canonical event identity release plan",
                "",
                f"Frozen inventory rows: {len(frozen)}",
                f"Superseded old events: {len(remove_rows)}",
                f"Planned new events: {len(new_rows)}",
                f"Planned merges into existing events: {len(merge_rows)}",
                f"Excluded reconstruction candidates: {len(excluded_rows)}",
                f"Provisional identity-layer rows: {planned_count}",
                f"Net identity-layer delta: {planned_count - len(frozen):+d}",
                "",
                "This plan is not applied. True-value and structured attribute correction",
                "gates must be completed before a new inventory release is built.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"Wrote {len(remove_rows)} rows to {REMOVE_OUTPUT}")
    print(f"Wrote {len(new_rows)} rows to {NEW_OUTPUT}")
    print(f"Wrote {len(merge_rows)} rows to {MERGE_OUTPUT}")
    print(f"Wrote {len(excluded_rows)} rows to {EXCLUDE_OUTPUT}")
    print(f"Wrote {MANIFEST_OUTPUT}")
    print(f"Wrote {REPORT_OUTPUT}")


if __name__ == "__main__":
    main()
