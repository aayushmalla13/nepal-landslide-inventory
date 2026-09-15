#!/usr/bin/env python3
"""Draw a human-labelling pack that measures the recovered records' precision.

Why this is needed, and why the existing measurements are not enough
-------------------------------------------------------------------
`scripts/score_secondary_extraction.py` reports precision 1.00. That number is
close to meaningless as an estimate of correctness, for two reasons.

First, it is scored against the 47-article audit the extractor's rules were
written from, so agreement is nearly guaranteed.

Second and more seriously, **the audit covers only `multi` articles**, while the
corpus run applies the extractor to every kept class-1 article. Two rounds of
reading random recovered records by hand suggested roughly 4 in 10 are correct.
Each round found new error families -- corridor labels, travel origins,
enumerated district lists, an ignored Bikram Sambat year -- and each fix was
justified, but that process has no stopping rule and no measurable endpoint.
Only a labelled sample gives a number.

The design
----------
Stratified on the two axes that the error analysis showed actually separate good
records from bad:

* **firm vs soft date basis** -- an explicit date or a named weekday, against a
  relative cue ('last night', 'today');
* **cross-district vs same-district** -- a second district, against a second
  occasion in the district the article is already about, which is where
  re-dating the article's own landslide shows up.

Each stratum is sampled proportionally with the rest drawn at random, and every
row carries an inclusion weight so the scoring can report a population precision
rather than the sample's own.

What the annotator is *not* shown: the date basis, the confidence, or which
stratum a row came from. They are shown the claim, because the claim is what is
being judged, and the article text, because that is the evidence.

Usage::

    PYTHONPATH=src python3 scripts/draw_secondary_precision_pack.py
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import random
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

csv.field_size_limit(50_000_000)

SEED = 20260912
TARGET_ROWS = 120
CENSUS_THRESHOLD = 250
ROW_PREFIX = "sec"

FIRM_BASES = frozenset({"explicit_bs_date", "explicit_ad_date"})

# Sets already drawn and labelled. A row that has been judged once must not be
# judged again: re-drawing it would report agreement with an earlier reading as
# if it were fresh evidence.
SPENT_SETS: tuple[str, ...] = ()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_corpus(path: Path) -> dict[str, dict[str, str]]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", newline="") as handle:
        return {row["url"]: row for row in csv.DictReader(handle)}


def stratum_of(row: dict[str, str]) -> str:
    firmness = "firm" if row["date_basis"] in FIRM_BASES else "soft"
    axis = "same" if row["district"] == row["primary_district"] else "cross"
    return f"{axis}:{firmness}"


def row_rng(seed: int, key: str) -> random.Random:
    """Per-row deterministic RNG keyed by a hash, never by ``hash()``.

    Python salts ``hash()`` per process, so a draw built on it is not
    reproducible across runs.
    """

    digest = hashlib.sha256(f"{seed}:{key}".encode("utf-8")).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--recovered", default="data/outputs/secondary_failures.csv")
    parser.add_argument("--corpus", default="data/corpus/corpus_for_extraction.csv.gz")
    parser.add_argument("--prefix", default="data/outputs/secondary_precision")
    parser.add_argument("--rows", type=int, default=TARGET_ROWS)
    parser.add_argument(
        "--census-below",
        type=int,
        default=CENSUS_THRESHOLD,
        help=(
            "label every row when the population is no larger than this. A "
            "proportional draw covering most of the population buys sampling "
            "error for nothing."
        ),
    )
    parser.add_argument(
        "--novel-only",
        action="store_true",
        default=True,
        help=(
            "restrict to recovered district-days the inventory does not already "
            "hold. A record that collides with an existing case-day changes "
            "nothing about the analysis whether it is right or wrong."
        ),
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    recovered = read_csv(ROOT / args.recovered)
    if args.novel_only:
        recovered = [row for row in recovered if row["already_a_case_day"] == "False"]
    corpus = read_corpus(ROOT / args.corpus)

    spent: set[str] = set()
    for name in SPENT_SETS:
        path = ROOT / name
        if path.exists():
            for row in read_csv(path):
                spent.add(f"{row.get('url', '')}|{row.get('district', '')}|{row.get('date', '')}")

    by_stratum: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in recovered:
        key = f"{row['url']}|{row['district']}|{row['event_date_ad']}"
        if key in spent:
            continue
        by_stratum[stratum_of(row)].append(row)

    total = sum(len(rows) for rows in by_stratum.values())
    if total == 0:
        raise SystemExit("no recovered records to sample")

    # A proportional draw of 120 covered 79% of the population, which buys
    # sampling error for nothing. Below the census threshold every row is
    # labelled instead, every inclusion weight is 1.0, and the result is the
    # precision rather than an estimate of it.
    census = total <= args.census_below

    drawn: list[tuple[str, dict[str, str], float]] = []
    for stratum in sorted(by_stratum):
        population = by_stratum[stratum]
        if census:
            take = len(population)
        else:
            # Proportional allocation, with a floor so a small stratum is still
            # estimable at all.
            share = len(population) / total
            take = min(len(population), max(15, round(args.rows * share)))
        ordered = sorted(
            population, key=lambda row: (row["district"], row["event_date_ad"], row["url"])
        )
        rng = row_rng(SEED, stratum)
        rng.shuffle(ordered)
        chosen = ordered[:take]
        weight = len(population) / len(chosen)
        for row in chosen:
            drawn.append((stratum, row, weight))

    drawn.sort(key=lambda item: (item[1]["district"], item[1]["event_date_ad"], item[1]["url"]))

    label_path = ROOT / f"{args.prefix}_LABEL_HERE.csv"
    reading_path = ROOT / f"{args.prefix}_reading_pack.csv"
    weights_path = ROOT / f"{args.prefix}_strata.csv"

    with label_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "row_id",
                "claimed_district",
                "claimed_date",
                "article_district",
                "article_date",
                "url",
                "evidence_sentence",
                "failure_really_happened_there",
                "date_is_right",
                "annotator",
                "notes",
            ],
        )
        writer.writeheader()
        for index, (_, row, _) in enumerate(drawn, start=1):
            writer.writerow(
                {
                    "row_id": f"{ROW_PREFIX}-{index:04d}",
                    "claimed_district": row["district"],
                    "claimed_date": row["event_date_ad"],
                    "article_district": row["primary_district"],
                    "article_date": row["primary_date"],
                    "url": row["url"],
                    "evidence_sentence": row["evidence_sentence"],
                    "failure_really_happened_there": "",
                    "date_is_right": "",
                    "annotator": "",
                    "notes": "",
                }
            )

    with reading_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "row_id",
                "claimed_district",
                "claimed_date",
                "source",
                "route_lang",
                "url",
                "title",
                "evidence_sentence",
                "article_text",
            ],
        )
        writer.writeheader()
        for index, (_, row, _) in enumerate(drawn, start=1):
            article = corpus.get(row["url"], {})
            writer.writerow(
                {
                    "row_id": f"{ROW_PREFIX}-{index:04d}",
                    "claimed_district": row["district"],
                    "claimed_date": row["event_date_ad"],
                    "source": row["source"],
                    "route_lang": row["route_lang"],
                    "url": row["url"],
                    "title": article.get("title", ""),
                    "evidence_sentence": row["evidence_sentence"],
                    "article_text": article.get("text", ""),
                }
            )

    # Strata and weights live in a separate file the annotator is told not to
    # open: knowing a row came from the 'soft' stratum would steer the label.
    with weights_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "row_id",
                "url",
                "district",
                "event_date_ad",
                "stratum",
                "stratum_population",
                "inclusion_weight",
                "date_basis",
            ],
        )
        writer.writeheader()
        for index, (stratum, row, weight) in enumerate(drawn, start=1):
            writer.writerow(
                {
                    "row_id": f"{ROW_PREFIX}-{index:04d}",
                    "url": row["url"],
                    "district": row["district"],
                    "event_date_ad": row["event_date_ad"],
                    "stratum": stratum,
                    "stratum_population": len(by_stratum[stratum]),
                    "inclusion_weight": round(weight, 4),
                    "date_basis": row["date_basis"],
                }
            )

    mode = "census" if census else "stratified sample"
    print(f"{mode}: {len(drawn)} rows from {total} novel recovered district-days")
    for stratum in sorted(by_stratum):
        taken = sum(1 for item in drawn if item[0] == stratum)
        print(
            f"  {stratum:12s} population {len(by_stratum[stratum]):4d} -> sampled {taken:3d} "
            f"(weight {len(by_stratum[stratum]) / taken:.2f})"
        )
    print(f"\nwrote {label_path.name}, {reading_path.name}, {weights_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
