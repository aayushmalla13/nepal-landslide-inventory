#!/usr/bin/env python3
"""Normalize incomplete v0.9 mapping decisions without inventing event attributes."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "outputs"
COMPLETED = OUTPUT / "v09_article_mapping_DECISIONS_COMPLETED.csv"
ORIGINAL = OUTPUT / "v09_article_mapping_DECISIONS_SUBMITTED.csv"
LOG = OUTPUT / "v09_article_mapping_normalization_log.csv"
MANIFEST = OUTPUT / "v09_article_mapping_normalization_manifest.json"
ORIGINAL_SHA256 = "4112692373007d1767472f8615f619715f588931a9e889abf4a14fab819b749b"

UNCLEAR_ROWS = {
    "V9R-001",
    "V9R-006",
    "V9R-014",
    "V9R-020",
    "V9R-022",
    "V9R-036",
    "V9R-042",
    "V9R-043",
    "V9R-045",
    "V9R-047",
    "V9R-048",
    "V9R-054",
    "V9R-060",
    "V9R-061",
    "V9R-070",
    "V9R-081",
    "V9R-108",
    "V9R-112",
}
RETAIN_GROUPS = {
    "V9R-031": {"G4"},
    "V9R-041": {"G1", "G2"},
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def normalize_rows(
    rows: list[dict[str, str]],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    normalized: list[dict[str, str]] = []
    log: list[dict[str, str]] = []
    seen: set[str] = set()
    for source in rows:
        row = dict(source)
        queue_id = row["queue_id"]
        if queue_id in UNCLEAR_ROWS:
            seen.add(queue_id)
            original_resolution = row["final_resolution"]
            row["final_resolution"] = "unclear"
            row["final_event_count"] = ""
            row["final_event_groups_json"] = ""
            row["excluded_article_mapping_ids_json"] = ""
            log.append(
                {
                    "queue_id": queue_id,
                    "original_resolution": original_resolution,
                    "normalized_resolution": "unclear",
                    "normalization_action": "clear_non_actionable_event_fields",
                    "reason": (
                        "Reviewer notes do not support every required event attribute; "
                        "no date, district, group, or exclusion was invented."
                    ),
                }
            )
        elif queue_id in RETAIN_GROUPS:
            seen.add(queue_id)
            groups = json.loads(row["final_event_groups_json"])
            retained = [group for group in groups if group["group_id"] in RETAIN_GROUPS[queue_id]]
            if len(retained) != len(RETAIN_GROUPS[queue_id]):
                raise ValueError(f"{queue_id}: expected retained groups are absent")
            row["final_event_count"] = str(len(retained))
            row["final_event_groups_json"] = json.dumps(
                retained, ensure_ascii=False, separators=(",", ":")
            )
            row["excluded_article_mapping_ids_json"] = "[]"
            log.append(
                {
                    "queue_id": queue_id,
                    "original_resolution": source["final_resolution"],
                    "normalized_resolution": row["final_resolution"],
                    "normalization_action": "retain_complete_event_groups_only",
                    "reason": (
                        "Retained only reviewer-defined groups with nonblank required "
                        "date and district fields."
                    ),
                }
            )
        normalized.append(row)
    expected = UNCLEAR_ROWS | set(RETAIN_GROUPS)
    if seen != expected:
        raise ValueError(f"Normalization rows missing from submission: {sorted(expected - seen)}")
    return normalized, log


def main() -> int:
    if ORIGINAL.exists():
        if sha256(ORIGINAL) != ORIGINAL_SHA256:
            raise ValueError("Preserved original submission differs from its locked hash")
    else:
        if sha256(COMPLETED) != ORIGINAL_SHA256:
            raise ValueError("Completed submission differs from the expected original hash")
        ORIGINAL.write_bytes(COMPLETED.read_bytes())

    normalized, log = normalize_rows(read_csv(ORIGINAL))
    write_csv(COMPLETED, normalized)
    write_csv(LOG, log)
    manifest = {
        "audit": "v09_article_mapping_submission_normalization_v1",
        "policy": (
            "Preserve the original submission; clear unresolved event definitions and "
            "retain only reviewer-defined groups with complete required attributes."
        ),
        "normalized_rows": len(log),
        "unclear_rows": len(UNCLEAR_ROWS),
        "partial_group_rows": len(RETAIN_GROUPS),
        "input_sha256": {ORIGINAL.name: sha256(ORIGINAL)},
        "output_sha256": {
            COMPLETED.name: sha256(COMPLETED),
            LOG.name: sha256(LOG),
            Path(__file__).name: sha256(Path(__file__)),
        },
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Preserved original submission at {ORIGINAL}")
    print(f"Normalized {len(log)} rows in {COMPLETED}")
    print(f"Wrote {LOG}")
    print(f"Wrote {MANIFEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
