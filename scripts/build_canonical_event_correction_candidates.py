#!/usr/bin/env python3
"""Build an evidence-bearing correction queue from the adjudicated event audit."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "outputs"
ADJUDICATED = OUTPUT / "canonical_event_audit_ADJUDICATED.csv"
ADJUDICATION_MANIFEST = OUTPUT / "canonical_event_audit_adjudication_manifest.json"
READING_PACK = OUTPUT / "canonical_event_audit_reading_pack.csv"
WEIGHTS = OUTPUT / "canonical_event_audit_weights.csv"
CANDIDATES = OUTPUT / "canonical_event_correction_candidates.csv"
SUMMARY = OUTPUT / "canonical_event_correction_summary.json"
REPORT = OUTPUT / "canonical_event_correction_report.md"
BATCH_OUTPUTS = {
    "requires_article_mapping": OUTPUT / "canonical_event_correction_BATCH_ARTICLE_MAPPING.csv",
    "requires_true_value_review": OUTPUT / "canonical_event_correction_BATCH_TRUE_VALUE_REVIEW.csv",
    "structured_attribute_candidate": OUTPUT / "canonical_event_correction_BATCH_STRUCTURED_ATTRIBUTES.csv",
}

ACTION_HYPOTHESES = {
    "exclude_false_event": "scope_or_event_specificity",
    "review_event_existence": "scope_or_event_specificity",
    "split_or_exclude_aggregate": "event_granularity",
    "review_event_granularity": "event_granularity",
    "correct_district": "location_role_resolution",
    "review_district": "location_role_resolution",
    "correct_date": "event_date_resolution",
    "review_date": "event_date_resolution",
    "correct_municipality": "location_role_resolution",
    "review_municipality": "location_role_resolution",
    "correct_event_type": "event_type_classification",
    "review_event_type": "event_type_classification",
    "correct_hazard_type": "hazard_type_classification",
    "review_hazard_type": "hazard_type_classification",
    "correct_deaths": "casualty_extraction",
    "clear_deaths": "casualty_extraction",
    "review_deaths": "casualty_extraction",
    "recluster_articles": "deduplication",
    "review_duplicate_merge": "deduplication",
}
ARTICLE_MAPPING_ACTIONS = {
    "exclude_false_event", "split_or_exclude_aggregate",
    "review_event_granularity", "recluster_articles",
    "review_duplicate_merge",
}
TRUE_VALUE_REVIEW_ACTIONS = {
    "review_event_existence", "correct_district", "review_district",
    "correct_date", "review_date", "correct_municipality",
    "review_municipality", "review_event_type", "review_hazard_type",
    "review_deaths",
}
IDENTITY_ACTIONS = {
    "exclude_false_event", "review_event_existence",
    "split_or_exclude_aggregate", "review_event_granularity",
    "correct_district", "review_district", "correct_date", "review_date",
    "recluster_articles", "review_duplicate_merge",
}


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


def deaths_mismatch(claimed: str, true: str) -> bool:
    claimed = claimed.strip()
    true = true.strip().lower()
    if true in {"", "unclear"}:
        return False
    if true == "not_reported":
        return bool(claimed)
    return not claimed or int(claimed) != int(true)


def classify(row: dict[str, str]) -> tuple[list[str], dict[str, str]]:
    actions: list[str] = []
    proposed = {"event_type": "", "hazard_type": "", "deaths": ""}
    event = row["event_really_happened"].strip().lower()
    if event == "no":
        return ["exclude_false_event"], proposed
    if event == "unclear":
        return ["review_event_existence"], proposed

    binary_actions = (
        ("one_physical_event", "split_or_exclude_aggregate", "review_event_granularity"),
        ("district_correct", "correct_district", "review_district"),
        ("date_correct", "correct_date", "review_date"),
        ("municipality_correct", "correct_municipality", "review_municipality"),
    )
    for field, no_action, unclear_action in binary_actions:
        value = row[field].strip().lower()
        if value == "no":
            actions.append(no_action)
        elif value == "unclear":
            actions.append(unclear_action)

    event_type = row["event_type_true"].strip().lower()
    if event_type == "unclear":
        actions.append("review_event_type")
    elif event_type and event_type != row["claimed_event_type"].strip().lower():
        actions.append("correct_event_type")
        proposed["event_type"] = event_type

    hazard_type = row["hazard_type_true"].strip().lower()
    if hazard_type == "unclear":
        actions.append("review_hazard_type")
    elif hazard_type and hazard_type != row["claimed_hazard_type"].strip().lower():
        actions.append("correct_hazard_type")
        proposed["hazard_type"] = hazard_type

    deaths = row["deaths_true"].strip().lower()
    if deaths == "unclear":
        actions.append("review_deaths")
    elif deaths_mismatch(row["claimed_deaths"], deaths):
        actions.append("clear_deaths" if deaths == "not_reported" else "correct_deaths")
        proposed["deaths"] = "" if deaths == "not_reported" else deaths

    duplicate = row["duplicate_merge_correct"].strip().lower()
    if duplicate == "no":
        actions.append("recluster_articles")
    elif duplicate == "unclear":
        actions.append("review_duplicate_merge")
    return actions, proposed


def readiness(actions: list[str]) -> str:
    if any(action in ARTICLE_MAPPING_ACTIONS for action in actions):
        return "requires_article_mapping"
    if any(action in TRUE_VALUE_REVIEW_ACTIONS for action in actions):
        return "requires_true_value_review"
    return "structured_attribute_candidate"


def priority(actions: list[str]) -> str:
    if any(action in IDENTITY_ACTIONS for action in actions):
        return "P0_identity_or_linkage"
    if any(action.startswith("review_") for action in actions):
        return "P2_uncertain"
    return "P1_attribute"


def build_candidates(
    audit_rows: list[dict[str, str]],
    reading_by_id: dict[str, dict[str, str]],
    weights_by_id: dict[str, dict[str, str]],
) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    for row in audit_rows:
        actions, proposed = classify(row)
        if not actions:
            continue
        weight = weights_by_id[row["row_id"]]
        hypotheses = list(dict.fromkeys(ACTION_HYPOTHESES[action] for action in actions))
        candidates.append(
            {
                "candidate_id": f"CEC-{len(candidates) + 1:03d}",
                "row_id": row["row_id"],
                "event_id": row["event_id"],
                "priority_tier": priority(actions),
                "correction_readiness": readiness(actions),
                "recommended_actions": ";".join(actions),
                "systematic_issue_hypotheses": ";".join(hypotheses),
                "production_status": "candidate_unapplied",
                "sampling_stratum": weight["stratum"],
                "sampling_weight": weight["sampling_weight"],
                "claimed_event_date": row["claimed_event_date"],
                "claimed_district": row["claimed_district"],
                "claimed_municipality": row["claimed_municipality"],
                "claimed_event_type": row["claimed_event_type"],
                "claimed_hazard_type": row["claimed_hazard_type"],
                "claimed_deaths": row["claimed_deaths"],
                "proposed_event_date": "",
                "proposed_district": "",
                "proposed_municipality": "",
                "proposed_event_type": proposed["event_type"],
                "proposed_hazard_type": proposed["hazard_type"],
                "proposed_deaths": proposed["deaths"],
                "event_really_happened": row["event_really_happened"],
                "one_physical_event": row["one_physical_event"],
                "district_correct": row["district_correct"],
                "date_correct": row["date_correct"],
                "municipality_correct": row["municipality_correct"],
                "event_type_true": row["event_type_true"],
                "hazard_type_true": row["hazard_type_true"],
                "deaths_true": row["deaths_true"],
                "duplicate_merge_correct": row["duplicate_merge_correct"],
                "cluster_article_count": row["cluster_article_count"],
                "representative_title": row["representative_title"],
                "representative_url": row["representative_url"],
                "adjudicator": row["annotator"],
                "adjudication_notes": row["notes"],
                "article_evidence": reading_by_id[row["row_id"]]["article_evidence"],
                "reviewed_action": "",
                "reviewed_by": "",
                "review_notes": "",
            }
        )
    return candidates


def main() -> None:
    manifest = json.loads(ADJUDICATION_MANIFEST.read_text(encoding="utf-8"))
    expected_hash = manifest["outputs"][ADJUDICATED.name]
    if sha256(ADJUDICATED) != expected_hash:
        raise ValueError("Adjudicated audit differs from its provenance manifest.")
    audit_rows = read_csv(ADJUDICATED)
    reading_rows = read_csv(READING_PACK)
    weight_rows = read_csv(WEIGHTS)
    if [row["row_id"] for row in audit_rows] != [row["row_id"] for row in reading_rows]:
        raise ValueError("Audit and reading-pack row order differ.")
    if [row["row_id"] for row in audit_rows] != [row["row_id"] for row in weight_rows]:
        raise ValueError("Audit and sampling-weight row order differ.")

    candidates = build_candidates(
        audit_rows,
        {row["row_id"]: row for row in reading_rows},
        {row["row_id"]: row for row in weight_rows},
    )
    if not candidates:
        raise ValueError("No correction candidates were identified.")
    write_csv(CANDIDATES, candidates)
    for readiness_name, path in BATCH_OUTPUTS.items():
        batch = [row for row in candidates if row["correction_readiness"] == readiness_name]
        if not batch:
            raise ValueError(f"Correction batch {readiness_name} is unexpectedly empty.")
        write_csv(path, batch)

    action_counts = Counter()
    hypothesis_counts = Counter()
    for row in candidates:
        action_counts.update(row["recommended_actions"].split(";"))
        hypothesis_counts.update(row["systematic_issue_hypotheses"].split(";"))
    total_weight = sum(float(row["sampling_weight"]) for row in weight_rows)
    candidate_weight = sum(float(row["sampling_weight"]) for row in candidates)
    summary = {
        "audit_rows": len(audit_rows),
        "candidate_rows": len(candidates),
        "clean_rows": len(audit_rows) - len(candidates),
        "weighted_flagged_inventory_share": candidate_weight / total_weight,
        "priority_counts": dict(Counter(row["priority_tier"] for row in candidates)),
        "readiness_counts": dict(Counter(row["correction_readiness"] for row in candidates)),
        "action_counts": dict(action_counts.most_common()),
        "systematic_issue_counts": dict(hypothesis_counts.most_common()),
        "inputs": {
            ADJUDICATED.name: sha256(ADJUDICATED),
            ADJUDICATION_MANIFEST.name: sha256(ADJUDICATION_MANIFEST),
            READING_PACK.name: sha256(READING_PACK),
            WEIGHTS.name: sha256(WEIGHTS),
        },
        "outputs": {
            CANDIDATES.name: sha256(CANDIDATES),
            **{path.name: sha256(path) for path in BATCH_OUTPUTS.values()},
        },
        "interpretation": (
            "Candidates are unapplied review leads, not production corrections. "
            "Overlapping action counts must not be summed as unique events."
        ),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# Canonical event correction candidates",
        "",
        f"Audited rows: {len(audit_rows)}",
        f"Candidate rows: {len(candidates)}",
        f"Rows with no identified correction: {len(audit_rows) - len(candidates)}",
        f"Population-weighted flagged share: {candidate_weight / total_weight:.3f}",
        "",
        "## Priority",
        "",
        "| Tier | Candidate rows |",
        "|---|---:|",
    ]
    for name, count in sorted(summary["priority_counts"].items()):
        lines.append(f"| {name} | {count} |")
    lines.extend(["", "## Ordered work batches", "", "| Batch | Rows |", "|---|---:|"])
    for name, count in sorted(summary["readiness_counts"].items()):
        lines.append(f"| {name} | {count} |")
    lines.extend(["", "## Actions", "", "| Action | Rows |", "|---|---:|"])
    for name, count in action_counts.most_common():
        lines.append(f"| {name} | {count} |")
    lines.extend(
        [
            "",
            "Candidates remain unapplied. District, date, municipality, split, and",
            "re-clustering actions require source-level review before a correction layer",
            "or new inventory release is created.",
            "",
        ]
    )
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {len(candidates)} rows to {CANDIDATES}")
    for path in BATCH_OUTPUTS.values():
        print(f"Wrote {path}")
    print(f"Wrote {SUMMARY}")
    print(f"Wrote {REPORT}")


if __name__ == "__main__":
    main()
