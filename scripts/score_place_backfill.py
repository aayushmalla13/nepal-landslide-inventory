#!/usr/bin/env python3
"""Measure the precision of proposed municipality and ward fills.

Why this gate exists
--------------------
``scripts/place_backfill_report.py`` proposes fills but deliberately applies
none: its own summary says "PROPOSED, NOT APPLIED. Precision must be measured on
the labelled review pack before these values enter a versioned inventory
release." This script is that measurement.

The fills are attractive precisely because they are cheap -- 1,714 ward fills
from text the pipeline already holds. That is also why they are dangerous. A
wrong municipality is not a missing value; it is a confident false location that
propagates into any sub-district analysis and into the published inventory, and
nothing downstream can tell it from a correct one.

How precision is estimated
--------------------------
The review pack is a stratified sample, so a raw accept rate over the 72 labelled
rows would not estimate population precision: municipality fills are a 94-row
stratum sampled at roughly one in six, ward fills a 1,714-row stratum sampled at
roughly one in twenty-nine. Precision is therefore estimated **within each
stratum** and combined with weights proportional to stratum size.

``unsure`` verdicts are excluded from the numerator and denominator and reported
separately. Counting them as accepts would flatter the estimate; counting them
as rejects would punish the proposal for the reviewer's uncertainty. Either
choice would be a decision disguised as arithmetic.

Intervals are Wilson score intervals, which behave sensibly at small n and near
1.0 where the normal approximation does not.

Usage::

    PYTHONPATH=src python3 scripts/score_place_backfill.py
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path

ACCEPT, REJECT, UNSURE = "accept", "reject", "unsure"


def wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval. Returns (low, high); (nan, nan) when total is 0."""

    if total == 0:
        return (math.nan, math.nan)
    phat = successes / total
    denominator = 1 + z * z / total
    centre = (phat + z * z / (2 * total)) / denominator
    margin = (
        z
        * math.sqrt(phat * (1 - phat) / total + z * z / (4 * total * total))
        / denominator
    )
    return (max(0.0, centre - margin), min(1.0, centre + margin))


def stratum_of(row: dict[str, str], field: str) -> str:
    """The sampling stratum a row belongs to for a given field."""

    language = (row.get("language") or "").strip() or "unknown"
    return f"{language}:{field}"


def score_field(
    labelled: list[dict[str, str]],
    population: list[dict[str, str]],
    *,
    proposal_column: str,
    verdict_column: str,
    field: str,
) -> dict[str, object]:
    """Stratified precision for one proposed field."""

    population_by_stratum: dict[str, int] = defaultdict(int)
    for row in population:
        if (row.get(proposal_column) or "").strip():
            population_by_stratum[stratum_of(row, field)] += 1

    counts: dict[str, dict[str, int]] = defaultdict(
        lambda: {ACCEPT: 0, REJECT: 0, UNSURE: 0}
    )
    for row in labelled:
        if not (row.get(proposal_column) or "").strip():
            continue
        verdict = (row.get(verdict_column) or "").strip().lower()
        if verdict in (ACCEPT, REJECT, UNSURE):
            counts[stratum_of(row, field)][verdict] += 1

    strata: dict[str, object] = {}
    weighted_numerator = weighted_denominator = 0.0
    total_accept = total_reject = total_unsure = 0
    for stratum, size in sorted(population_by_stratum.items()):
        tally = counts.get(stratum, {ACCEPT: 0, REJECT: 0, UNSURE: 0})
        decided = tally[ACCEPT] + tally[REJECT]
        total_accept += tally[ACCEPT]
        total_reject += tally[REJECT]
        total_unsure += tally[UNSURE]
        precision = tally[ACCEPT] / decided if decided else math.nan
        low, high = wilson_interval(tally[ACCEPT], decided)
        strata[stratum] = {
            "population": size,
            "labelled_decided": decided,
            "accept": tally[ACCEPT],
            "reject": tally[REJECT],
            "unsure": tally[UNSURE],
            "precision": None if math.isnan(precision) else round(precision, 4),
            "wilson_ci": None if math.isnan(low) else [round(low, 4), round(high, 4)],
        }
        if decided:
            weighted_numerator += size * precision
            weighted_denominator += size

    decided_total = total_accept + total_reject
    pooled_low, pooled_high = wilson_interval(total_accept, decided_total)
    return {
        "field": field,
        "population_with_a_proposal": sum(population_by_stratum.values()),
        "labelled_decided": decided_total,
        "accept": total_accept,
        "reject": total_reject,
        "unsure_excluded": total_unsure,
        "stratified_precision": (
            round(weighted_numerator / weighted_denominator, 4)
            if weighted_denominator
            else None
        ),
        "pooled_precision": round(total_accept / decided_total, 4) if decided_total else None,
        "pooled_wilson_ci": None
        if math.isnan(pooled_low)
        else [round(pooled_low, 4), round(pooled_high, 4)],
        "strata": strata,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--labelled", default="data/outputs/place_backfill_review_pack_COMPLETED.csv"
    )
    parser.add_argument("--candidates", default="data/outputs/place_backfill_candidates.csv")
    parser.add_argument("--output", default="data/outputs/place_backfill_precision.json")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    root = Path(__file__).resolve().parents[1]

    def read(path: Path) -> list[dict[str, str]]:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))

    labelled = read(root / args.labelled)
    population = read(root / args.candidates)

    result = {
        "labelled_rows": len(labelled),
        "candidate_rows": len(population),
        "reviewers": sorted({(r.get("reviewer") or "").strip() for r in labelled} - {""}),
        "unsure_policy": (
            "Excluded from both numerator and denominator, and reported. Counting "
            "them as accepts would flatter the estimate; as rejects would punish "
            "the proposal for the reviewer's uncertainty."
        ),
        "municipality": score_field(
            labelled,
            population,
            proposal_column="proposed_municipality",
            verdict_column="municipality_verdict",
            field="municipality",
        ),
        "ward": score_field(
            labelled,
            population,
            proposal_column="proposed_ward",
            verdict_column="ward_verdict",
            field="ward",
        ),
    }

    output_path = root / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    for field in ("municipality", "ward"):
        block = result[field]
        print(f"\n=== {field} ===")
        print(
            f"  population with a proposal: {block['population_with_a_proposal']:,}"
            f"   labelled decided: {block['labelled_decided']}"
            f"   (unsure excluded: {block['unsure_excluded']})"
        )
        print(
            f"  pooled precision {block['pooled_precision']}  "
            f"95% CI {block['pooled_wilson_ci']}   "
            f"stratified {block['stratified_precision']}"
        )
        for name, stratum in block["strata"].items():
            print(
                f"    {name:24s} pop={stratum['population']:5d} "
                f"decided={stratum['labelled_decided']:3d} "
                f"accept={stratum['accept']:3d} reject={stratum['reject']:3d} "
                f"precision={stratum['precision']}"
            )
    print(f"\nwrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
