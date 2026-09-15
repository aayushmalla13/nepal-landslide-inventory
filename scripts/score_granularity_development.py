#!/usr/bin/env python3
"""Score event-granularity classification on the DEVELOPMENT set.

Why this script exists
----------------------
Locked test v7 put article-level headline precision at 0.626, and 78% of its
false positives were articles the human annotator marked ``multi`` or
``roundup`` -- real Nepali landslide reports covering more than one failure.
The classifier is not confused about whether a landslide happened. It is
confused about how many. Granularity agreement on v7 was 0.486.

**v7 cannot be used to fix this.** It has been scored, so it is spent: using it
to design or evaluate a change would turn a held-out measurement into a training
signal. This script therefore works only on ``development_set_v1``, which exists
for exactly this purpose.

One caveat, stated up front
---------------------------
The development set was annotated by a language model (``annotator =
gpt-5.6-sol``), not by a person -- see ``docs/LOCKED_TEST_V7.md``. Fitting rules
hard against it risks learning that annotator's conventions rather than the
rubric's. So this script is used to *find mechanisms*, and any change it
motivates has to be defensible from the rubric on its own terms and then
confirmed on a human-labelled locked set v8.

The ablation
------------
``classify_event_granularity`` reads only the title and the first 250 characters
of the body. ``--reveal-window`` re-runs it with a larger lead so the cost of
that horizon can be measured rather than assumed.

Usage::

    PYTHONPATH=src python3 scripts/score_granularity_development.py
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# Article bodies exceed the default 128 KiB field limit.
csv.field_size_limit(50_000_000)

LABELS = ("single", "multi", "roundup", "not_applicable")


def read_corpus(path: Path) -> dict[str, dict[str, str]]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", newline="") as handle:
        return {row["url"]: row for row in csv.DictReader(handle)}


def read_labels(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def confusion(pairs: list[tuple[str, str]]) -> dict[str, object]:
    counts = Counter(pairs)
    labels = sorted({label for pair in pairs for label in pair})
    matrix = {
        truth: {pred: counts.get((truth, pred), 0) for pred in labels} for truth in labels
    }
    correct = sum(count for (truth, pred), count in counts.items() if truth == pred)
    per_class: dict[str, dict[str, object]] = {}
    for label in labels:
        true_positive = counts.get((label, label), 0)
        predicted = sum(counts.get((truth, label), 0) for truth in labels)
        actual = sum(counts.get((label, pred), 0) for pred in labels)
        precision = true_positive / predicted if predicted else None
        recall = true_positive / actual if actual else None
        per_class[label] = {
            "support": actual,
            "predicted": predicted,
            "precision": round(precision, 4) if precision is not None else None,
            "recall": round(recall, 4) if recall is not None else None,
        }
    return {
        "n": len(pairs),
        "accuracy": round(correct / len(pairs), 4) if pairs else None,
        "matrix": matrix,
        "per_class": per_class,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--labels", default="data/outputs/development_set_v1_labels_final.csv")
    parser.add_argument("--corpus", default="data/corpus/corpus_for_extraction.csv.gz")
    parser.add_argument("--output", default="data/outputs/granularity_development_score.json")
    parser.add_argument(
        "--predictions",
        default="",
        help=(
            "a *_predictions.csv carrying stratum inclusion weights. Required to "
            "report POPULATION rates for an enriched sample: the class-1 pack "
            "oversamples articles whose body carries a multi-event pattern, so "
            "its raw multi rate is several times the inventory's. Without the "
            "weights the sample's own rate would be reported as the inventory's."
        ),
    )
    parser.add_argument(
        "--reveal-window",
        type=int,
        default=0,
        help=(
            "if set, re-run with the lead window widened to this many characters, "
            "to measure how much the 250-character horizon costs"
        ),
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    from landslide_inventory.unify import event_typing

    labels = read_labels(ROOT / args.labels)
    corpus = read_corpus(ROOT / args.corpus)

    pairs: list[tuple[str, str]] = []
    missing_from_corpus = 0
    excluded_unclear = 0
    misses: list[dict[str, str]] = []
    for row in labels:
        truth = (row.get("event_granularity_true") or "").strip()
        if truth not in LABELS:
            excluded_unclear += 1
            continue
        article = corpus.get(row["url"])
        if article is None:
            missing_from_corpus += 1
            continue
        predicted = event_typing.classify_event_granularity(
            article.get("title"), article.get("text")
        )
        pairs.append((truth, predicted))
        if truth != predicted:
            misses.append(
                {
                    "row_id": row.get("row_id", ""),
                    "truth": truth,
                    "predicted": predicted,
                    "title": (article.get("title") or "")[:110],
                    "url": row["url"],
                }
            )

    result: dict[str, object] = {
        "set": "development_set_v1",
        "annotator_caveat": (
            "development_set_v1 was annotated by a language model, not a human. "
            "Use it to find mechanisms, not to fit thresholds; confirm on a "
            "human-labelled locked set."
        ),
        "labelled_rows": len(labels),
        "scored": len(pairs),
        "excluded_unclear_or_blank": excluded_unclear,
        "missing_from_corpus": missing_from_corpus,
        "baseline": confusion(pairs),
    }

    if args.reveal_window:
        original = event_typing.classify_event_granularity.__globals__.get("LEAD_CHARS")
        widened: list[tuple[str, str]] = []
        for row in labels:
            truth = (row.get("event_granularity_true") or "").strip()
            if truth not in LABELS:
                continue
            article = corpus.get(row["url"])
            if article is None:
                continue
            # Simulate the wider horizon by handing the classifier a body that
            # is already truncated to the wider window; the function's own
            # slice is then a no-op within it.
            text = (article.get("text") or "")[: args.reveal_window]
            widened.append(
                (truth, event_typing.classify_event_granularity(article.get("title"), text))
            )
        result["widened_lead"] = {
            "lead_chars": args.reveal_window,
            "note": (
                "Diagnostic only: the classifier still slices its own 250-char "
                "lead, so this measures how much signal a wider horizon could "
                "reach, not a proposed configuration."
            ),
            **confusion(widened),
        }
        _ = original

    if args.predictions:
        with (ROOT / args.predictions).open("r", encoding="utf-8-sig", newline="") as handle:
            weights = {r["row_id"]: r for r in csv.DictReader(handle)}
        by_row = {r.get("row_id", ""): r for r in labels}
        weighted: dict[str, float] = {}
        correct_weight = 0.0
        total_weight = 0.0
        per_stratum: dict[str, dict[str, float]] = {}
        for row_id, meta in weights.items():
            label = by_row.get(row_id)
            if label is None:
                continue
            truth = (label.get("event_granularity_true") or "").strip()
            if truth not in LABELS:
                continue
            article = corpus.get(label["url"])
            if article is None:
                continue
            predicted = event_typing.classify_event_granularity(
                article.get("title"), article.get("text")
            )
            weight = float(meta["inclusion_weight"])
            weighted[truth] = weighted.get(truth, 0.0) + weight
            total_weight += weight
            if truth == predicted:
                correct_weight += weight
            cell = per_stratum.setdefault(
                meta["stratum"], {"n": 0.0, "correct": 0.0, "multi": 0.0}
            )
            cell["n"] += 1
            cell["correct"] += 1 if truth == predicted else 0
            cell["multi"] += 1 if truth == "multi" else 0
        result["population_estimates"] = {
            "note": (
                "Weighted by stratum inclusion weight, so these describe the "
                "class-1 inventory rather than the enriched sample."
            ),
            "estimated_share_by_truth": {
                key: round(value / total_weight, 4) for key, value in sorted(weighted.items())
            },
            "weighted_accuracy": round(correct_weight / total_weight, 4) if total_weight else None,
            "per_stratum_unweighted": {
                key: {
                    "n": int(value["n"]),
                    "accuracy": round(value["correct"] / value["n"], 4) if value["n"] else None,
                    "multi_rate": round(value["multi"] / value["n"], 4) if value["n"] else None,
                }
                for key, value in sorted(per_stratum.items())
            },
        }

    result["misclassified_examples"] = misses[:25]

    output_path = ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    base = result["baseline"]
    print(f"scored {base['n']} rows   accuracy {base['accuracy']}")
    print("\nconfusion (rows = truth, columns = predicted):")
    labels_seen = sorted(base["matrix"])
    header = " " * 17 + "".join(f"{label:>16s}" for label in labels_seen)
    print(header)
    for truth in labels_seen:
        row_counts = "".join(f"{base['matrix'][truth][p]:16d}" for p in labels_seen)
        print(f"{truth:>17s}{row_counts}")
    print("\nper class:")
    for label, stats in base["per_class"].items():
        print(
            f"  {label:16s} support={stats['support']:4d} predicted={stats['predicted']:4d} "
            f"precision={stats['precision']} recall={stats['recall']}"
        )
    print(f"\nwrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
