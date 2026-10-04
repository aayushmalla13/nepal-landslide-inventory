#!/usr/bin/env python3
"""Build the focused post-correction structured-attribute review sheet."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "outputs"
SOURCE = OUTPUT / "post_correction_remediation_BATCH_STRUCTURED_ATTRIBUTES.csv"
REMEDIATION_MANIFEST = OUTPUT / "post_correction_remediation_manifest.json"
IDENTITY_REMOVE = OUTPUT / "post_correction_identity_plan_REMOVE_OLD_EVENTS.csv"
IDENTITY_MERGES = OUTPUT / "post_correction_identity_plan_MERGES_EXISTING.csv"
IDENTITY_MANIFEST = OUTPUT / "post_correction_identity_plan_manifest.json"
TRUE_VALUE_COMPLETED = (
    OUTPUT / "post_correction_remediation_BATCH_TRUE_VALUE_REVIEW_COMPLETED.csv"
)
TRUE_VALUE_MANIFEST = OUTPUT / "post_correction_true_value_plan_manifest.json"
REVIEW_OUTPUT = OUTPUT / "post_correction_structured_attribute_REVIEW.csv"
MANIFEST_OUTPUT = OUTPUT / "post_correction_structured_attribute_review_manifest.json"
REPORT_OUTPUT = OUTPUT / "post_correction_structured_attribute_review_report.md"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        {
            "queue_id": row["queue_id"],
            "row_id": row["row_id"],
            "event_id": row["event_id"],
            "recommended_actions": row["recommended_actions"],
            "claimed_event_date": row["claimed_event_date"],
            "claimed_district": row["claimed_district"],
            "claimed_event_type": row["claimed_event_type"],
            "claimed_hazard_type": row["claimed_hazard_type"],
            "claimed_deaths": row["claimed_deaths"],
            "suggested_event_type": row["proposed_event_type"],
            "suggested_hazard_type": row["proposed_hazard_type"],
            "suggested_deaths": row["proposed_deaths"],
            "audit_notes": row["audit_notes"],
            "representative_title": row["representative_title"],
            "representative_url": row["representative_url"],
            "article_evidence": row["article_evidence"],
            "final_record_action": "",
            "final_event_type": "",
            "final_hazard_type": "",
            "final_deaths": "",
            "reviewed_by": "",
            "review_notes": "",
        }
        for row in rows
    ]


def main() -> None:
    remediation = json.loads(REMEDIATION_MANIFEST.read_text(encoding="utf-8"))
    if sha256(SOURCE) != remediation["output_sha256"][SOURCE.name]:
        raise ValueError("Structured-attribute source differs from remediation provenance.")

    identity = json.loads(IDENTITY_MANIFEST.read_text(encoding="utf-8"))
    if not identity["status"].startswith("post_correction_identity_plan_unapplied"):
        raise ValueError("Post-correction identity plan is not ready.")
    true_value = json.loads(TRUE_VALUE_MANIFEST.read_text(encoding="utf-8"))
    expected_status = "post_correction_true_value_plan_unapplied_attributes_pending"
    if true_value["status"] != expected_status:
        raise ValueError("Post-correction true-value plan is not ready.")
    if sha256(TRUE_VALUE_COMPLETED) != true_value["input_sha256"][TRUE_VALUE_COMPLETED.name]:
        raise ValueError("Completed true-value review differs from plan provenance.")

    source_rows = read_csv(SOURCE)
    source_ids = {row["event_id"] for row in source_rows}
    prior_ids = {row["old_event_id"] for row in read_csv(IDENTITY_REMOVE)}
    prior_ids |= {
        row["merge_existing_event_id"] for row in read_csv(IDENTITY_MERGES)
    }
    prior_ids |= {row["event_id"] for row in read_csv(TRUE_VALUE_COMPLETED)}
    overlap = source_ids & prior_ids
    if overlap:
        raise ValueError(
            f"Structured-attribute rows overlap earlier plans: {sorted(overlap)}"
        )

    review = build(source_rows)
    write_csv(REVIEW_OUTPUT, review)
    actions = Counter(
        action for row in review for action in row["recommended_actions"].split(";")
    )
    manifest = {
        "review_rows": len(review),
        "action_counts": dict(actions),
        "prior_gate_overlap_count": 0,
        "input_sha256": {
            SOURCE.name: sha256(SOURCE),
            REMEDIATION_MANIFEST.name: sha256(REMEDIATION_MANIFEST),
            IDENTITY_REMOVE.name: sha256(IDENTITY_REMOVE),
            IDENTITY_MERGES.name: sha256(IDENTITY_MERGES),
            IDENTITY_MANIFEST.name: sha256(IDENTITY_MANIFEST),
            TRUE_VALUE_COMPLETED.name: sha256(TRUE_VALUE_COMPLETED),
            TRUE_VALUE_MANIFEST.name: sha256(TRUE_VALUE_MANIFEST),
        },
        "output_sha256": {REVIEW_OUTPUT.name: sha256(REVIEW_OUTPUT)},
        "status": "blank_post_correction_structured_attribute_review",
    }
    MANIFEST_OUTPUT.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    lines = [
        "# Post-correction structured-attribute review",
        "",
        f"Rows: {len(review)}",
        "Prior-gate overlap: 0",
        "",
        "| Required action | Rows |",
        "|---|---:|",
    ]
    for action, count in actions.most_common():
        lines.append(f"| {action} | {count} |")
    lines.append("")
    REPORT_OUTPUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {len(review)} rows to {REVIEW_OUTPUT}")
    print(f"Wrote {MANIFEST_OUTPUT}")
    print(f"Wrote {REPORT_OUTPUT}")


if __name__ == "__main__":
    main()
