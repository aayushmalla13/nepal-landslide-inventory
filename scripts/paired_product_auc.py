#!/usr/bin/env python3
"""Paired, district-clustered comparison of discrimination between two products.

Why a paired test, and not two confidence intervals
---------------------------------------------------
The CHIRPS-truncated and IMERG sensitivity runs share an identical case-control
design: the same events, the same drawn control district-days, the same seed,
the same strata. Only the rainfall values attached to each record differ. Two
runs that differ in exactly one input are the textbook setting for a paired
comparison, and treating them as independent throws that away.

Reading two marginal bootstrap intervals and noting that they overlap is not a
test. Overlapping intervals are routinely produced by differences that a paired
test resolves comfortably, because the marginal intervals carry the sampling
variability of the design itself -- variability that is *common to both runs*
and cancels when the same resample is scored under both products.

So this script resamples ONCE per iteration and scores both products on that
same resample, giving a bootstrap distribution of the difference. Resampling is
by district cluster, matching the clustering used throughout the analysis:
district-days within a district are not independent, and resampling records
would understate the interval.

Guard rails
-----------
* The two inputs must describe the same design. If the record ids, dates,
  districts, labels or strata differ in any position the script refuses to run
  rather than silently comparing different things.
* A deterministic seed, per the project's reproducibility rules.
* The difference is reported with a percentile interval and the share of
  iterations favouring each product. No p-value is manufactured from it.

Usage::

    PYTHONPATH=src python3 scripts/paired_product_auc.py
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from pathlib import Path
from typing import Sequence

DEV_END = "2022-12-31"
EXPOSURES = {1: "r1_mm", 3: "r3_mm", 5: "r5_mm", 7: "r7_mm"}


class DesignMismatch(RuntimeError):
    """The two runs do not share a case-control design, so they cannot be paired."""


def read_records(outputs_dir: Path) -> list[dict[str, str]]:
    """Cases and controls from one run, in a fixed order."""

    records: list[dict[str, str]] = []
    for name in ("event_antecedent_rainfall.csv", "rainfall_controls.csv"):
        path = outputs_dir / name
        with path.open("r", encoding="utf-8", newline="") as handle:
            records.extend(csv.DictReader(handle))
    records.sort(key=lambda row: (row["district"], row["date"], row["record_id"]))
    return records


def design_key(row: dict[str, str]) -> tuple[str, ...]:
    return (
        row["record_id"],
        row["matched_event_id"],
        row["date"],
        row["district"],
        row["label"],
    )


def assert_same_design(a: Sequence[dict[str, str]], b: Sequence[dict[str, str]]) -> None:
    if len(a) != len(b):
        raise DesignMismatch(
            f"different record counts: {len(a)} vs {len(b)}. The runs must share "
            "one case-control design for a paired comparison to mean anything."
        )
    for index, (left, right) in enumerate(zip(a, b, strict=False)):
        if design_key(left) != design_key(right):
            raise DesignMismatch(
                f"designs diverge at position {index}: "
                f"{design_key(left)} vs {design_key(right)}"
            )


def split_of(row: dict[str, str]) -> str:
    return "development" if row["date"] <= DEV_END else "temporal_test"


def paired_auc_difference(
    a_records: Sequence[dict[str, str]],
    b_records: Sequence[dict[str, str]],
    *,
    column: str,
    split: str,
    iterations: int,
    seed: int,
) -> dict[str, object]:
    from landslide_inventory.analysis.rainfall import auc, percentile

    indices = [
        index
        for index, row in enumerate(a_records)
        if split_of(row) == split and row[column] not in ("", "NA")
    ]
    labels = [int(a_records[index]["label"]) for index in indices]
    a_scores = [float(a_records[index][column]) for index in indices]
    b_scores = [float(b_records[index][column]) for index in indices]
    if len(set(labels)) < 2:
        return {"split": split, "column": column, "insufficient": True}

    observed_a = auc(labels, a_scores)
    observed_b = auc(labels, b_scores)

    by_district: dict[str, list[int]] = {}
    for position, index in enumerate(indices):
        by_district.setdefault(a_records[index]["district"], []).append(position)
    districts = sorted(by_district)

    rng = random.Random(seed)
    differences: list[float] = []
    for _ in range(iterations):
        drawn: list[int] = []
        for _ in range(len(districts)):
            drawn.extend(by_district[districts[rng.randrange(len(districts))]])
        resampled_labels = [labels[position] for position in drawn]
        if len(set(resampled_labels)) < 2:
            continue
        a_resampled = [a_scores[position] for position in drawn]
        b_resampled = [b_scores[position] for position in drawn]
        differences.append(
            auc(resampled_labels, b_resampled) - auc(resampled_labels, a_resampled)
        )

    differences.sort()
    favouring_b = sum(1 for value in differences if value > 0)
    return {
        "split": split,
        "column": column,
        "n": len(indices),
        "n_cases": sum(labels),
        "n_districts": len(districts),
        "auc_a": round(observed_a, 6),
        "auc_b": round(observed_b, 6),
        "auc_difference_b_minus_a": round(observed_b - observed_a, 6),
        "difference_ci_low": round(percentile(differences, 0.025), 6),
        "difference_ci_high": round(percentile(differences, 0.975), 6),
        "bootstrap_iterations_used": len(differences),
        "share_of_iterations_favouring_b": round(favouring_b / len(differences), 4)
        if differences
        else None,
        "interval_excludes_zero": bool(
            percentile(differences, 0.025) > 0 or percentile(differences, 0.975) < 0
        ),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--run-a", default="data/sensitivity/product/chirps_truncated")
    parser.add_argument("--run-b", default="data/sensitivity/product/imerg")
    parser.add_argument("--label-a", default="CHIRPS (truncated to the IMERG record)")
    parser.add_argument("--label-b", default="IMERG Final v07")
    parser.add_argument("--iterations", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=20260904)
    parser.add_argument("--output", default="data/outputs/rainfall_product_paired_auc.json")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "src"))

    a_records = read_records(root / args.run_a)
    b_records = read_records(root / args.run_b)
    assert_same_design(a_records, b_records)

    result: dict[str, object] = {
        "product_a": args.label_a,
        "product_b": args.label_b,
        "design": (
            "Both runs share one case-control design (same events, same drawn "
            "controls, same seed); only the rainfall values differ. Each bootstrap "
            "iteration resamples districts once and scores BOTH products on that "
            "same resample, so the design's own sampling variability cancels."
        ),
        "clustering": "district",
        "iterations": args.iterations,
        "seed": args.seed,
        "records_paired": len(a_records),
        "comparisons": {},
    }
    for window, column in EXPOSURES.items():
        for split in ("development", "temporal_test"):
            key = f"R{window}_{split}"
            result["comparisons"][key] = paired_auc_difference(
                a_records,
                b_records,
                column=column,
                split=split,
                iterations=args.iterations,
                seed=args.seed + window,
            )

    output_path = root / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"paired on {len(a_records):,} records\n")
    header = f"{'exposure':>18} {'AUC A':>8} {'AUC B':>8} {'diff':>9} {'95% CI':>20} {'excl 0':>7}"
    print(header)
    print("-" * len(header))
    for key, stats in result["comparisons"].items():
        if stats.get("insufficient"):
            continue
        interval = f"[{stats['difference_ci_low']:+.4f}, {stats['difference_ci_high']:+.4f}]"
        print(
            f"{key:>18} {stats['auc_a']:8.4f} {stats['auc_b']:8.4f} "
            f"{stats['auc_difference_b_minus_a']:+9.4f} {interval:>20} "
            f"{'yes' if stats['interval_excludes_zero'] else 'no':>7}"
        )
    print(f"\nwrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
