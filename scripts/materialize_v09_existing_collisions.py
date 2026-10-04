#!/usr/bin/env python3
"""Materialize validated v0.9 existing-event collision outcomes without applying them."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "outputs"
COMPLETED = OUTPUT / "v09_reconstruction_COLLISION_DECISIONS_COMPLETED.csv"
VALIDATION = OUTPUT / "v09_collision_validation.json"
MAPPING_DECISIONS = OUTPUT / "v09_article_mapping_DECISIONS_COMPLETED.csv"
NEW_OUTPUT = OUTPUT / "v09_existing_collision_NEW_CANDIDATES.csv"
MERGE_OUTPUT = OUTPUT / "v09_existing_collision_MERGES.csv"
EXCLUDE_OUTPUT = OUTPUT / "v09_existing_collision_EXCLUDED.csv"
BLOCKED_OUTPUT = OUTPUT / "v09_existing_collision_BLOCKED_CANDIDATES.csv"
MANIFEST_OUTPUT = OUTPUT / "v09_existing_collision_outcomes_manifest.json"
REPORT_OUTPUT = OUTPUT / "v09_existing_collision_outcomes_report.md"
SCRIPT_PATH = Path(__file__).resolve()
REPORT_TITLE = "v0.9 existing-event collision outcomes"


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


def materialize(
    collision_rows: list[dict[str, str]],
) -> tuple[
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    set[str],
]:
    blocked_old_ids = {
        row["old_event_id"] for row in collision_rows if row["final_action"] == "unclear"
    }
    new_rows: list[dict[str, str]] = []
    merge_rows: list[dict[str, str]] = []
    excluded_rows: list[dict[str, str]] = []
    blocked_rows: list[dict[str, str]] = []
    for row in collision_rows:
        if row["old_event_id"] in blocked_old_ids:
            blocked_rows.append(
                {
                    **row,
                    "blocked_reason": "old_event_bundle_contains_unclear_collision",
                    "production_status": "blocked_original_event_retained",
                }
            )
        elif row["final_action"] == "new_event":
            new_rows.append({**row, "production_status": "planned_new_event_unapplied"})
        elif row["final_action"] == "merge_existing":
            merge_rows.append({**row, "production_status": "planned_merge_existing_unapplied"})
        else:
            excluded_rows.append(
                {**row, "production_status": "planned_candidate_exclusion_unapplied"}
            )
    return new_rows, merge_rows, excluded_rows, blocked_rows, blocked_old_ids


def verify_inputs() -> None:
    validation = json.loads(VALIDATION.read_text(encoding="utf-8"))
    if sha256(COMPLETED) != validation["input_sha256"][COMPLETED.name]:
        raise ValueError("Completed collisions differ from validation provenance")
    if validation["status"] != "validated_existing_event_collision_decisions_unapplied":
        raise ValueError("Existing-event collision validation has the wrong status")


def main() -> int:
    verify_inputs()
    collision_rows = read_csv(COMPLETED)
    new_rows, merges, excluded, blocked, blocked_old_ids = materialize(collision_rows)
    mapping = read_csv(MAPPING_DECISIONS)
    resolved_old_ids = {row["event_id"] for row in mapping if row["final_resolution"] != "unclear"}
    safe_superseded = resolved_old_ids - blocked_old_ids
    common_columns = list(collision_rows[0])
    write_csv(NEW_OUTPUT, new_rows, common_columns + ["production_status"])
    write_csv(MERGE_OUTPUT, merges, common_columns + ["production_status"])
    write_csv(EXCLUDE_OUTPUT, excluded, common_columns + ["production_status"])
    write_csv(
        BLOCKED_OUTPUT,
        blocked,
        common_columns + ["blocked_reason", "production_status"],
    )
    input_paths = (COMPLETED, VALIDATION, MAPPING_DECISIONS, SCRIPT_PATH)
    output_paths = (NEW_OUTPUT, MERGE_OUTPUT, EXCLUDE_OUTPUT, BLOCKED_OUTPUT)
    manifest = {
        "validated_candidate_rows": len(collision_rows),
        "eligible_new_candidates": len(new_rows),
        "safe_merges_into_existing": len(merges),
        "excluded_candidates": len(excluded),
        "blocked_candidates": len(blocked),
        "blocked_old_event_bundles": len(blocked_old_ids),
        "safe_superseded_old_events": len(safe_superseded),
        "input_sha256": {str(path.relative_to(ROOT)): sha256(path) for path in input_paths},
        "output_sha256": {path.name: sha256(path) for path in output_paths},
        "status": "unapplied_final_candidate_collision_check_required",
    }
    MANIFEST_OUTPUT.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    REPORT_OUTPUT.write_text(
        "\n".join(
            [
                f"# {REPORT_TITLE}",
                "",
                f"Validated candidates: {len(collision_rows)}",
                f"Eligible proposed new events: {len(new_rows)}",
                f"Safe merges into existing events: {len(merges)}",
                f"Excluded candidates: {len(excluded)}",
                f"Blocked candidates: {len(blocked)}",
                f"Blocked old-event bundles retained unchanged: {len(blocked_old_ids)}",
                f"Old events safe to supersede: {len(safe_superseded)}",
                "",
                "Blocked bundles contain at least one unclear collision decision and",
                "remain wholly unapplied to avoid partial duplicate identities.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"Wrote {len(new_rows)} new candidates to {NEW_OUTPUT}")
    print(f"Wrote {len(merges)} merges to {MERGE_OUTPUT}")
    print(f"Wrote {len(excluded)} exclusions to {EXCLUDE_OUTPUT}")
    print(f"Wrote {len(blocked)} blocked candidates to {BLOCKED_OUTPUT}")
    print(f"Wrote {MANIFEST_OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
