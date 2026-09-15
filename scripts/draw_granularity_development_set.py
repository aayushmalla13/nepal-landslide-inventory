#!/usr/bin/env python3
"""Draw a human-labelling pack for event granularity.

Why a new set is needed
-----------------------
Granularity is the weakest part of the extraction pipeline: agreement 0.486 on
locked test v7, and 78% of v7's false positives were articles the human
annotator marked ``multi`` or ``roundup``. It is the single biggest lever on
article-level precision.

It cannot be fixed with the data already in the project:

* **Locked test v7 is spent.** It has been scored. Designing against it would
  convert a held-out measurement into a training signal.
* **development_set_v1 is not a usable target for this field.** Its granularity
  labels were produced by a language model, and they are unreliable *for
  granularity specifically*. On the 51 articles matching the pipeline's
  documented road-obstruction rule -- a deliberate design decision, with the
  reasoning written in the code -- the model annotator split 28 ``single`` to 22
  ``multi``, near a coin flip. 31 of its 63 ``multi`` articles have a singular
  landslide subject in the title ("Landslide obstructs Karnali Highway"). Fitting
  rules to that would not improve the classifier; it would encode annotator noise
  and probably reverse a documented decision.

So this pack exists to get **human** granularity labels, on articles that have
never received prior human truth labels, so a fix can be designed honestly and
then evaluated on a fresh locked set v8. Earlier model-labelled diagnostics are
not treated as human truth; their answers remain hidden from the annotator.

What is drawn
-------------
Stratified by route language and by the granularity the pipeline currently
predicts, so each cell of the confusion matrix gets support -- including the
cells where the classifier is confident and wrong. Rows already labelled in any
previous set are excluded, and the exclusion is verified rather than assumed.

Only three fields are asked for. Granularity is the question; the other two are
what make a granularity judgement well defined.

Usage::

    PYTHONPATH=src python3 scripts/draw_granularity_development_set.py
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

csv.field_size_limit(50_000_000)

SEED = 20260904
PER_STRATUM = 20

LABEL_COLUMNS = [
    "event_granularity_true",
    "is_landslide_event_true",
    "in_nepal_true",
    "annotator",
    "notes",
]

SPENT_SETS = (
    "data/outputs/locked_test_set_v7_labels_final.csv",
    "data/outputs/development_set_v1_labels_final.csv",
    "data/outputs/granularity_development_COMPLETED.csv",
)

# v6 was labelled entirely by gpt-5.6-sol. It is a historical diagnostic, not
# an independent human reference set, and cannot disqualify an article from a
# human development sample. Its answers must never be included in label packs.
MODEL_REFERENCE_SETS = (
    "data/outputs/locked_test_set_v6_labels_final.csv",
)


def read_corpus(path: Path) -> list[dict[str, str]]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def spent_urls(paths: list[Path]) -> set[str]:
    """Every URL that has been labelled before, in any set."""

    seen: set[str] = set()
    for path in paths:
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                url = (row.get("url") or "").strip()
                if url:
                    seen.add(url)
    return seen


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--corpus", default="data/corpus/corpus_for_extraction.csv.gz")
    parser.add_argument("--outputs", default="data/outputs")
    parser.add_argument("--per-stratum", type=int, default=PER_STRATUM)
    parser.add_argument(
        "--classes",
        default="1,2,3",
        help=(
            "pipeline classes to draw from. Class 1 alone is useless here: the "
            "class-1 gate requires headline eligibility, which requires "
            "granularity=single, so every class-1 article is predicted single by "
            "construction. The multi and roundup articles live in classes 2 and 3."
        ),
    )
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument(
        "--prefix",
        default="granularity_development",
        help="output filename prefix, so a second pack does not overwrite the first",
    )
    parser.add_argument(
        "--row-prefix",
        default="gran",
        help=(
            "row_id prefix. It MUST differ between packs. Both packs originally "
            "used 'gran-0001...', which made a completed file from one pack "
            "indistinguishable from the other by row id alone -- and a copy of "
            "the first pack was duly renamed to the second's filename. Only a "
            "row count and a URL comparison caught it."
        ),
    )
    parser.add_argument(
        "--stratify",
        choices=("predicted", "body_signal"),
        default="predicted",
        help=(
            "'predicted': by the granularity the pipeline predicts -- the right "
            "frame for measuring the classifier overall. 'body_signal': by whether "
            "a multi-event pattern appears anywhere in the body -- the right frame "
            "for a CLASS-1 pack, where every article is predicted single by "
            "construction, so the prediction carries no information and a flat "
            "sample would contain too few true multi articles to learn from."
        ),
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    from landslide_inventory.unify.event_typing import classify_event_granularity

    corpus = read_corpus(ROOT / args.corpus)
    wanted = {value.strip() for value in args.classes.split(",") if value.strip()}
    events = [row for row in corpus if row.get("class") in wanted]
    spent = spent_urls([ROOT / path for path in SPENT_SETS])

    from landslide_inventory.unify.event_typing import (
        MULTI_ADMIN_PATTERN,
        MULTI_EVENT_PATTERN,
    )

    def body_carries_a_multi_signal(row: dict[str, str]) -> bool:
        """Does a multi-event pattern appear ANYWHERE in the body?

        Not a prediction -- the classifier deliberately reads only the title and
        a 250-character lead, and widening that window was measured and rejected
        (it gains 9 multi and wrongly flips 15 single). This is used purely as a
        sampling stratifier: it correlates with true plurality well enough to
        enrich the rare class, and the stratum weights undo the enrichment when
        population rates are estimated.
        """

        body = row.get("text") or ""
        return bool(MULTI_EVENT_PATTERN.search(body) or MULTI_ADMIN_PATTERN.search(body))

    strata: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in events:
        if row["url"] in spent:
            continue
        language = "np" if row.get("route_lang") == "np" else "en"
        if args.stratify == "predicted":
            cell = classify_event_granularity(row.get("title"), row.get("text"))
        else:
            cell = "signal" if body_carries_a_multi_signal(row) else "plain"
        strata[(language, cell)].append(row)

    stratum_sizes = {f"{k[0]}:{k[1]}": len(v) for k, v in strata.items()}

    rng = random.Random(args.seed)
    drawn: list[dict[str, str]] = []
    for key in sorted(strata):
        pool = sorted(strata[key], key=lambda item: item["url"])
        rng.shuffle(pool)
        drawn.extend(pool[: args.per_stratum])
    drawn.sort(key=lambda row: row["url"])

    assert not ({row["url"] for row in drawn} & spent), "a spent article was drawn"

    outputs = ROOT / args.outputs
    outputs.mkdir(parents=True, exist_ok=True)

    label_path = outputs / f"{args.prefix}_LABEL_HERE.csv"
    reading_path = outputs / f"{args.prefix}_reading_pack.csv"
    manifest_path = outputs / f"{args.prefix}_manifest.json"

    # The pipeline's own answer is deliberately NOT shown.
    #
    # The point of this set is to adjudicate the cases where the classifier is
    # confident and wrong, and showing its answer on those very rows invites the
    # annotator to ratify it. Stratifying by the prediction already guarantees
    # those rows are in the sample; the annotator does not need to know which
    # ones they are. It is recorded in the manifest instead, so the confusion
    # matrix can still be built after labelling.
    label_columns = ["row_id", "url", "source", "route_lang", "title"]
    with label_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=label_columns + LABEL_COLUMNS)
        writer.writeheader()
        for index, row in enumerate(drawn, start=1):
            language = "np" if row.get("route_lang") == "np" else "en"
            writer.writerow(
                {
                    "row_id": f"{args.row_prefix}-{index:04d}",
                    "url": row["url"],
                    "source": row.get("source", ""),
                    "route_lang": language,
                    "title": row.get("title", ""),
                    **{column: "" for column in LABEL_COLUMNS},
                }
            )

    with reading_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["row_id", "route_lang", "source", "url", "title", "article_text"]
        )
        writer.writeheader()
        for index, row in enumerate(drawn, start=1):
            writer.writerow(
                {
                    "row_id": f"{args.row_prefix}-{index:04d}",
                    "route_lang": "np" if row.get("route_lang") == "np" else "en",
                    "source": row.get("source", ""),
                    "url": row["url"],
                    "title": row.get("title", ""),
                    "article_text": row.get("text", ""),
                }
            )

    # Predictions AND inclusion weights live here, away from the annotator.
    #
    # The weight is the stratum's population divided by how many of it were
    # drawn. Without it an enriched sample would report the multi rate of the
    # sample rather than of the inventory, overstating it several-fold.
    def stratum_of(row: dict[str, str]) -> str:
        language = "np" if row.get("route_lang") == "np" else "en"
        if args.stratify == "predicted":
            return f"{language}:{classify_event_granularity(row.get('title'), row.get('text'))}"
        return f"{language}:{'signal' if body_carries_a_multi_signal(row) else 'plain'}"

    drawn_per_cell = Counter(stratum_of(row) for row in drawn)
    predictions_path = outputs / f"{args.prefix}_predictions.csv"
    with predictions_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "row_id", "url", "predicted_granularity", "stratum",
                "stratum_population", "inclusion_weight", "pipeline_class",
            ],
        )
        writer.writeheader()
        for index, row in enumerate(drawn, start=1):
            cell = stratum_of(row)
            population = stratum_sizes[cell]
            writer.writerow(
                {
                    "row_id": f"{args.row_prefix}-{index:04d}",
                    "url": row["url"],
                    "predicted_granularity": classify_event_granularity(
                        row.get("title"), row.get("text")
                    ),
                    "stratum": cell,
                    "stratum_population": population,
                    "inclusion_weight": round(population / drawn_per_cell[cell], 4),
                    "pipeline_class": row.get("class", ""),
                }
            )

    digest = hashlib.sha256(label_path.read_bytes()).hexdigest()
    manifest = {
        "purpose": (
            "Human granularity labels for designing a fix. This is a DEVELOPMENT "
            "set: it may be inspected while designing. The fix must then be "
            "evaluated on a newly drawn, human-labelled locked set v8."
        ),
        "seed": args.seed,
        "row_id_prefix": args.row_prefix,
        "classes_drawn_from": sorted(wanted),
        "why_not_class_1_only": (
            "The class-1 gate requires headline eligibility, which requires "
            "granularity=single, so all 3,397 class-1 articles are predicted "
            "single by construction and carry no multi or roundup contrast."
        ),
        "per_stratum": args.per_stratum,
        "rows": len(drawn),
        "stratify_by": args.stratify,
        "strata": {f"{k[0]}:{k[1]}": len(v) for k, v in sorted(strata.items())},
        "drawn_per_stratum": dict(drawn_per_cell),
        "inclusion_weights": {
            cell: round(stratum_sizes[cell] / count, 4)
            for cell, count in drawn_per_cell.items()
        },
        "excluded_previously_labelled_urls": len(spent),
        "excluded_sets": list(SPENT_SETS),
        "model_reference_sets_not_used_as_truth": list(MODEL_REFERENCE_SETS),
        "label_file_sha256": digest,
        "why_development_set_v1_is_not_used": (
            "Its granularity labels are model-produced and unreliable for this "
            "field: on the 51 articles matching the pipeline's documented "
            "road-obstruction rule it split 28 single / 22 multi, and 31 of its "
            "63 multi articles have a singular landslide subject in the title."
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"drew {len(drawn)} rows across {len(strata)} strata")
    for key, count in sorted(manifest["drawn_per_stratum"].items()):
        print(f"  {key:20s} {count}")
    print(f"excluded {len(spent)} previously labelled URLs")
    print(
        f"\nwrote {label_path.name}, {reading_path.name}, "
        f"{predictions_path.name}, {manifest_path.name}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
