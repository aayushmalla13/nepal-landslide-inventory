#!/usr/bin/env python3
"""Validate a completed current-state dedup collision review batch."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "outputs"
TEMPLATE = OUTPUT / "dedup_collision_review_BATCH_01_LABEL_HERE.csv"
MANIFEST = OUTPUT / "dedup_collision_review_manifest.json"
DEFAULT_COMPLETED = OUTPUT / "dedup_collision_review_BATCH_01_COMPLETED.csv"
VALIDATION_OUTPUT = OUTPUT / "dedup_collision_review_BATCH_01_validation.json"
EDITABLE_COLUMNS = {"decision", "merge_survivor_event_id", "reviewed_by", "review_notes"}
DECISIONS = {"merge", "keep_distinct", "unclear"}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find(parents: dict[str, str], item: str) -> str:
    root = parents.setdefault(item, item)
    if root != item:
        root = find(parents, root)
        parents[item] = root
    return root


def union(parents: dict[str, str], left: str, right: str) -> None:
    left_root = find(parents, left)
    right_root = find(parents, right)
    if left_root != right_root:
        parent, child = sorted((left_root, right_root))
        parents[child] = parent


def validate(completed: list[dict[str, str]], template: list[dict[str, str]]) -> dict[str, object]:
    if len(completed) != len(template):
        raise ValueError(f"Expected {len(template)} rows, found {len(completed)}.")
    if [row["pair_id"] for row in completed] != [row["pair_id"] for row in template]:
        raise ValueError("Pair IDs or row order differ from the blank review sheet.")

    counts: Counter[str] = Counter()
    parents: dict[str, str] = {}
    distinct_edges: list[tuple[str, str, str]] = []
    survivor_votes: list[tuple[str, str, str]] = []
    for row, blank in zip(completed, template, strict=True):
        pair_id = row["pair_id"]
        for column in blank:
            if column not in EDITABLE_COLUMNS and row.get(column, "") != blank.get(column, ""):
                raise ValueError(f"{pair_id}: frozen column {column} changed.")
        decision = row["decision"].strip()
        survivor = row["merge_survivor_event_id"].strip()
        reviewer = row["reviewed_by"].strip()
        notes = row["review_notes"].strip()
        left = row["left_event_id"]
        right = row["right_event_id"]
        if decision not in DECISIONS:
            raise ValueError(f"{pair_id}: invalid or blank decision.")
        if not reviewer:
            raise ValueError(f"{pair_id}: reviewed_by is blank.")
        if decision == "merge":
            if not survivor:
                raise ValueError(f"{pair_id}: merge survivor is required.")
            if not notes:
                raise ValueError(f"{pair_id}: merge requires review notes.")
            union(parents, left, right)
            survivor_votes.append((pair_id, left, survivor))
        else:
            if survivor:
                raise ValueError(f"{pair_id}: survivor is only valid for merge decisions.")
            if decision == "unclear" and not notes:
                raise ValueError(f"{pair_id}: unclear requires review notes.")
            if decision == "keep_distinct":
                distinct_edges.append((pair_id, left, right))
        counts[decision] += 1

    for pair_id, left, right in distinct_edges:
        if find(parents, left) == find(parents, right):
            raise ValueError(
                f"{pair_id}: keep_distinct contradicts a transitive merge in the same group."
            )
    survivors_by_component: dict[str, set[str]] = {}
    for pair_id, member, survivor in survivor_votes:
        if find(parents, member) != find(parents, survivor):
            raise ValueError(
                f"{pair_id}: merge survivor must belong to the transitive merge component."
            )
        survivors_by_component.setdefault(find(parents, member), set()).add(survivor)
    survivor_conflicts = {
        component: sorted(survivors)
        for component, survivors in survivors_by_component.items()
        if len(survivors) > 1
    }
    blocked = bool(counts["unclear"] or survivor_conflicts)
    return {
        "review_rows": len(completed),
        "decision_counts": dict(counts),
        "unresolved_rows": counts["unclear"],
        "survivor_conflict_components": survivor_conflicts,
        "survivor_conflict_count": len(survivor_conflicts),
        "status": (
            "blocked_unresolved_or_inconsistent_collision_decisions"
            if blocked else "validated_collision_batch_not_yet_applied"
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("completed", nargs="?", type=Path, default=DEFAULT_COMPLETED)
    args = parser.parse_args()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if sha256(TEMPLATE) != manifest["outputs"][TEMPLATE.name]:
        raise ValueError("Blank review sheet differs from its manifest.")
    result = validate(read_csv(args.completed), read_csv(TEMPLATE))
    result["inputs"] = {
        args.completed.name: sha256(args.completed),
        TEMPLATE.name: sha256(TEMPLATE),
        MANIFEST.name: sha256(MANIFEST),
    }
    VALIDATION_OUTPUT.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"Validated {result['review_rows']} collision decisions.")
    print(f"Wrote {VALIDATION_OUTPUT}")


if __name__ == "__main__":
    main()
