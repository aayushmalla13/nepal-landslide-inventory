#!/usr/bin/env python3
"""Validate final reconstruction-to-frozen collision decisions."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "outputs"
TEMPLATE = OUTPUT / "canonical_event_reconstruction_FINAL_COLLISION_DECISIONS.csv"
PAIRS = OUTPUT / "canonical_event_reconstruction_FINAL_COLLISION_PAIRS.csv"
MANIFEST = OUTPUT / "canonical_event_collision_gate_FINAL_manifest.json"
DEFAULT_COMPLETED = OUTPUT / "canonical_event_reconstruction_FINAL_COLLISION_DECISIONS_COMPLETED.csv"
VALIDATION_OUTPUT = OUTPUT / "canonical_event_collision_decisions_validation.json"

FINAL_COLUMNS = {
    "final_collision_action", "merge_target_event_id",
    "reviewed_by_collision", "collision_review_notes",
}
ACTIONS = {"new_event", "merge_existing", "exclude_duplicate", "exclude_candidate", "unclear"}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate(
    completed: list[dict[str, str]],
    template: list[dict[str, str]],
    pairs: list[dict[str, str]],
) -> dict[str, object]:
    if len(completed) != len(template):
        raise ValueError(f"Expected {len(template)} collision rows, found {len(completed)}.")
    if [row["candidate_event_id"] for row in completed] != [row["candidate_event_id"] for row in template]:
        raise ValueError("Candidate IDs or order differ from the blank collision sheet.")
    valid_targets: dict[str, set[str]] = {}
    for pair in pairs:
        valid_targets.setdefault(pair["candidate_event_id"], set()).add(pair["existing_event_id"])

    counts: Counter[str] = Counter()
    merge_targets: Counter[str] = Counter()
    for row, blank in zip(completed, template, strict=True):
        row_id = row["candidate_event_id"]
        for column in blank:
            if column not in FINAL_COLUMNS and row.get(column, "") != blank.get(column, ""):
                raise ValueError(f"{row_id}: frozen column {column} changed.")
        action = row["final_collision_action"].strip()
        target = row["merge_target_event_id"].strip()
        if action not in ACTIONS:
            raise ValueError(f"{row_id}: invalid or blank final_collision_action.")
        if not row["reviewed_by_collision"].strip():
            raise ValueError(f"{row_id}: reviewed_by_collision is blank.")
        if action in {"merge_existing", "exclude_duplicate"}:
            if target not in valid_targets.get(row_id, set()):
                raise ValueError(f"{row_id}: merge target is absent from its collision pairs.")
            if not row["collision_review_notes"].strip():
                raise ValueError(f"{row_id}: merge/exclusion decision requires review notes.")
            merge_targets[target] += 1
        elif target:
            raise ValueError(f"{row_id}: merge target is only valid for merge or duplicate exclusion.")
        counts[action] += 1
    return {
        "decision_rows": len(completed),
        "action_counts": dict(counts),
        "unique_merge_targets": len(merge_targets),
        "unresolved_rows": counts["unclear"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("completed", nargs="?", type=Path, default=DEFAULT_COMPLETED)
    args = parser.parse_args()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if sha256(TEMPLATE) != manifest["outputs"][TEMPLATE.name]:
        raise ValueError("Collision decision template differs from its manifest.")
    if sha256(PAIRS) != manifest["outputs"][PAIRS.name]:
        raise ValueError("Collision pair table differs from its manifest.")
    result = validate(read_csv(args.completed), read_csv(TEMPLATE), read_csv(PAIRS))
    result["inputs"] = {
        args.completed.name: sha256(args.completed),
        TEMPLATE.name: sha256(TEMPLATE),
        PAIRS.name: sha256(PAIRS),
        MANIFEST.name: sha256(MANIFEST),
    }
    result["status"] = (
        "blocked_unresolved_collision_decisions"
        if result["unresolved_rows"] else "validated_collision_decisions_not_yet_applied"
    )
    VALIDATION_OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Validated {result['decision_rows']} collision decisions.")
    print(f"Wrote {VALIDATION_OUTPUT}")


if __name__ == "__main__":
    main()
