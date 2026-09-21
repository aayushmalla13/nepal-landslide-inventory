#!/usr/bin/env python3
"""Build the locked date-review pack for post-correction event candidates."""

from __future__ import annotations

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
ARTICLE_MAP = OUTPUT / "post_correction_article_membership_MAP.csv"
MAPPING_MANIFEST = OUTPUT / "post_correction_article_mapping_manifest.json"
DATE_REVIEW = OUTPUT / "post_correction_reconstruction_DATE_REVIEW.csv"
MANIFEST_OUTPUT = OUTPUT / "post_correction_date_review_manifest.json"
REPORT_OUTPUT = OUTPUT / "post_correction_date_review_report.md"

DATE_REVIEW_COLUMNS = [
    "candidate_event_id",
    "queue_id",
    "row_id",
    "old_event_id",
    "district",
    "municipality",
    "event_type",
    "hazard_type",
    "deaths",
    "article_mapping_ids_json",
    "article_urls_json",
    "event_evidence",
    "source_evidence",
    "final_action",
    "resolved_event_date",
    "reviewed_by",
    "review_notes",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
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


def parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def build_date_review(
    groups: list[dict[str, str]], mapping_by_id: dict[str, dict[str, str]]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for group in groups:
        if parse_date(group["event_date"]) is not None:
            continue
        mapping_ids = json.loads(group["article_mapping_ids_json"])
        evidence_parts: list[str] = []
        for mapping_id in mapping_ids:
            source = mapping_by_id[mapping_id]
            evidence_parts.append(
                f"{mapping_id}\nTITLE: {source['title']}\n"
                f"PUBLISHED: {source['published_date_ad']}\nTEXT:\n{source['article_text']}"
            )
        rows.append(
            {
                "candidate_event_id": group["candidate_event_id"],
                "queue_id": group["queue_id"],
                "row_id": group["row_id"],
                "old_event_id": group["old_event_id"],
                "district": group["district"],
                "municipality": group["municipality"],
                "event_type": group["event_type"],
                "hazard_type": group["hazard_type"],
                "deaths": group["deaths"],
                "article_mapping_ids_json": group["article_mapping_ids_json"],
                "article_urls_json": group["article_urls_json"],
                "event_evidence": group["evidence"],
                "source_evidence": "\n\n---\n\n".join(evidence_parts),
                "final_action": "",
                "resolved_event_date": "",
                "reviewed_by": "",
                "review_notes": "",
            }
        )
    return rows


def verify_inputs() -> None:
    reconstruction = json.loads(RECONSTRUCTION_MANIFEST.read_text(encoding="utf-8"))
    if sha256(GROUPS) != reconstruction["output_sha256"][GROUPS.name]:
        raise ValueError("Reconstruction groups differ from their manifest")
    mapping = json.loads(MAPPING_MANIFEST.read_text(encoding="utf-8"))
    if sha256(ARTICLE_MAP) != mapping["output_sha256"][ARTICLE_MAP.name]:
        raise ValueError("Article map differs from its manifest")


def main() -> int:
    verify_inputs()
    groups = read_csv(GROUPS)
    mapping_by_id = {row["mapping_id"]: row for row in read_csv(ARTICLE_MAP)}
    date_review = build_date_review(groups, mapping_by_id)
    if len(date_review) != 30:
        raise ValueError(f"Expected 30 date-review rows, found {len(date_review)}")
    if len({row["candidate_event_id"] for row in date_review}) != len(date_review):
        raise ValueError("Duplicate candidate in date-review pack")
    write_csv(DATE_REVIEW, date_review, DATE_REVIEW_COLUMNS)
    manifest = {
        "audit": "post_correction_reconstruction_date_review_v1",
        "candidate_rows": len(groups),
        "date_review_rows": len(date_review),
        "status": "date_review_template_no_production_changes",
        "input_sha256": {
            path.name: sha256(path)
            for path in (GROUPS, RECONSTRUCTION_MANIFEST, ARTICLE_MAP, MAPPING_MANIFEST)
        },
        "output_sha256": {DATE_REVIEW.name: sha256(DATE_REVIEW)},
    }
    MANIFEST_OUTPUT.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    REPORT_OUTPUT.write_text(
        "\n".join(
            [
                "# Post-correction reconstruction date review",
                "",
                f"Reconstructed candidates: {len(groups)}",
                f"Candidates with valid dates: {len(groups) - len(date_review)}",
                f"Candidates requiring date review: {len(date_review)}",
                "",
                "No candidate or production event was changed.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"Wrote {len(date_review)} date-review rows to {DATE_REVIEW}")
    print(f"Wrote {MANIFEST_OUTPUT}")
    print(f"Wrote {REPORT_OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
