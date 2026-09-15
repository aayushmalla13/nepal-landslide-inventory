#!/usr/bin/env python3
"""Score strict-v2 secondary extraction against completed locked test v8 labels."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

PAIR_SEPARATOR = ";"
UNKNOWN = {"unclear"}
NONE = {"none"}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_pair(value: str) -> tuple[str, str]:
    from landslide_inventory.gazetteer import all_districts, normalize_district

    pieces = [piece.strip() for piece in value.split("|")]
    if len(pieces) != 2:
        raise ValueError(f"expected District|YYYY-MM-DD, got {value!r}")
    district = normalize_district(pieces[0], "en")
    if district not in set(all_districts()):
        raise ValueError(f"unknown district in pair {value!r}")
    try:
        event_date = date.fromisoformat(pieces[1]).isoformat()
    except ValueError as exc:
        raise ValueError(f"invalid ISO date in pair {value!r}") from exc
    return district, event_date


def parse_pairs(value: str) -> tuple[set[tuple[str, str]], bool]:
    cleaned = value.strip()
    lowered = cleaned.lower()
    if lowered in NONE:
        return set(), False
    if lowered in UNKNOWN:
        return set(), True
    if not cleaned:
        raise ValueError("blank pair label")
    return {parse_pair(piece.strip()) for piece in cleaned.split(PAIR_SEPARATOR)}, False


def wilson_interval(successes: float, total: float, z: float = 1.959963984540054) -> list[float] | None:
    if total <= 0:
        return None
    p = successes / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    radius = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total) / denominator
    return [max(0.0, centre - radius), min(1.0, centre + radius)]


def metric(
    numerator: float, denominator: float, *, include_wilson: bool = True
) -> dict[str, object]:
    return {
        "numerator": round(numerator, 6),
        "denominator": round(denominator, 6),
        "estimate": round(numerator / denominator, 6) if denominator else None,
        "wilson_95": (
            [round(value, 6) for value in wilson_interval(numerator, denominator)]
            if denominator and include_wilson
            else None
        ),
    }


def validate_alignment(
    labels: list[dict[str, str]], hidden: list[dict[str, str]], manifest: dict
) -> None:
    if len(labels) != manifest["sample_size"] or len(labels) != len(hidden):
        raise ValueError("locked files do not have the manifest row count")
    label_ids = [row["row_id"] for row in labels]
    hidden_ids = [row["row_id"] for row in hidden]
    if label_ids != hidden_ids:
        raise ValueError("completed labels and hidden predictions are misaligned")
    label_urls = [row["url"] for row in labels]
    if label_urls != [row["url"] for row in hidden]:
        raise ValueError("completed labels and hidden prediction URLs are misaligned")
    if len(label_urls) != len(set(label_urls)):
        raise ValueError("duplicate URL in completed labels")


def score_rows(labels: list[dict[str, str]], hidden: list[dict[str, str]]) -> tuple[dict, list[dict]]:
    counts = Counter()
    weighted = Counter()
    comparisons: list[dict] = []

    for label, key in zip(labels, hidden):
        primary_text = label["primary_district_date_true"].strip()
        if not primary_text:
            raise ValueError(f"{label['row_id']}: blank primary label")
        primary_unknown = primary_text.lower() in UNKNOWN
        primary_gold = None if primary_unknown else parse_pair(primary_text)

        additional_gold, all_additional_unknown = parse_pairs(
            label["additional_district_dates_true"]
        )
        unresolved = label["unresolved_additional_events_true"].strip().lower()
        if unresolved not in {"yes", "no"}:
            raise ValueError(f"{label['row_id']}: unresolved must be yes or no")
        if all_additional_unknown and unresolved != "yes":
            raise ValueError(f"{label['row_id']}: unclear additional events require unresolved=yes")

        predictions, prediction_unknown = parse_pairs(key["strict_v2_predictions"])
        if prediction_unknown:
            raise ValueError("machine predictions cannot be unclear")
        pipeline_primary = None
        if key["pipeline_primary_district"].strip() and key["pipeline_primary_date"].strip():
            pipeline_primary = parse_pair(
                f"{key['pipeline_primary_district']}|{key['pipeline_primary_date']}"
            )

        gold_all = set(additional_gold)
        if primary_gold:
            gold_all.add(primary_gold)
        target = gold_all - ({pipeline_primary} if pipeline_primary else set())
        recovered = predictions & target
        missed = target - predictions

        truth_complete = not primary_unknown and unresolved == "no"
        precision_tp = len(predictions & gold_all)
        unmatched_predictions = predictions - gold_all
        precision_fp = len(unmatched_predictions) if truth_complete else 0
        unscorable = len(unmatched_predictions) if not truth_complete else 0
        weight = float(key["inclusion_weight"])

        values = {
            "recovery_tp": len(recovered),
            "recovery_fn": len(missed),
            "precision_tp": precision_tp,
            "precision_fp": precision_fp,
            "unscorable_predictions": unscorable,
        }
        counts.update(values)
        weighted.update({name: value * weight for name, value in values.items()})
        counts["articles"] += 1
        weighted["articles"] += weight
        if truth_complete:
            counts["fully_resolved_articles"] += 1
            weighted["fully_resolved_articles"] += weight
            if precision_fp:
                counts["false_positive_articles"] += 1
                weighted["false_positive_articles"] += weight
        else:
            counts["partially_or_unresolved_articles"] += 1
            weighted["partially_or_unresolved_articles"] += weight
        if target:
            counts["articles_with_pipeline_missing_exact_pairs"] += 1
            weighted["articles_with_pipeline_missing_exact_pairs"] += weight
        counts["semantic_additional_exact_pairs"] += len(additional_gold)
        weighted["semantic_additional_exact_pairs"] += len(additional_gold) * weight

        def format_set(values: set[tuple[str, str]], empty: str = "none") -> str:
            return "; ".join(
                f"{district}|{event_date}" for district, event_date in sorted(values)
            ) or empty

        comparisons.append(
            {
                "row_id": label["row_id"],
                "url": label["url"],
                "stratum": key["stratum"],
                "inclusion_weight": weight,
                "gold_all_exact_pairs": format_set(gold_all, "unclear" if not gold_all else "none"),
                "pipeline_primary_pair": (
                    f"{pipeline_primary[0]}|{pipeline_primary[1]}" if pipeline_primary else "none"
                ),
                "pipeline_missing_exact_pairs": format_set(target),
                "truth_complete": "yes" if truth_complete else "no",
                "strict_v2_predictions": key["strict_v2_predictions"],
                "recovered_missing_pairs": len(recovered),
                "missed_exact_pairs": len(missed),
                "precision_true_positive_pairs": precision_tp,
                "precision_false_positive_pairs": precision_fp,
                "unscorable_predicted_pairs": unscorable,
            }
        )

    unweighted_specific = metric(
        counts["fully_resolved_articles"] - counts["false_positive_articles"],
        counts["fully_resolved_articles"],
    )
    report = {
        "unweighted": {
            "counts": dict(counts),
            "pipeline_missing_exact_pair_recall": metric(
                counts["recovery_tp"], counts["recovery_tp"] + counts["recovery_fn"]
            ),
            "adjudicable_pair_precision": metric(
                counts["precision_tp"], counts["precision_tp"] + counts["precision_fp"]
            ),
            "fully_resolved_article_no_false_prediction_rate": unweighted_specific,
        },
        "weighted": {
            "counts": {key: round(value, 6) for key, value in weighted.items()},
            "pipeline_missing_exact_pair_recall": metric(
                weighted["recovery_tp"],
                weighted["recovery_tp"] + weighted["recovery_fn"],
                include_wilson=False,
            ),
            "adjudicable_pair_precision": metric(
                weighted["precision_tp"],
                weighted["precision_tp"] + weighted["precision_fp"],
                include_wilson=False,
            ),
            "fully_resolved_article_no_false_prediction_rate": metric(
                weighted["fully_resolved_articles"] - weighted["false_positive_articles"],
                weighted["fully_resolved_articles"],
                include_wilson=False,
            ),
        },
    }
    return report, comparisons

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outputs", default="data/outputs")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    outputs = ROOT / args.outputs
    labels_path = outputs / "secondary_locked_v8_COMPLETED.csv"
    hidden_path = outputs / "secondary_locked_v8_DO_NOT_OPEN_predictions.csv"
    manifest_path = outputs / "secondary_locked_v8_manifest.json"
    report_path = outputs / "secondary_locked_v8_score.json"
    comparison_path = outputs / "secondary_locked_v8_comparison.csv"

    labels = read_csv(labels_path)
    hidden = read_csv(hidden_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    validate_alignment(labels, hidden, manifest)
    report, comparisons = score_rows(labels, hidden)
    annotators = Counter((row.get("annotator") or "").strip() for row in labels)
    model_annotators = {"chatgpt", "claude", "gemini", "copilot", "llm", "ai"}
    model_labelled = bool(annotators) and all(
        name.lower() in model_annotators for name in annotators
    )
    report.update(
        {
            "design_version": manifest["design_version"],
            "labels_sha256": sha256(labels_path),
            "hidden_predictions_sha256": sha256(hidden_path),
            "sample_size": len(labels),
            "annotator_counts": dict(annotators),
            "evaluation_status": (
                "MODEL_LABEL_DIAGNOSTIC" if model_labelled else "INDEPENDENT_LABEL_EVALUATION"
            ),
            "decision": "DO_NOT_INTEGRATE",
            "decision_reason": (
                "No strict-v2 prediction was adjudicable, and pipeline-missing exact-pair recall was zero. "
                "The evaluation cannot establish precision and does not support release integration. "
                + (
                    "All rows identify ChatGPT as annotator, so this is not independent human validation."
                    if model_labelled
                    else ""
                )
            ),
            "partial_label_policy": (
                "Exact labeled pairs contribute to recall. A prediction unmatched in an article "
                "with unresolved additional events is unscorable, not a false positive."
            ),
        }
    )
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if comparisons:
        with comparison_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(comparisons[0]))
            writer.writeheader()
            writer.writerows(comparisons)

    recall = report["unweighted"]["pipeline_missing_exact_pair_recall"]
    precision = report["unweighted"]["adjudicable_pair_precision"]
    print(f"pipeline-missing exact-pair recall: {recall['numerator']}/{recall['denominator']} = {recall['estimate']}")
    print(f"adjudicable precision: {precision['numerator']}/{precision['denominator']} = {precision['estimate']}")
    print(f"decision: {report['decision']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
