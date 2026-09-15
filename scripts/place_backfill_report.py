#!/usr/bin/env python3
"""Propose municipality and ward fills for event articles, with evidence.

This does not modify the inventory. It writes three artefacts:

``place_backfill_candidates.csv``
    Every proposed fill, with the matched text snippet, so each one can be
    checked without opening the source article.

``place_backfill_review_pack.csv``
    A deterministic stratified sample for human verification. Precision has to
    be measured on labelled rows before these fills enter a release; this is the
    file to label.

``place_backfill_summary.json``
    Counts by field, language and district agreement.

Input is a corpus export produced from the project database with::

    SELECT ae.url, ae.source, ae.route_lang, ae.class, ae.event_date_ad,
           ae.district, ae.municipality, ae.ward, ra.text
    FROM article_events ae
    LEFT JOIN raw_articles ra ON ra.url = ae.url

Usage::

    python3 scripts/place_backfill_report.py --corpus data/corpus/corpus_for_extraction.csv.gz
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from landslide_inventory.unify.place_backfill import backfill_place  # noqa: E402

REVIEW_SAMPLE_PER_STRATUM = 30
REVIEW_SEED = 20260814


def read_corpus(path: Path) -> list[dict[str, str]]:
    csv.field_size_limit(sys.maxsize)
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", newline="") as handle:  # type: ignore[operator]
        return list(csv.DictReader(handle))


def blank(value: str | None) -> bool:
    return str(value or "").strip() in ("", "None", "unknown")



def _spent_keys(paths: "list[Path]") -> set[tuple[str, str]]:
    """(url, event_date_ad) of every row already labelled in a previous round."""

    spent: set[tuple[str, str]] = set()
    for path in paths:
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                spent.add((row.get("url", ""), row.get("event_date_ad", "")))
    return spent


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", default="data/corpus/corpus_for_extraction.csv.gz")
    parser.add_argument("--outputs", default="data/outputs")
    parser.add_argument(
        "--spent",
        action="append",
        default=None,
        help=(
            "a previously labelled review pack whose rows must not be drawn "
            "again (repeatable). Defaults to the completed first round."
        ),
    )
    args = parser.parse_args()
    spent_paths = [
        ROOT / path
        for path in (
            args.spent
            if args.spent is not None
            else ["data/outputs/place_backfill_review_pack_COMPLETED.csv"]
        )
    ]

    rows = read_corpus(ROOT / args.corpus)
    events = [row for row in rows if row.get("class") == "1"]
    outputs = ROOT / args.outputs
    outputs.mkdir(parents=True, exist_ok=True)

    candidates: list[dict[str, object]] = []
    stats: Counter[str] = Counter()
    by_language: dict[str, Counter[str]] = defaultdict(Counter)

    for row in events:
        stats["articles"] += 1
        language = "np" if row.get("route_lang") == "np" else "en"
        result = backfill_place(
            row.get("text") or "",
            language=language,
            district=row.get("district") or "",
            municipality=row.get("municipality"),
            ward=row.get("ward"),
        )
        if result.is_empty:
            continue
        if result.municipality is not None:
            stats["municipality_filled"] += 1
            by_language[language]["municipality"] += 1
            if result.municipality_ambiguous:
                stats["municipality_ambiguous_name"] += 1
        if result.ward is not None:
            stats["ward_filled"] += 1
            by_language[language]["ward"] += 1
        candidates.append(
            {
                "url": row.get("url", ""),
                "source": row.get("source", ""),
                "language": language,
                "event_date_ad": row.get("event_date_ad", ""),
                "district": row.get("district", ""),
                "existing_municipality": row.get("municipality", ""),
                "proposed_municipality": result.municipality or "",
                "municipality_reason": result.municipality_reason,
                "municipality_name_is_ambiguous": result.municipality_ambiguous,
                "municipality_evidence": result.municipality_evidence,
                "existing_ward": row.get("ward", ""),
                "proposed_ward": result.ward if result.ward is not None else "",
                "ward_reason": result.ward_reason,
                "ward_evidence": result.ward_evidence,
                "municipality_verdict": "",
                "ward_verdict": "",
                "reviewer": "",
                "note": "",
            }
        )

    columns = list(candidates[0]) if candidates else ["url"]
    candidates_path = outputs / "place_backfill_candidates.csv"
    with candidates_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(candidates)

    # Stratify the review sample so precision can be estimated separately for the
    # cases most likely to differ: language, and whether a ward was attached.
    strata: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for row in candidates:
        key = (str(row["language"]), "ward" if row["proposed_ward"] != "" else "municipality_only")
        strata[key].append(row)
    # A row that has already been labelled is SPENT and must not be drawn again.
    #
    # The first review pack was labelled, then used to diagnose and motivate a
    # code change (the person-attribution guard). Measuring the change on the
    # same rows that motivated it is optimistic by construction, so a
    # confirmation round needs rows the change has never been evaluated on.
    # Re-running with the same seed returned 15 of the 72 spent rows; excluding
    # them explicitly is the only way the next estimate is honest.
    spent = _spent_keys(spent_paths)
    if spent:
        print(f"excluding {len(spent)} already-labelled rows from the review sample")
    rng = random.Random(REVIEW_SEED)
    review: list[dict[str, object]] = []
    for key in sorted(strata):
        pool = [
            item
            for item in sorted(strata[key], key=lambda item: str(item["url"]))
            if (str(item["url"]), str(item["event_date_ad"])) not in spent
        ]
        rng.shuffle(pool)
        review.extend(pool[:REVIEW_SAMPLE_PER_STRATUM])
    review_path = outputs / "place_backfill_review_pack.csv"
    with review_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(review)

    summary = {
        "articles_considered": stats["articles"],
        "articles_with_a_proposed_fill": len(candidates),
        "municipality_fills": stats["municipality_filled"],
        "municipality_fills_with_a_shared_name": stats["municipality_ambiguous_name"],
        "ward_fills": stats["ward_filled"],
        "by_language": {lang: dict(counter) for lang, counter in sorted(by_language.items())},
        "review_pack_rows": len(review),
        "review_strata": {f"{a}:{b}": len(v) for (a, b), v in sorted(strata.items())},
        "rules": [
            "additive only: an existing value is never overwritten",
            "a municipality is accepted only if the gazetteer places it in the article district",
            "a ward is accepted only when adjacent to an accepted municipality mention",
            "no value is imputed when the text does not state one",
        ],
        "status": (
            "PROPOSED, NOT APPLIED. Precision must be measured on the labelled "
            "review pack before these values enter a versioned inventory release."
        ),
    }
    summary_path = outputs / "place_backfill_summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(f"articles considered            : {summary['articles_considered']}")
    print(f"articles with a proposed fill  : {summary['articles_with_a_proposed_fill']}")
    print(f"  municipality fills           : {summary['municipality_fills']}")
    print(f"  ward fills                   : {summary['ward_fills']}")
    print(f"review pack rows               : {summary['review_pack_rows']}")
    for path in (candidates_path, review_path, summary_path):
        print(f"wrote {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
