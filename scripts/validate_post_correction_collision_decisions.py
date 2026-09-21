#!/usr/bin/env python3
"""Validate completed post-correction existing-event collision decisions."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "outputs"
TEMPLATE = OUTPUT / "post_correction_reconstruction_COLLISION_DECISIONS.csv"
PAIRS = OUTPUT / "post_correction_reconstruction_COLLISION_PAIRS.csv"
COLLISION_MANIFEST = OUTPUT / "post_correction_collision_manifest.json"
DEFAULT_COMPLETED = OUTPUT / "post_correction_reconstruction_COLLISION_DECISIONS_COMPLETED.csv"
VALIDATION_OUTPUT = OUTPUT / "post_correction_collision_validation.json"

FINAL_COLUMNS = {
    "final_action",
    "merge_existing_event_id",
    "reviewed_by",
    "collision_review_notes",
}
ACTIONS = {"new_event", "merge_existing", "exclude_duplicate", "exclude_candidate", "unclear"}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
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
) -> dict[str, Any]:
    if len(completed) != len(template):
        raise ValueError(f"Expected {len(template)} rows, found {len(completed)}")
    if [row["candidate_event_id"] for row in completed] != [
        row["candidate_event_id"] for row in template
    ]:
        raise ValueError("Candidate IDs or order differ from the locked template")
    allowed_merges: dict[str, set[str]] = {}
    for pair in pairs:
        allowed_merges.setdefault(pair["candidate_event_id"], set()).add(
            pair["existing_event_id"]
        )
    counts: Counter[str] = Counter()
    for row, blank in zip(completed, template, strict=True):
        candidate_id = row["candidate_event_id"]
        for column in blank:
            if column not in FINAL_COLUMNS and row.get(column, "") != blank.get(column, ""):
                raise ValueError(f"{candidate_id}: frozen column {column} changed")
        action = row["final_action"].strip()
        if action not in ACTIONS:
            raise ValueError(f"{candidate_id}: invalid or blank final_action")
        if not row["reviewed_by"].strip():
            raise ValueError(f"{candidate_id}: reviewed_by is blank")
        merge_id = row["merge_existing_event_id"].strip()
        if action == "merge_existing":
            if merge_id not in allowed_merges.get(candidate_id, set()):
                raise ValueError(f"{candidate_id}: merge target is not a collision candidate")
        elif merge_id:
            raise ValueError(f"{candidate_id}: merge target is only valid for merge_existing")
        counts[action] += 1
    return {
        "decision_rows": len(completed),
        "action_counts": dict(counts),
        "unresolved_rows": counts["unclear"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("completed", nargs="?", type=Path, default=DEFAULT_COMPLETED)
    args = parser.parse_args()
    manifest = json.loads(COLLISION_MANIFEST.read_text(encoding="utf-8"))
    for path in (TEMPLATE, PAIRS):
        if sha256(path) != manifest["output_sha256"][path.name]:
            raise ValueError(f"Locked collision artifact changed: {path.name}")
    result = validate(read_csv(args.completed), read_csv(TEMPLATE), read_csv(PAIRS))
    result["input_sha256"] = {
        args.completed.name: sha256(args.completed),
        TEMPLATE.name: sha256(TEMPLATE),
        PAIRS.name: sha256(PAIRS),
        COLLISION_MANIFEST.name: sha256(COLLISION_MANIFEST),
    }
    result["status"] = "validated_existing_event_collision_decisions_unapplied"
    VALIDATION_OUTPUT.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"Validated {result['decision_rows']} collision decisions")
    print(f"Wrote {VALIDATION_OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
