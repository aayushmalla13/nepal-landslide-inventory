#!/usr/bin/env python3
"""Validate date review and materialize a date-resolved reconstruction set."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "outputs"
GROUPS = OUTPUT / "canonical_event_reconstruction_GROUPS.csv"
RECONSTRUCTION_MANIFEST = OUTPUT / "canonical_event_reconstruction_manifest.json"
DATE_TEMPLATE = OUTPUT / "canonical_event_reconstruction_DATE_REVIEW.csv"
COLLISION_MANIFEST = OUTPUT / "canonical_event_collision_gate_manifest.json"
DEFAULT_COMPLETED = OUTPUT / "canonical_event_reconstruction_DATE_REVIEW_COMPLETED.csv"
RESOLVED_GROUPS = OUTPUT / "canonical_event_reconstruction_GROUPS_DATE_RESOLVED.csv"
EXCLUDED_CANDIDATES = OUTPUT / "canonical_event_reconstruction_DATE_EXCLUDED.csv"
MANIFEST_OUTPUT = OUTPUT / "canonical_event_reconstruction_date_resolution_manifest.json"
REPORT_OUTPUT = OUTPUT / "canonical_event_reconstruction_date_resolution_report.md"

FINAL_COLUMNS = {"final_action", "resolved_event_date", "reviewed_by", "review_notes"}
MIN_DATE = date(2015, 1, 1)
MAX_DATE = date(2026, 8, 9)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
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
        raise ValueError(f"Expected {len(template)} date rows, found {len(completed)}.")
    if [row["candidate_event_id"] for row in completed] != [row["candidate_event_id"] for row in template]:
        raise ValueError("Candidate IDs or order differ from the blank date review.")
    for row, blank in zip(completed, template, strict=True):
        row_id = row["candidate_event_id"]
        for column in blank:
            if column not in FINAL_COLUMNS and row.get(column, "") != blank.get(column, ""):
                raise ValueError(f"{row_id}: frozen column {column} changed.")
        action = row["final_action"].strip()
        if action not in {"set_date", "exclude_candidate"}:
            raise ValueError(f"{row_id}: final_action must be set_date or exclude_candidate.")
        if not row["reviewed_by"].strip():
            raise ValueError(f"{row_id}: reviewed_by is blank.")
        value = row["resolved_event_date"].strip()
        if action == "exclude_candidate":
            if value:
                raise ValueError(f"{row_id}: excluded candidate must not have a resolved date.")
            continue
        try:
            parsed = date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(f"{row_id}: resolved date must use YYYY-MM-DD.") from exc
        if not MIN_DATE <= parsed <= MAX_DATE:
            raise ValueError(f"{row_id}: resolved date is outside the frozen inventory period.")


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
                    "candidate_id": row["candidate_id"],
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
                value for value in (row["review_notes"], decision["review_notes"].strip()) if value
            )
            resolved.append(row)
    return resolved, excluded


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("completed", nargs="?", type=Path, default=DEFAULT_COMPLETED)
    args = parser.parse_args()
    collision_manifest = json.loads(COLLISION_MANIFEST.read_text(encoding="utf-8"))
    if sha256(DATE_TEMPLATE) != collision_manifest["outputs"][DATE_TEMPLATE.name]:
        raise ValueError("Date-review template differs from its collision-gate manifest.")
    reconstruction_manifest = json.loads(RECONSTRUCTION_MANIFEST.read_text(encoding="utf-8"))
    if sha256(GROUPS) != reconstruction_manifest["outputs"][GROUPS.name]:
        raise ValueError("Reconstruction groups differ from their manifest.")
    completed = read_csv(args.completed)
    template = read_csv(DATE_TEMPLATE)
    validate(completed, template)
    groups = read_csv(GROUPS)
    resolved, excluded = resolve(groups, completed)
    write_csv(RESOLVED_GROUPS, resolved, list(groups[0]))
    write_csv(EXCLUDED_CANDIDATES, excluded, list(excluded[0]))
    manifest = {
        "input_candidates": len(groups),
        "dates_resolved": sum(row["final_action"] == "set_date" for row in completed),
        "candidates_excluded": len(excluded),
        "retained_candidates": len(resolved),
        "inputs": {
            GROUPS.name: sha256(GROUPS),
            DATE_TEMPLATE.name: sha256(DATE_TEMPLATE),
            args.completed.name: sha256(args.completed),
            COLLISION_MANIFEST.name: sha256(COLLISION_MANIFEST),
        },
        "outputs": {
            RESOLVED_GROUPS.name: sha256(RESOLVED_GROUPS),
            EXCLUDED_CANDIDATES.name: sha256(EXCLUDED_CANDIDATES),
        },
        "status": "date_resolved_collision_check_required",
    }
    MANIFEST_OUTPUT.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    REPORT_OUTPUT.write_text(
        "\n".join(
            [
                "# Reconstruction date resolution",
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
    print(f"Validated {len(completed)} date decisions.")
    print(f"Wrote {len(resolved)} rows to {RESOLVED_GROUPS}")
    print(f"Wrote {len(excluded)} rows to {EXCLUDED_CANDIDATES}")
    print(f"Wrote {MANIFEST_OUTPUT}")
    print(f"Wrote {REPORT_OUTPUT}")


if __name__ == "__main__":
    main()
