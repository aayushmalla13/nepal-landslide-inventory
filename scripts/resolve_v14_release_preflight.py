#!/usr/bin/env python3
"""Exclude reviewed reconstructions that cannot satisfy the release date schema."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/outputs"
IDENTITY_MANIFEST = OUTPUT / "v14_identity_plan_manifest.json"
ORIGINAL_NEW = OUTPUT / "v14_identity_plan_NEW_EVENTS.csv"
ORIGINAL_EXCLUDED = OUTPUT / "v14_identity_plan_EXCLUDED_CANDIDATES.csv"
STRUCTURED_MANIFEST = OUTPUT / "v14_structured_attribute_plan_manifest.json"
RELEASE_NEW = OUTPUT / "v14_release_identity_NEW_EVENTS.csv"
RELEASE_EXCLUDED = OUTPUT / "v14_release_identity_EXCLUDED_CANDIDATES.csv"
MANIFEST = OUTPUT / "v14_release_preflight_manifest.json"
REPORT = OUTPUT / "v14_release_preflight_report.md"


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
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


def has_exact_date(candidate: dict[str, str]) -> bool:
    try:
        date.fromisoformat(candidate["event_date"])
    except (KeyError, ValueError):
        return False
    return True


def exclusion_row(candidate: dict[str, str], columns: list[str]) -> dict[str, str]:
    row = {column: candidate.get(column, "") for column in columns}
    row.update(
        {
            "exclusion_stage": "release_preflight_exact_date",
            "duplicate_of_candidate_event_id": "",
            "reviewed_by": candidate.get("reviewed_by_final", ""),
            "review_notes": (
                "Release preflight exclusion: the source supports a distinct physical "
                "event but not an exact YYYY-MM-DD occurrence date required by the "
                "high-precision inventory schema. "
                + candidate.get("final_collision_notes", "")
            ),
            "production_status": "planned_exclude_candidate_unapplied",
        }
    )
    return row


def main() -> int:
    identity = json.loads(IDENTITY_MANIFEST.read_text(encoding="utf-8"))
    structured = json.loads(STRUCTURED_MANIFEST.read_text(encoding="utf-8"))
    if structured["status"] != "all_v14_manual_gates_complete_candidate_assembly_pending":
        raise ValueError("v1.4 manual gates are not complete")
    for path in (ORIGINAL_NEW, ORIGINAL_EXCLUDED):
        if sha256(path) != identity["output_sha256"][path.name]:
            raise ValueError(f"Identity artifact changed: {path.name}")

    new_columns, new_rows = read_csv(ORIGINAL_NEW)
    excluded_columns, excluded_rows = read_csv(ORIGINAL_EXCLUDED)
    blocked = [row for row in new_rows if not has_exact_date(row)]
    release_new = [row for row in new_rows if has_exact_date(row)]
    release_excluded = [
        *excluded_rows,
        *(exclusion_row(row, excluded_columns) for row in blocked),
    ]
    if not blocked:
        raise ValueError("Expected at least one exact-date release blocker")
    write_csv(RELEASE_NEW, new_columns, release_new)
    write_csv(RELEASE_EXCLUDED, excluded_columns, release_excluded)

    projected_rows = structured["provisional_rows_after_all_manual_plans"] - len(blocked)
    manifest = {
        "reason": "exact YYYY-MM-DD date required by high-precision release schema",
        "blocked_candidate_ids": sorted(row["candidate_event_id"] for row in blocked),
        "planned_new_events_before": len(new_rows),
        "planned_new_events_after": len(release_new),
        "excluded_candidates_before": len(excluded_rows),
        "excluded_candidates_after": len(release_excluded),
        "projected_release_rows": projected_rows,
        "input_sha256": {
            IDENTITY_MANIFEST.name: sha256(IDENTITY_MANIFEST),
            ORIGINAL_NEW.name: sha256(ORIGINAL_NEW),
            ORIGINAL_EXCLUDED.name: sha256(ORIGINAL_EXCLUDED),
            STRUCTURED_MANIFEST.name: sha256(STRUCTURED_MANIFEST),
        },
        "output_sha256": {
            RELEASE_NEW.name: sha256(RELEASE_NEW),
            RELEASE_EXCLUDED.name: sha256(RELEASE_EXCLUDED),
        },
        "status": "v14_release_preflight_exact_date_gate_complete",
    }
    MANIFEST.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    REPORT.write_text(
        "\n".join(
            [
                "# v1.4 release preflight",
                "",
                f"{len(blocked)} reviewed physical events are excluded from the release",
                "because their sources do not establish exact occurrence dates. The",
                "original reviewed identity plan remains preserved and unchanged.",
                "",
                f"Release-ready new events: {len(release_new)}",
                f"Release-ready excluded candidates: {len(release_excluded)}",
                f"Projected canonical rows: {projected_rows}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"Wrote {len(release_new)} rows to {RELEASE_NEW}")
    print(f"Wrote {len(release_excluded)} rows to {RELEASE_EXCLUDED}")
    print(f"Wrote {MANIFEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
