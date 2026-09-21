#!/usr/bin/env python3
"""Validate completed post-correction article-mapping decisions."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "outputs"
TEMPLATE = OUTPUT / "post_correction_article_mapping_DECISIONS.csv"
ARTICLE_MAP = OUTPUT / "post_correction_article_membership_MAP.csv"
MAPPING_MANIFEST = OUTPUT / "post_correction_article_mapping_manifest.json"
DEFAULT_COMPLETED = OUTPUT / "post_correction_article_mapping_DECISIONS_COMPLETED.csv"
VALIDATION_OUTPUT = OUTPUT / "post_correction_article_mapping_validation.json"

FINAL_COLUMNS = {
    "final_resolution",
    "final_event_count",
    "final_event_groups_json",
    "excluded_article_mapping_ids_json",
    "reviewed_by",
    "review_notes",
}
RESOLUTIONS = {
    "exclude_cluster",
    "keep_cluster",
    "decompose_source_article",
    "recluster_articles",
    "recluster_and_decompose",
    "unclear",
}
GROUP_FIELDS = {
    "group_id",
    "article_mapping_ids",
    "event_date",
    "district",
    "municipality",
    "event_type",
    "hazard_type",
    "deaths",
    "evidence",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_json_list(value: str, queue_id: str, field: str) -> list[Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as error:
        raise ValueError(f"{queue_id}: {field} is not valid JSON") from error
    if not isinstance(parsed, list):
        raise ValueError(f"{queue_id}: {field} must be a JSON list")
    return parsed


def validate(
    completed: list[dict[str, str]],
    template: list[dict[str, str]],
    mapping_rows: list[dict[str, str]],
) -> dict[str, int]:
    if len(completed) != len(template):
        raise ValueError(f"Expected {len(template)} decision rows, found {len(completed)}")
    if [row["queue_id"] for row in completed] != [row["queue_id"] for row in template]:
        raise ValueError("Queue IDs or row order differ from the blank decision sheet")
    mapping_ids: dict[str, set[str]] = {}
    for row in mapping_rows:
        mapping_ids.setdefault(row["queue_id"], set()).add(row["mapping_id"])

    total_groups = excluded_clusters = unresolved = 0
    for row, blank in zip(completed, template, strict=True):
        queue_id = row["queue_id"]
        for column in blank:
            if column not in FINAL_COLUMNS and row.get(column, "") != blank.get(column, ""):
                raise ValueError(f"{queue_id}: frozen column {column} changed")
        resolution = row["final_resolution"].strip()
        if resolution not in RESOLUTIONS:
            raise ValueError(f"{queue_id}: invalid or blank final_resolution")
        if not row["reviewed_by"].strip():
            raise ValueError(f"{queue_id}: reviewed_by is blank")
        available = mapping_ids.get(queue_id, set())

        if resolution == "unclear":
            if row["final_event_count"].strip() or row["final_event_groups_json"].strip():
                raise ValueError(f"{queue_id}: unclear resolution must not define events")
            unresolved += 1
            continue

        try:
            event_count = int(row["final_event_count"])
        except ValueError as error:
            raise ValueError(f"{queue_id}: final_event_count must be an integer") from error
        groups = parse_json_list(
            row["final_event_groups_json"], queue_id, "final_event_groups_json"
        )
        excluded = parse_json_list(
            row["excluded_article_mapping_ids_json"],
            queue_id,
            "excluded_article_mapping_ids_json",
        )
        if not all(isinstance(value, str) for value in excluded):
            raise ValueError(f"{queue_id}: excluded mapping IDs must be strings")
        excluded_set = set(excluded)
        if len(excluded_set) != len(excluded) or not excluded_set <= available:
            raise ValueError(f"{queue_id}: excluded mapping IDs are duplicate or unknown")

        if resolution == "exclude_cluster":
            if event_count != 0 or groups or excluded_set != available:
                raise ValueError(
                    f"{queue_id}: exclusion requires zero events, no groups, "
                    "and all articles excluded"
                )
            excluded_clusters += 1
            continue
        if event_count <= 0 or event_count != len(groups):
            raise ValueError(
                f"{queue_id}: event count must equal the positive number of groups"
            )

        group_ids: set[str] = set()
        used: set[str] = set()
        for group in groups:
            if not isinstance(group, dict) or not GROUP_FIELDS <= set(group):
                raise ValueError(f"{queue_id}: each event group needs all required fields")
            group_id = str(group["group_id"]).strip()
            if not group_id or group_id in group_ids:
                raise ValueError(f"{queue_id}: group IDs must be nonblank and unique")
            group_ids.add(group_id)
            members = group["article_mapping_ids"]
            if (
                not isinstance(members, list)
                or not members
                or not all(isinstance(value, str) for value in members)
            ):
                raise ValueError(
                    f"{queue_id}/{group_id}: article_mapping_ids must be a nonempty list"
                )
            if not set(members) <= available:
                raise ValueError(f"{queue_id}/{group_id}: unknown mapping ID")
            if len(set(members)) != len(members):
                raise ValueError(f"{queue_id}/{group_id}: duplicate mapping ID")
            for field in GROUP_FIELDS - {"group_id", "article_mapping_ids", "municipality"}:
                if not str(group[field]).strip():
                    raise ValueError(f"{queue_id}/{group_id}: {field} is blank")
            used.update(members)
        if used & excluded_set:
            raise ValueError(f"{queue_id}: an article is retained and excluded")
        if used | excluded_set != available:
            raise ValueError(f"{queue_id}: every article must be retained or excluded")
        total_groups += len(groups)

    return {
        "decision_rows": len(completed),
        "retained_event_groups": total_groups,
        "excluded_clusters": excluded_clusters,
        "unresolved_clusters": unresolved,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("completed", nargs="?", type=Path, default=DEFAULT_COMPLETED)
    args = parser.parse_args()
    manifest = json.loads(MAPPING_MANIFEST.read_text(encoding="utf-8"))
    for path in (TEMPLATE, ARTICLE_MAP):
        if sha256(path) != manifest["output_sha256"][path.name]:
            raise ValueError(f"Locked article-mapping artifact changed: {path.name}")
    result: dict[str, Any] = validate(
        read_csv(args.completed), read_csv(TEMPLATE), read_csv(ARTICLE_MAP)
    )
    result["inputs"] = {
        args.completed.name: sha256(args.completed),
        TEMPLATE.name: sha256(TEMPLATE),
        ARTICLE_MAP.name: sha256(ARTICLE_MAP),
        MAPPING_MANIFEST.name: sha256(MAPPING_MANIFEST),
    }
    result["status"] = "validated_mapping_decisions_not_yet_applied"
    VALIDATION_OUTPUT.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"Validated {result['decision_rows']} mapping decisions")
    print(f"Wrote {VALIDATION_OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
