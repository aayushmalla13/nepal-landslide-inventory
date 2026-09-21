#!/usr/bin/env python3
"""Validate date decisions and materialize a date-resolved candidate set."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "outputs"
GROUPS = OUTPUT / "post_correction_reconstruction_GROUPS.csv"
RECONSTRUCTION_MANIFEST = OUTPUT / "post_correction_reconstruction_manifest.json"
DATE_TEMPLATE = OUTPUT / "post_correction_reconstruction_DATE_REVIEW.csv"
DATE_MANIFEST = OUTPUT / "post_correction_date_review_manifest.json"
DEFAULT_COMPLETED = OUTPUT / "post_correction_reconstruction_DATE_REVIEW_COMPLETED.csv"
RESOLVED_GROUPS = OUTPUT / "post_correction_reconstruction_GROUPS_DATE_RESOLVED.csv"
EXCLUDED_CANDIDATES = OUTPUT / "post_correction_reconstruction_DATE_EXCLUDED.csv"
MANIFEST_OUTPUT = OUTPUT / "post_correction_date_resolution_manifest.json"
REPORT_OUTPUT = OUTPUT / "post_correction_date_resolution_report.md"

FINAL_COLUMNS = {"final_action", "resolved_event_date", "reviewed_by", "review_notes"}
MIN_DATE = date(2015, 1, 1)
MAX_DATE = date(2026, 8, 9)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
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


def validate(completed: list[dict[str, str]], template: list[dict[str, str]]) -> None:
    if len(completed) != len(template):
        raise ValueError(f"Expected {len(template)} date rows, found {len(completed)}")
    if [row["candidate_event_id"] for row in completed] != [
        row["candidate_event_id"] for row in template
    ]:
        raise ValueError("Candidate IDs or order differ from the blank date review")
    for row, blank in zip(completed, template, strict=True):
        candidate_id = row["candidate_event_id"]
        for column in blank:
            if column not in FINAL_COLUMNS and row.get(column, "") != blank.get(column, ""):
                raise ValueError(f"{candidate_id}: frozen column {column} changed")
        action = row["final_action"].strip()
        if action not in {"set_date", "exclude_candidate"}:
            raise ValueError(
                f"{candidate_id}: final_action must be set_date or exclude_candidate"
            )
        if not row["reviewed_by"].strip():
            raise ValueError(f"{candidate_id}: reviewed_by is blank")
        value = row["resolved_event_date"].strip()
        if action == "exclude_candidate":
            if value:
                raise ValueError(f"{candidate_id}: excluded candidate must not have a date")
            continue
        try:
            parsed = date.fromisoformat(value)
        except ValueError as error:
            raise ValueError(f"{candidate_id}: date must use YYYY-MM-DD") from error
        if not MIN_DATE <= parsed <= MAX_DATE:
            raise ValueError(f"{candidate_id}: date is outside the inventory period")


def resolve(
    groups: list[dict[str, str]], completed: list[dict[str, str]]
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    decisions = {row["candidate_event_id"]: row for row in completed}
    resolved: list[dict[str, str]] = []
    excluded: list[dict[str, str]] = []
    for source in groups:
        row = dict(source)
        decision = decisions.get(row["candidate_event_id"])
        if decision is None:
            resolved.append(row)
        elif decision["final_action"].strip() == "exclude_candidate":
            excluded.append(
                {
                    "candidate_event_id": row["candidate_event_id"],
                    "queue_id": row["queue_id"],
                    "old_event_id": row["old_event_id"],
                    "district": row["district"],
                    "evidence": row["evidence"],
                    "reviewed_by": decision["reviewed_by"].strip(),
                    "review_notes": decision["review_notes"].strip(),
                    "production_status": "candidate_excluded_date_unresolved",
                }
            )
        else:
            row["event_date"] = decision["resolved_event_date"].strip()
            row["review_notes"] = " | ".join(
                value
                for value in (row["review_notes"], decision["review_notes"].strip())
                if value
            )
            resolved.append(row)
    return resolved, excluded


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("completed", nargs="?", type=Path, default=DEFAULT_COMPLETED)
    args = parser.parse_args()
    date_manifest = json.loads(DATE_MANIFEST.read_text(encoding="utf-8"))
    if sha256(DATE_TEMPLATE) != date_manifest["output_sha256"][DATE_TEMPLATE.name]:
        raise ValueError("Date-review template differs from its manifest")
    reconstruction = json.loads(RECONSTRUCTION_MANIFEST.read_text(encoding="utf-8"))
    if sha256(GROUPS) != reconstruction["output_sha256"][GROUPS.name]:
        raise ValueError("Reconstruction groups differ from their manifest")
    completed = read_csv(args.completed)
    template = read_csv(DATE_TEMPLATE)
    validate(completed, template)
    groups = read_csv(GROUPS)
    resolved, excluded = resolve(groups, completed)
    write_csv(RESOLVED_GROUPS, resolved, list(groups[0]))
    exclusion_columns = list(excluded[0]) if excluded else [
        "candidate_event_id",
        "queue_id",
        "old_event_id",
        "district",
        "evidence",
        "reviewed_by",
        "review_notes",
        "production_status",
    ]
    write_csv(EXCLUDED_CANDIDATES, excluded, exclusion_columns)
    manifest: dict[str, Any] = {
        "input_candidates": len(groups),
        "dates_resolved": sum(row["final_action"] == "set_date" for row in completed),
        "candidates_excluded": len(excluded),
        "retained_candidates": len(resolved),
        "input_sha256": {
            path.name: sha256(path)
            for path in (GROUPS, RECONSTRUCTION_MANIFEST, DATE_TEMPLATE, DATE_MANIFEST)
        }
        | {args.completed.name: sha256(args.completed)},
        "output_sha256": {
            path.name: sha256(path) for path in (RESOLVED_GROUPS, EXCLUDED_CANDIDATES)
        },
        "status": "date_resolved_collision_check_required",
    }
    MANIFEST_OUTPUT.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    REPORT_OUTPUT.write_text(
        "\n".join(
            [
                "# Post-correction reconstruction date resolution",
                "",
                f"Candidates reviewed: {len(completed)}",
                f"Dates resolved: {manifest['dates_resolved']}",
                f"Candidates excluded: {len(excluded)}",
                f"Candidates retained for collision screening: {len(resolved)}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"Validated {len(completed)} date decisions")
    print(f"Wrote {len(resolved)} rows to {RESOLVED_GROUPS}")
    print(f"Wrote {len(excluded)} rows to {EXCLUDED_CANDIDATES}")
    print(f"Wrote {MANIFEST_OUTPUT}")
    print(f"Wrote {REPORT_OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
