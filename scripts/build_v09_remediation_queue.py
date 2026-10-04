#!/usr/bin/env python3
"""Freeze actionable v0.8 validation findings into the v0.9 remediation queue."""

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
COMPLETED = OUTPUT / "v08_fresh_validation_COMPLETED.csv"
READING = OUTPUT / "v08_fresh_validation_reading_pack.csv"
WEIGHTS = OUTPUT / "v08_fresh_validation_weights.csv"
VALIDATION_MANIFEST = OUTPUT / "v08_fresh_validation_manifest.json"
VALIDATION_SCORE = OUTPUT / "v08_fresh_validation_score.json"

QUEUE = OUTPUT / "v09_remediation_queue.csv"
SUMMARY = OUTPUT / "v09_remediation_summary.json"
REPORT = OUTPUT / "v09_remediation_report.md"
MANIFEST = OUTPUT / "v09_remediation_manifest.json"
BATCH_OUTPUTS = {
    "requires_article_mapping": OUTPUT / "v09_remediation_BATCH_ARTICLE_MAPPING.csv",
    "requires_true_value_review": OUTPUT / "v09_remediation_BATCH_TRUE_VALUE_REVIEW.csv",
    "structured_attribute_candidate": OUTPUT / "v09_remediation_BATCH_STRUCTURED_ATTRIBUTES.csv",
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
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        raise ValueError(f"Cannot write empty remediation artifact: {path.name}")
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
    return urlparse(url.strip()).netloc.lower().removeprefix("www.")


def verify_inputs(score: dict[str, Any], manifest: dict[str, Any]) -> None:
    scored = score["input_sha256"]
    for path in (COMPLETED, VALIDATION_MANIFEST):
        if sha256(path) != scored[path.name]:
            raise ValueError(f"Scored validation input changed: {path.name}")
    locked = manifest["outputs"]
    for path in (READING, WEIGHTS):
        if sha256(path) != locked[path.name]:
            raise ValueError(f"Locked validation artifact changed: {path.name}")
    if score["promotion_decision"]["passed"]:
        raise ValueError("A promoted candidate must not enter the remediation queue")


def validate_alignment(
    labels: list[dict[str, str]],
    readings: list[dict[str, str]],
    weights: list[dict[str, str]],
) -> None:
    label_ids = [row["row_id"] for row in labels]
    if label_ids != [row["row_id"] for row in readings]:
        raise ValueError("Labels and reading-pack row order differ")
    if label_ids != [row["row_id"] for row in weights]:
        raise ValueError("Labels and sampling-weight row order differ")
    if len(label_ids) != len(set(label_ids)):
        raise ValueError("Validation row IDs are not unique")


def build_queue_rows(
    labels: list[dict[str, str]],
    reading_by_id: dict[str, dict[str, str]],
    weights_by_id: dict[str, dict[str, str]],
) -> list[dict[str, str]]:
    queue: list[dict[str, str]] = []
    for row in labels:
        actions, proposed = classify(row)
        if not actions:
            continue
        weight = weights_by_id[row["row_id"]]
        hypotheses = list(dict.fromkeys(ACTION_HYPOTHESES[action] for action in actions))
        queue.append(
            {
                "queue_id": f"V9R-{len(queue) + 1:03d}",
                "row_id": row["row_id"],
                "sample_role": "v08_fresh_probability",
                "correction_layer": "v09_remediation",
                "event_id": row["event_id"],
                "priority_tier": priority(actions),
                "correction_readiness": readiness(actions),
                "finding_certainty": certainty(actions),
                "recommended_actions": ";".join(actions),
                "systematic_issue_hypotheses": ";".join(hypotheses),
                "source_domain": source_domain(row["representative_url"]),
                "production_status": "frozen_unapplied",
                "sampling_stratum": weight["stratum"],
                "sampling_weight": weight["sampling_weight"],
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
    all_weighted_rows: list[dict[str, str]], queue: list[dict[str, str]]
) -> dict[str, Any]:
    flagged_weight = sum(float(row["sampling_weight"]) for row in queue)
    eligible_weight = sum(float(row["sampling_weight"]) for row in all_weighted_rows)
    return {
        "audit": "v09_remediation_queue_v1",
        "source_candidate": "nepal_landslide_inventory_v0.8.0_candidate_20260923",
        "target_candidate": "nepal_landslide_inventory_v0.9.0_candidate",
        "queue_status": "frozen_unapplied",
        "validation_rows": len(all_weighted_rows),
        "queue_rows": len(queue),
        "population_weighted_flagged_share": flagged_weight / eligible_weight,
        "priority_counts": counter(queue, "priority_tier"),
        "readiness_counts": counter(queue, "correction_readiness"),
        "certainty_counts": counter(queue, "finding_certainty"),
        "action_counts": counter(queue, "recommended_actions", split=True),
        "systematic_issue_counts": counter(queue, "systematic_issue_hypotheses", split=True),
        "source_domain_counts": counter(queue, "source_domain"),
        "interpretation": (
            "Queue membership means at least one scored field requires correction or "
            "review. The weighted flagged share is not an invalid-event rate because "
            "valid events can have one incorrect attribute."
        ),
    }


def render_report(summary: dict[str, Any]) -> str:
    lines = [
        "# v0.9 remediation queue",
        "",
        "**Status:** frozen and unapplied",
        "",
        f"Source candidate: `{summary['source_candidate']}`",
        f"Actionable rows: {summary['queue_rows']} of {summary['validation_rows']}",
        (f"Population-weighted flagged share: {summary['population_weighted_flagged_share']:.3f}"),
        "",
        "The weighted share is not an invalid-event rate. A valid event can be",
        "queued for one attribute, and action counts overlap.",
    ]
    for title, field in (
        ("Ordered work batches", "readiness_counts"),
        ("Priority", "priority_counts"),
        ("Certainty", "certainty_counts"),
        ("Systematic issue families", "systematic_issue_counts"),
        ("Source domains", "source_domain_counts"),
        ("Recommended actions", "action_counts"),
    ):
        lines.extend(["", f"## {title}", "", "| Category | Rows |", "|---|---:|"])
        for name, count in summary[field].items():
            lines.append(f"| {name} | {count} |")
    lines.extend(
        [
            "",
            "Article mapping and identity decisions must be completed before true-value",
            "or structured-attribute corrections are applied. The v0.8 audit and this",
            "queue remain immutable evidence throughout remediation.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    score = json.loads(VALIDATION_SCORE.read_text(encoding="utf-8"))
    validation_manifest = json.loads(VALIDATION_MANIFEST.read_text(encoding="utf-8"))
    verify_inputs(score, validation_manifest)

    labels = read_csv(COMPLETED)
    readings = read_csv(READING)
    weights = read_csv(WEIGHTS)
    validate_alignment(labels, readings, weights)
    reading_by_id = {row["row_id"]: row for row in readings}
    weights_by_id = {row["row_id"]: row for row in weights}
    queue = build_queue_rows(labels, reading_by_id, weights_by_id)
    if not queue:
        raise ValueError("No remediation findings were identified")
    if len({row["event_id"] for row in queue}) != len(queue):
        raise ValueError("An event appears more than once in the remediation queue")

    write_csv(QUEUE, queue)
    for readiness_name, path in BATCH_OUTPUTS.items():
        write_csv(
            path,
            [row for row in queue if row["correction_readiness"] == readiness_name],
        )

    weighted_rows = [{**row, **weights_by_id[row["row_id"]]} for row in labels]
    summary = build_summary(weighted_rows, queue)
    input_paths = (
        COMPLETED,
        READING,
        WEIGHTS,
        VALIDATION_MANIFEST,
        VALIDATION_SCORE,
        Path(__file__).resolve(),
        ROOT / "src/landslide_inventory/validation/correction_candidates.py",
    )
    summary["input_sha256"] = {str(path.relative_to(ROOT)): sha256(path) for path in input_paths}
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    REPORT.write_text(render_report(summary), encoding="utf-8")
    manifest = {
        "audit": summary["audit"],
        "source_candidate": summary["source_candidate"],
        "target_candidate": summary["target_candidate"],
        "queue_status": summary["queue_status"],
        "input_sha256": summary["input_sha256"],
        "output_sha256": {
            path.name: sha256(path) for path in (QUEUE, *BATCH_OUTPUTS.values(), SUMMARY, REPORT)
        },
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {len(queue)} findings to {QUEUE}")
    for path in BATCH_OUTPUTS.values():
        print(f"Wrote {path}")
    print(f"Wrote {SUMMARY}")
    print(f"Wrote {REPORT}")
    print(f"Wrote {MANIFEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
