#!/usr/bin/env python3
"""Freeze actionable findings from the post-correction validation audits."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from landslide_inventory.validation.correction_candidates import (
    ACTION_HYPOTHESES,
    certainty,
    classify,
    priority,
    readiness,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "outputs"
FRESH = OUTPUT / "post_correction_fresh_audit_COMPLETED.csv"
CHALLENGE = OUTPUT / "post_correction_challenge_COMPLETED.csv"
FRESH_READING = OUTPUT / "post_correction_fresh_audit_reading_pack.csv"
CHALLENGE_READING = OUTPUT / "post_correction_challenge_reading_pack.csv"
FRESH_WEIGHTS = OUTPUT / "post_correction_fresh_audit_weights.csv"
VALIDATION_MANIFEST = OUTPUT / "post_correction_validation_manifest.json"
VALIDATION_SCORE = OUTPUT / "post_correction_validation_score.json"

QUEUE = OUTPUT / "post_correction_remediation_queue.csv"
SUMMARY = OUTPUT / "post_correction_remediation_summary.json"
REPORT = OUTPUT / "post_correction_remediation_report.md"
MANIFEST = OUTPUT / "post_correction_remediation_manifest.json"
BATCH_OUTPUTS = {
    "requires_article_mapping": OUTPUT
    / "post_correction_remediation_BATCH_ARTICLE_MAPPING.csv",
    "requires_true_value_review": OUTPUT
    / "post_correction_remediation_BATCH_TRUE_VALUE_REVIEW.csv",
    "structured_attribute_candidate": OUTPUT
    / "post_correction_remediation_BATCH_STRUCTURED_ATTRIBUTES.csv",
}

LABEL_COLUMNS = (
    "event_really_happened",
    "one_physical_event",
    "district_correct",
    "date_correct",
    "municipality_correct",
    "event_type_true",
    "hazard_type_true",
    "deaths_true",
    "duplicate_merge_correct",
)
CLAIM_COLUMNS = (
    "claimed_event_date",
    "claimed_district",
    "claimed_municipality",
    "claimed_event_type",
    "claimed_hazard_type",
    "claimed_deaths",
    "claimed_missing",
    "claimed_injured",
    "cluster_article_count",
    "representative_title",
    "representative_url",
    "event_evidence",
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
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


def source_domain(url: str) -> str:
    domain = urlparse(url.strip()).netloc.lower()
    return domain.removeprefix("www.")


def verify_scored_inputs(score: dict[str, Any]) -> None:
    expected = score["input_sha256"]
    for path in (FRESH, CHALLENGE, VALIDATION_MANIFEST):
        if sha256(path) != expected[path.name]:
            raise ValueError(f"Scored validation input changed: {path.name}")


def verify_locked_artifacts(validation_manifest: dict[str, Any]) -> None:
    expected = validation_manifest["outputs"]
    for path in (FRESH_READING, CHALLENGE_READING, FRESH_WEIGHTS):
        if sha256(path) != expected[path.name]:
            raise ValueError(f"Locked validation artifact changed: {path.name}")


def validate_alignment(
    labels: list[dict[str, str]],
    readings: list[dict[str, str]],
    expected_role: str,
) -> None:
    if [row["row_id"] for row in labels] != [row["row_id"] for row in readings]:
        raise ValueError(f"{expected_role}: label and reading-pack row order differ")
    if any(row["sample_role"] != expected_role for row in labels):
        raise ValueError(f"{expected_role}: unexpected sample role")


def build_queue_rows(
    labels: list[dict[str, str]],
    reading_by_id: dict[str, dict[str, str]],
    weights_by_id: dict[str, dict[str, str]],
    *,
    first_number: int,
) -> list[dict[str, str]]:
    queue: list[dict[str, str]] = []
    for row in labels:
        actions, proposed = classify(row)
        if not actions:
            continue
        weight = weights_by_id.get(row["row_id"], {})
        hypotheses = list(dict.fromkeys(ACTION_HYPOTHESES[action] for action in actions))
        queue.append(
            {
                "queue_id": f"PCR-{first_number + len(queue):03d}",
                "row_id": row["row_id"],
                "sample_role": row["sample_role"],
                "correction_layer": row["correction_layer"],
                "event_id": row["event_id"],
                "priority_tier": priority(actions),
                "correction_readiness": readiness(actions),
                "finding_certainty": certainty(actions),
                "recommended_actions": ";".join(actions),
                "systematic_issue_hypotheses": ";".join(hypotheses),
                "source_domain": source_domain(row["representative_url"]),
                "production_status": "frozen_unapplied",
                "sampling_stratum": weight.get("stratum", ""),
                "sampling_weight": weight.get("sampling_weight", ""),
                **{column: row[column] for column in CLAIM_COLUMNS},
                "proposed_event_date": "",
                "proposed_district": "",
                "proposed_municipality": "",
                "proposed_event_type": proposed["event_type"],
                "proposed_hazard_type": proposed["hazard_type"],
                "proposed_deaths": proposed["deaths"],
                **{column: row[column] for column in LABEL_COLUMNS},
                "annotator": row["annotator"],
                "audit_notes": row["notes"],
                "article_evidence": reading_by_id[row["row_id"]]["article_evidence"],
                "reviewed_action": "",
                "reviewed_by": "",
                "review_notes": "",
            }
        )
    return queue


def counter(rows: list[dict[str, str]], field: str, *, split: bool = False) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        values = row[field].split(";") if split else [row[field]]
        counts.update(value for value in values if value)
    return dict(counts.most_common())


def build_summary(
    fresh_rows: list[dict[str, str]],
    challenge_rows: list[dict[str, str]],
    queue: list[dict[str, str]],
) -> dict[str, Any]:
    fresh_queue = [row for row in queue if row["sample_role"] == "fresh_probability"]
    challenge_queue = [
        row for row in queue if row["sample_role"] == "correction_challenge"
    ]
    all_fresh_weight = sum(float(row["sampling_weight"]) for row in fresh_queue)
    eligible_weight = sum(float(row["sampling_weight"]) for row in fresh_rows)
    return {
        "audit": "post_correction_remediation_queue_v1",
        "candidate_release": "nepal_landslide_inventory_v0.7.0_candidate_20260916",
        "queue_rows": len(queue),
        "fresh_audit_rows": len(fresh_rows),
        "fresh_flagged_rows": len(fresh_queue),
        "fresh_weighted_flagged_share": all_fresh_weight / eligible_weight,
        "challenge_rows": len(challenge_rows),
        "challenge_flagged_rows": len(challenge_queue),
        "sample_role_counts": counter(queue, "sample_role"),
        "priority_counts": counter(queue, "priority_tier"),
        "readiness_counts": counter(queue, "correction_readiness"),
        "certainty_counts": counter(queue, "finding_certainty"),
        "action_counts": counter(queue, "recommended_actions", split=True),
        "systematic_issue_counts": counter(
            queue, "systematic_issue_hypotheses", split=True
        ),
        "source_domain_counts": counter(queue, "source_domain"),
        "interpretation": (
            "Fresh and challenge findings are correction leads, not a new validation "
            "estimate. Sampling weights apply only to fresh_probability rows."
        ),
    }


def render_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Post-correction remediation queue",
        "",
        f"Queue rows: {summary['queue_rows']}",
        f"Fresh findings: {summary['fresh_flagged_rows']} of {summary['fresh_audit_rows']}",
        (
            "Fresh population-weighted flagged share: "
            f"{summary['fresh_weighted_flagged_share']:.3f}"
        ),
        (
            f"Challenge findings: {summary['challenge_flagged_rows']} of "
            f"{summary['challenge_rows']}"
        ),
        "",
        "The weighted flagged share is not the invalid-record rate. A row can be",
        "flagged for one attribute, and action counts overlap.",
    ]
    for title, field in (
        ("Ordered work batches", "readiness_counts"),
        ("Priority", "priority_counts"),
        ("Systematic issue families", "systematic_issue_counts"),
        ("Source domains", "source_domain_counts"),
        ("Actions", "action_counts"),
    ):
        lines.extend(["", f"## {title}", "", "| Category | Rows |", "|---|---:|"])
        for name, count in summary[field].items():
            lines.append(f"| {name} | {count} |")
    lines.extend(
        [
            "",
            "Fresh and challenge rows remain distinct in the queue. Challenge rows",
            "must not be weighted or pooled into population estimates. All findings",
            "remain unapplied until their assigned correction gate is completed.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    score = json.loads(VALIDATION_SCORE.read_text(encoding="utf-8"))
    validation_manifest = json.loads(VALIDATION_MANIFEST.read_text(encoding="utf-8"))
    verify_scored_inputs(score)
    verify_locked_artifacts(validation_manifest)

    fresh = read_csv(FRESH)
    challenge = read_csv(CHALLENGE)
    fresh_reading = read_csv(FRESH_READING)
    challenge_reading = read_csv(CHALLENGE_READING)
    weights = read_csv(FRESH_WEIGHTS)
    validate_alignment(fresh, fresh_reading, "fresh_probability")
    validate_alignment(challenge, challenge_reading, "correction_challenge")
    if [row["row_id"] for row in fresh] != [row["row_id"] for row in weights]:
        raise ValueError("Fresh labels and sampling weights differ")

    fresh_queue = build_queue_rows(
        fresh,
        {row["row_id"]: row for row in fresh_reading},
        {row["row_id"]: row for row in weights},
        first_number=1,
    )
    challenge_queue = build_queue_rows(
        challenge,
        {row["row_id"]: row for row in challenge_reading},
        {},
        first_number=len(fresh_queue) + 1,
    )
    queue = fresh_queue + challenge_queue
    if not queue:
        raise ValueError("No remediation findings were identified")
    if len({row["event_id"] for row in queue}) != len(queue):
        raise ValueError("An event appears more than once in the remediation queue")

    write_csv(QUEUE, queue)
    for readiness_name, path in BATCH_OUTPUTS.items():
        batch = [row for row in queue if row["correction_readiness"] == readiness_name]
        if not batch:
            raise ValueError(f"Remediation batch is unexpectedly empty: {readiness_name}")
        write_csv(path, batch)

    weights_by_id = {row["row_id"]: row for row in weights}
    weighted_fresh = [{**row, **weights_by_id[row["row_id"]]} for row in fresh]
    summary = build_summary(weighted_fresh, challenge, queue)
    summary["input_sha256"] = {
        path.name: sha256(path)
        for path in (
            FRESH,
            CHALLENGE,
            FRESH_READING,
            CHALLENGE_READING,
            FRESH_WEIGHTS,
            VALIDATION_MANIFEST,
            VALIDATION_SCORE,
        )
    }
    SUMMARY.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    REPORT.write_text(render_report(summary), encoding="utf-8")
    manifest = {
        "audit": summary["audit"],
        "candidate_release": summary["candidate_release"],
        "queue_status": "frozen_unapplied",
        "input_sha256": summary["input_sha256"],
        "output_sha256": {
            path.name: sha256(path)
            for path in (QUEUE, *BATCH_OUTPUTS.values(), SUMMARY, REPORT)
        },
    }
    MANIFEST.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"Wrote {len(queue)} findings to {QUEUE}")
    for path in BATCH_OUTPUTS.values():
        print(f"Wrote {path}")
    print(f"Wrote {SUMMARY}")
    print(f"Wrote {REPORT}")
    print(f"Wrote {MANIFEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
