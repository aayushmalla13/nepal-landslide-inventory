#!/usr/bin/env python3
"""Estimate what multi-event district-day extraction would actually recover.

Why this script exists
----------------------
The granularity work established that 29.3% of kept class-1 articles report
more than one landslide failure, and concluded that this under-counts events.
The natural remedy is to emit several ``(district, date)`` records from one
article instead of one. Before building that, the question is how much it would
actually add -- because the analysis unit is the **district-day**, not the
failure. Several failures on one slope system, in one district, on one night
collapse to the same district-day and recover nothing.

``data/outputs/multievent_yield_audit.csv`` records a full read of all 47
human-labelled ``multi`` articles in the class-1 development pack, scoring for
each the number of *defensible additional district-days* it would support,
split into ``strong`` (an explicitly located failure in a named second
district, or an explicitly dated second occasion) and ``weak`` (contestable:
border attributions, unlocated assertions, relative dates that cannot be
anchored).

It also records the **trap taxonomy**: the systematic reasons a district name
appears in one of these articles without a failure having happened there. Those
traps are what a naive "emit every district mentioned" rule would convert into
false case-days.

This script turns that audit into two numbers:

1. the *sample* yield -- extra district-days per 47 multi articles, and
2. the *inventory* yield -- the same quantity reweighted by the class-1 pack's
   stratum inclusion weights, because the pack deliberately oversamples
   articles whose body carries a multi-event phrase.

It also computes the naive-extractor precision ceiling by comparing the
defensible count against the number of distinct districts the existing place
candidates already surface for the same articles.

Nothing here modifies the inventory. It is a go/no-go measurement.

Usage::

    PYTHONPATH=src python3 scripts/score_multievent_yield.py
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

csv.field_size_limit(50_000_000)

# A defensible-recovery count below this, as a share of the analysis case-days,
# means the project cannot repay a new inventory release plus a fresh locked
# test set. Stated before the numbers were computed.
MATERIALITY_THRESHOLD = 0.05

# The audit found that 4 of the 17 defensible recovered pairs already exist as
# case-days in the v0.6.0 inventory, contributed by other articles. Recovered
# pairs that collide add no new district-day, so the gross yield overstates the
# net gain by this factor. Three of the four are Chitwan on the
# Narayangadh-Muglin corridor, which is reported so often that a second article
# rarely adds a district-day the inventory lacks.
COLLISION_RATE = 4 / 17

BOOTSTRAP_DRAWS = 20000
BOOTSTRAP_SEED = 20260912


def stratified_bootstrap(
    per_article: dict[str, list[int]],
    stratum_weight: dict[str, float],
    draws: int,
    seed: int,
) -> tuple[float, float]:
    """Return a percentile interval for the weighted extra-district-day total.

    The sampled articles are resampled with replacement *within* each stratum,
    which is how they were drawn. This propagates the dominant uncertainty: a
    stratum represented by a handful of articles but standing for hundreds of
    inventory articles carries enormous sampling error, and a point estimate
    hides it entirely.
    """

    rng = random.Random(seed)
    totals: list[float] = []
    strata = sorted(per_article)
    for _ in range(draws):
        total = 0.0
        for stratum in strata:
            values = per_article[stratum]
            weight = stratum_weight[stratum]
            total += weight * sum(rng.choice(values) for _ in values)
        totals.append(total)
    totals.sort()
    lower = totals[int(0.025 * (draws - 1))]
    upper = totals[int(0.975 * (draws - 1))]
    return lower, upper


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def resolve_candidate_districts(article: dict[str, str]) -> list[str]:
    """Return the distinct districts the existing place candidates resolve to."""

    from landslide_inventory.gazetteer import normalize_district
    from landslide_inventory.gazetteer_municipality import municipality_to_district

    def resolve(name: str) -> str | None:
        for lang in ("en", "np"):
            district = normalize_district(name, lang)
            if district:
                return district
        return municipality_to_district(name)

    districts: list[str] = []
    assigned = (article.get("district") or "").strip()
    if assigned:
        districts.append(assigned)
    for name in json.loads(article.get("place_candidates_json") or "[]"):
        district = resolve(name)
        if district and district not in districts:
            districts.append(district)
    return districts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--audit", default="data/outputs/multievent_yield_audit.csv")
    parser.add_argument("--labels", default="data/outputs/granularity_class1_COMPLETED.csv")
    parser.add_argument("--predictions", default="data/outputs/granularity_class1_predictions.csv")
    parser.add_argument("--articles", default="data/outputs/article_events.csv")
    parser.add_argument("--cases", default="data/outputs/event_antecedent_rainfall.csv")
    parser.add_argument("--output", default="data/outputs/multievent_yield.json")
    return parser


def main() -> int:
    args = build_parser().parse_args()

    audit = {row["row_id"]: row for row in read_csv(ROOT / args.audit)}
    labels = {row["row_id"]: row for row in read_csv(ROOT / args.labels)}
    predictions = {row["row_id"]: row for row in read_csv(ROOT / args.predictions)}
    articles = {row["url"]: row for row in read_csv(ROOT / args.articles)}
    cases = [row for row in read_csv(ROOT / args.cases) if row["label"] == "1"]

    multi_ids = sorted(
        row_id for row_id, row in labels.items() if row["event_granularity_true"] == "multi"
    )
    missing = [row_id for row_id in multi_ids if row_id not in audit]
    if missing:
        raise SystemExit(f"audit is incomplete; missing {len(missing)} multi rows: {missing[:5]}")
    extra = sorted(set(audit) - set(multi_ids))
    if extra:
        raise SystemExit(f"audit covers non-multi rows: {extra[:5]}")

    strong = sum(int(audit[row_id]["extra_districtdays_strong"]) for row_id in multi_ids)
    weak = sum(int(audit[row_id]["extra_districtdays_weak"]) for row_id in multi_ids)

    recovery_kind = Counter(audit[row_id]["recovery_kind"] for row_id in multi_ids)
    traps = Counter(
        audit[row_id]["trap_kind"] for row_id in multi_ids if audit[row_id]["trap_kind"]
    )

    # Naive-extractor ceiling: every distinct candidate district beyond the one
    # already assigned would become a new case-day.
    naive_extra = 0
    for row_id in multi_ids:
        article = articles.get(labels[row_id]["url"])
        if article is None:
            continue
        naive_extra += max(0, len(resolve_candidate_districts(article)) - 1)

    # Reweight to the class-1 inventory. Each sampled article stands for
    # `inclusion_weight` inventory articles within its stratum.
    weighted_strong = 0.0
    weighted_weak = 0.0
    weighted_naive = 0.0
    per_article: dict[str, list[int]] = defaultdict(list)
    stratum_weight: dict[str, float] = {}
    stratum_contribution: dict[str, float] = defaultdict(float)
    for row_id in multi_ids:
        meta = predictions.get(row_id)
        if meta is None:
            continue
        weight = float(meta["inclusion_weight"])
        stratum = meta["stratum"]
        stratum_weight[stratum] = weight
        combined = int(audit[row_id]["extra_districtdays_strong"]) + int(
            audit[row_id]["extra_districtdays_weak"]
        )
        per_article[stratum].append(combined)
        stratum_contribution[stratum] += weight * combined
        weighted_strong += weight * int(audit[row_id]["extra_districtdays_strong"])
        weighted_weak += weight * int(audit[row_id]["extra_districtdays_weak"])
        article = articles.get(labels[row_id]["url"])
        if article is not None:
            weighted_naive += weight * max(0, len(resolve_candidate_districts(article)) - 1)

    lower, upper = stratified_bootstrap(
        per_article, stratum_weight, BOOTSTRAP_DRAWS, BOOTSTRAP_SEED
    )

    case_days = len(cases)
    result = {
        "question": (
            "How many additional district-days would per-failure extraction "
            "recover, and at what false-positive cost?"
        ),
        "materiality_threshold_stated_in_advance": MATERIALITY_THRESHOLD,
        "multi_articles_audited": len(multi_ids),
        "sample": {
            "extra_district_days_strong": strong,
            "extra_district_days_weak": weak,
            "extra_district_days_naive_extractor": naive_extra,
            "articles_yielding_nothing": recovery_kind.get("none", 0),
            "recovery_kind": dict(sorted(recovery_kind.items())),
            "trap_kind": dict(sorted(traps.items())),
        },
        "naive_precision_ceiling": {
            "note": (
                "Share of the naive extractor's extra district-days that are "
                "defensible. The complement is the false case-day rate it would "
                "inject into the inventory."
            ),
            "strong_only": round(strong / naive_extra, 4) if naive_extra else None,
            "strong_plus_weak": round((strong + weak) / naive_extra, 4) if naive_extra else None,
        },
        "inventory_projection": {
            "note": (
                "Sample counts reweighted by class-1 stratum inclusion weights, "
                "because the pack oversamples multi-event phrasing."
            ),
            "extra_district_days_strong": round(weighted_strong, 1),
            "extra_district_days_strong_plus_weak": round(weighted_strong + weighted_weak, 1),
            "extra_district_days_naive_extractor": round(weighted_naive, 1),
            "analysis_case_days_v0_6_0": case_days,
            "gain_strong_pct": round(100 * weighted_strong / case_days, 2),
            "gain_strong_plus_weak_pct": round(
                100 * (weighted_strong + weighted_weak) / case_days, 2
            ),
            "naive_false_case_day_pct": round(
                100 * (weighted_naive - weighted_strong - weighted_weak) / case_days, 2
            ),
            "stratum_contribution": {
                key: {
                    "multi_articles_sampled": len(per_article[key]),
                    "inclusion_weight": stratum_weight[key],
                    "contribution": round(value, 1),
                    "share_of_total": round(value / (weighted_strong + weighted_weak), 4)
                    if (weighted_strong + weighted_weak)
                    else None,
                }
                for key, value in sorted(stratum_contribution.items())
            },
        },
        "uncertainty": {
            "note": (
                "Stratified bootstrap over the sampled articles, resampled "
                "within stratum because that is how they were drawn. The "
                "interval is wide because two strata standing for most of the "
                "class-1 inventory are represented by a handful of multi "
                "articles each."
            ),
            "draws": BOOTSTRAP_DRAWS,
            "seed": BOOTSTRAP_SEED,
            "gross_extra_district_days_ci95": [round(lower, 1), round(upper, 1)],
            "gain_pct_ci95": [
                round(100 * lower / case_days, 2),
                round(100 * upper / case_days, 2),
            ],
        },
        "collision_adjustment": {
            "note": (
                "Recovered pairs that already exist as case-days from other "
                "articles add no new district-day. Measured directly against "
                "the v0.6.0 case-day set."
            ),
            "observed_collisions": 4,
            "observed_recovered_pairs": 17,
            "collision_rate": round(COLLISION_RATE, 4),
            "net_extra_district_days": round(
                (weighted_strong + weighted_weak) * (1 - COLLISION_RATE), 1
            ),
            "net_gain_pct": round(
                100 * (weighted_strong + weighted_weak) * (1 - COLLISION_RATE) / case_days, 2
            ),
            "net_gain_pct_ci95": [
                round(100 * lower * (1 - COLLISION_RATE) / case_days, 2),
                round(100 * upper * (1 - COLLISION_RATE) / case_days, 2),
            ],
        },
    }
    net_gain = (weighted_strong + weighted_weak) * (1 - COLLISION_RATE) / case_days
    net_lower = lower * (1 - COLLISION_RATE) / case_days
    result["verdict"] = (
        "material" if net_gain >= MATERIALITY_THRESHOLD else "immaterial_relative_to_cost"
    )
    result["verdict_robust_to_sampling_error"] = bool(net_lower >= MATERIALITY_THRESHOLD)

    output_path = ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"audited {len(multi_ids)} multi articles")
    print(
        f"  sample extra district-days: strong={strong}  weak={weak}  "
        f"naive extractor would emit {naive_extra}"
    )
    ceiling = result["naive_precision_ceiling"]
    print(
        f"  naive precision ceiling: {ceiling['strong_only']} (strong) / "
        f"{ceiling['strong_plus_weak']} (strong+weak)"
    )
    projection = result["inventory_projection"]
    print(
        f"  inventory projection: +{projection['extra_district_days_strong_plus_weak']} "
        f"district-days on {case_days} case-days = "
        f"{projection['gain_strong_plus_weak_pct']}% gross"
    )
    collision = result["collision_adjustment"]
    uncertainty = result["uncertainty"]
    print(
        f"  net of collisions: +{collision['net_extra_district_days']} = "
        f"{collision['net_gain_pct']}%  "
        f"95% CI [{collision['net_gain_pct_ci95'][0]}, {collision['net_gain_pct_ci95'][1]}]"
    )
    print(
        f"  a naive extractor would also inject "
        f"{projection['naive_false_case_day_pct']}% false case-days"
    )
    print("\n  where the estimate comes from:")
    for key, cell in projection["stratum_contribution"].items():
        print(
            f"    {key:12s} n={cell['multi_articles_sampled']:3d} "
            f"weight={cell['inclusion_weight']:7.2f} "
            f"contributes {cell['contribution']:7.1f} "
            f"({cell['share_of_total']:.0%} of the total)"
        )
    print(f"\n  verdict: {result['verdict']}")
    print(f"  robust to sampling error: {result['verdict_robust_to_sampling_error']}")
    _ = uncertainty
    print(f"\nwrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
