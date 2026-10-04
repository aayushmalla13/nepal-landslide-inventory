#!/usr/bin/env python3
"""Prepare the final v1.1 collision review, pre-filling low-risk candidates."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/outputs"
TEMPLATE = OUTPUT / "v11_reconstruction_FINAL_COLLISION_DECISIONS.csv"
MANIFEST = OUTPUT / "v11_final_collision_manifest.json"
REVIEW = OUTPUT / "v11_reconstruction_FINAL_COLLISION_REVIEW.csv"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def prepare(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    prepared: list[dict[str, str]] = []
    for source in rows:
        row = dict(source)
        if row["top_candidate_collision_tier"] in {"none", "low"}:
            row["final_candidate_action"] = "new_event"
            row["reviewed_by_final"] = "final_collision_screen_v1"
            row["final_collision_notes"] = (
                "No medium/high candidate collision; retained as a distinct event."
            )
        prepared.append(row)
    return prepared


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if sha256(TEMPLATE) != manifest["output_sha256"][TEMPLATE.name]:
        raise ValueError("Locked v1.1 final-collision template changed")
    with TEMPLATE.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = prepare(list(reader))
        columns = list(reader.fieldnames or [])
    with REVIEW.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    prefilled = sum(bool(row["final_candidate_action"]) for row in rows)
    print(f"Wrote {len(rows)} rows to {REVIEW}")
    print(f"Pre-filled {prefilled} low-risk rows; {len(rows) - prefilled} rows need review")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
