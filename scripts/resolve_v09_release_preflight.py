#!/usr/bin/env python3
"""Resolve release-schema blockers without rewriting reviewed v0.9 evidence."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "outputs"
IDENTITY_MANIFEST = OUTPUT / "v09_identity_plan_manifest.json"
ORIGINAL_NEW = OUTPUT / "v09_identity_plan_NEW_EVENTS.csv"
ORIGINAL_EXCLUDED = OUTPUT / "v09_identity_plan_EXCLUDED_CANDIDATES.csv"
RELEASE_NEW = OUTPUT / "v09_release_identity_NEW_EVENTS.csv"
RELEASE_EXCLUDED = OUTPUT / "v09_release_identity_EXCLUDED_CANDIDATES.csv"
MANIFEST = OUTPUT / "v09_release_preflight_manifest.json"
REPORT = OUTPUT / "v09_release_preflight_report.md"
TARGET = "v09_candidate_523169d15a745a34"


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


def exclusion_row(candidate: dict[str, str], columns: list[str]) -> dict[str, str]:
    if candidate["district"] != "Dailekh/Kalikot":
        raise ValueError("Target candidate no longer has the reviewed cross-district value")
    row = {column: candidate.get(column, "") for column in columns}
    row.update(
        {
            "exclusion_stage": "release_preflight_location",
            "duplicate_of_candidate_event_id": "",
            "reviewed_by": candidate.get("reviewed_by_final", ""),
            "review_notes": (
                "Release preflight exclusion: source places Dahikhola between Dullu "
                "Municipality (Dailekh) and Shubhakalika Rural Municipality (Kalikot), "
                "so the required single canonical district cannot be established. "
                + candidate.get("final_collision_notes", "")
            ),
            "production_status": "planned_exclude_candidate_unapplied",
        }
    )
    return row


def main() -> int:
    identity = json.loads(IDENTITY_MANIFEST.read_text(encoding="utf-8"))
    for path in (ORIGINAL_NEW, ORIGINAL_EXCLUDED):
        if sha256(path) != identity["output_sha256"][path.name]:
            raise ValueError(f"Identity artifact changed: {path.name}")

    new_columns, new_rows = read_csv(ORIGINAL_NEW)
    excluded_columns, excluded_rows = read_csv(ORIGINAL_EXCLUDED)
    targets = [row for row in new_rows if row["candidate_event_id"] == TARGET]
    if len(targets) != 1:
        raise ValueError(f"Expected exactly one preflight target: {TARGET}")
    release_new = [row for row in new_rows if row["candidate_event_id"] != TARGET]
    release_excluded = [*excluded_rows, exclusion_row(targets[0], excluded_columns)]
    write_csv(RELEASE_NEW, new_columns, release_new)
    write_csv(RELEASE_EXCLUDED, excluded_columns, release_excluded)

    manifest = {
        "target_candidate": TARGET,
        "reason": "single canonical district cannot be established from border evidence",
        "planned_new_events_before": len(new_rows),
        "planned_new_events_after": len(release_new),
        "excluded_candidates_before": len(excluded_rows),
        "excluded_candidates_after": len(release_excluded),
        "projected_release_rows": identity["planned_identity_layer_rows"] - 1 - 8,
        "input_sha256": {
            IDENTITY_MANIFEST.name: sha256(IDENTITY_MANIFEST),
            ORIGINAL_NEW.name: sha256(ORIGINAL_NEW),
            ORIGINAL_EXCLUDED.name: sha256(ORIGINAL_EXCLUDED),
        },
        "output_sha256": {
            RELEASE_NEW.name: sha256(RELEASE_NEW),
            RELEASE_EXCLUDED.name: sha256(RELEASE_EXCLUDED),
        },
        "status": "v09_release_preflight_location_gate_complete",
    }
    MANIFEST.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    REPORT.write_text(
        "\n".join(
            [
                "# v0.9 release preflight", "",
                "One reviewed physical event is excluded from the release because its",
                "source places Dahikhola on the Dailekh/Kalikot boundary and does not",
                "support the single canonical district required by the inventory schema.",
                "The original reviewed identity plan remains preserved and unchanged.", "",
                f"Release-ready new events: {len(release_new)}",
                f"Release-ready excluded candidates: {len(release_excluded)}",
                f"Projected canonical rows: {manifest['projected_release_rows']}", "",
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
