#!/usr/bin/env python3
"""Compare two district-day rainfall products on their common support.

Why this exists
---------------
Every threshold in this study is estimated from one rainfall product, CHIRPS.
The standing reviewer question is whether the cutpoint describes Nepali
landslides or describes CHIRPS. Answering it needs two things, and the second is
the one that is easy to get wrong:

1. Re-estimating the threshold on a second product (NASA IMERG). That is done by
   the analysis stage, driven by a config that points at the IMERG series.
2. Knowing *how the two products differ as measurements*, so that a shift in the
   cutpoint can be attributed. A cutpoint that moves by the same factor as the
   products' mean ratio is a units difference; one that moves independently is
   something else.

THE TRAP THIS SCRIPT IS BUILT TO PREVENT
----------------------------------------
The two series do not cover the same period. CHIRPS runs to 2026-07-31; IMERG
Final publishes with months of latency and ends at 2025-09-30. Comparing the
full CHIRPS record against the shorter IMERG record confounds *product* with
*period* -- the extra ten months are a monsoon-weighted, non-random slice, and
any difference it produces is uninterpretable.

So this script never accepts two periods. It intersects the district-days
present in both series, reports the intersection explicitly, and refuses to
report a comparison at all if the overlap is too thin to mean anything. Every
statistic below is computed on identical district-days.

What is compared
----------------
Daily values and the antecedent accumulations the analysis actually uses
(R1/R3/R5/R7), because agreement on daily rain and agreement on a five-day
accumulation are different questions and the second is the one the threshold
depends on. For each, on the common support:

* Spearman and Pearson correlation
* mean and median difference (B minus A), MAE, RMSE, ratio of means
* agreement on exceeding a stated operating cutpoint, as a 2x2 table with
  percentage agreement and Cohen's kappa

Two caveats are carried into the output rather than left to the reader
-----------------------------------------------------------------------
* CHIRPS district means come from ClimateSERV's area-weighted server-side mean;
  IMERG means here are unweighted means of 0.1-degree cell centres inside each
  district. The comparison differs in aggregation as well as in product.
* Bhaktapur resolves to one IMERG grid cell and Kathmandu to three. Their
  per-district rows are flagged, and a summary excluding them is reported
  alongside the full one.

Usage::

    PYTHONPATH=src python3 scripts/compare_rainfall_products.py \\
        --product-a data/external/chirps_daily_districts.csv \\
        --product-b data/external/imerg_daily_districts.csv \\
        --label-a "CHIRPS v2.0 Final" --label-b "IMERG Final v07" \\
        --cutpoint-mm 51.6 --cutpoint-window 5 \\
        --output data/outputs/rainfall_product_comparison.json \\
        --markdown docs/RAINFALL_PRODUCT_COMPARISON.md
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Mapping, Sequence

# A comparison computed on a handful of district-days is not evidence about a
# product. Below this the script reports the overlap and declines to summarise.
MINIMUM_COMMON_DISTRICT_DAYS = 1000

# Flagged in the IMERG run manifest: too few grid cells for a district mean to
# be a meaningful areal estimate.
SPARSE_SUPPORT_DISTRICTS = ("Bhaktapur", "Kathmandu")


def pearson(x_values: Sequence[float], y_values: Sequence[float]) -> float:
    if len(x_values) != len(y_values) or len(x_values) < 2:
        return math.nan
    x_mean = sum(x_values) / len(x_values)
    y_mean = sum(y_values) / len(y_values)
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_values, y_values, strict=False))
    x_scale = math.sqrt(sum((x - x_mean) ** 2 for x in x_values))
    y_scale = math.sqrt(sum((y - y_mean) ** 2 for y in y_values))
    return numerator / (x_scale * y_scale) if x_scale and y_scale else math.nan


def cohen_kappa(a_flags: Sequence[int], b_flags: Sequence[int]) -> float:
    """Agreement beyond chance on a binary exceedance call."""

    n = len(a_flags)
    if n == 0:
        return math.nan
    both = sum(1 for a, b in zip(a_flags, b_flags, strict=False) if a == 1 and b == 1)
    neither = sum(1 for a, b in zip(a_flags, b_flags, strict=False) if a == 0 and b == 0)
    observed = (both + neither) / n
    a_rate = sum(a_flags) / n
    b_rate = sum(b_flags) / n
    expected = a_rate * b_rate + (1 - a_rate) * (1 - b_rate)
    if expected >= 1.0:
        # Both products call every district-day the same way; kappa is undefined
        # rather than perfect, and reporting 1.0 would overstate the evidence.
        return math.nan
    return (observed - expected) / (1 - expected)


def common_support(
    a_values: Mapping[tuple[str, date], float],
    b_values: Mapping[tuple[str, date], float],
) -> list[tuple[str, date]]:
    """The district-days present in BOTH products, sorted deterministically."""

    return sorted(set(a_values) & set(b_values), key=lambda key: (key[0], key[1]))


def window_series(
    values: Mapping[tuple[str, date], float],
    keys: Sequence[tuple[str, date]],
    window: int,
) -> list[float | None]:
    """Accumulations ending on each key's day; ``None`` if the window is incomplete.

    A window is only usable when every day in it is present in *both* products,
    which the caller enforces by pairing the returned lists.
    """

    series: list[float | None] = []
    for district, day in keys:
        total = 0.0
        complete = True
        for offset in range(window):
            value = values.get((district, day - timedelta(days=offset)))
            if value is None:
                complete = False
                break
            total += value
        series.append(total if complete else None)
    return series


def paired(
    a_series: Sequence[float | None], b_series: Sequence[float | None]
) -> tuple[list[float], list[float], list[int]]:
    """Drop any position where either product lacks a complete window."""

    a_out: list[float] = []
    b_out: list[float] = []
    kept: list[int] = []
    for index, (a, b) in enumerate(zip(a_series, b_series, strict=False)):
        if a is None or b is None:
            continue
        a_out.append(a)
        b_out.append(b)
        kept.append(index)
    return a_out, b_out, kept


def agreement_statistics(
    a_values: Sequence[float],
    b_values: Sequence[float],
    *,
    cutpoint_mm: float | None,
) -> dict[str, object]:
    from landslide_inventory.analysis.rainfall import spearman

    n = len(a_values)
    if n < 2:
        return {"n": n, "insufficient": True}
    differences = [b - a for a, b in zip(a_values, b_values, strict=False)]
    a_mean = sum(a_values) / n
    b_mean = sum(b_values) / n
    stats: dict[str, object] = {
        "n": n,
        "mean_a": round(a_mean, 4),
        "mean_b": round(b_mean, 4),
        "ratio_of_means_b_over_a": round(b_mean / a_mean, 4) if a_mean else None,
        "mean_difference_b_minus_a": round(sum(differences) / n, 4),
        "median_difference_b_minus_a": round(statistics.median(differences), 4),
        "mean_absolute_difference": round(sum(abs(d) for d in differences) / n, 4),
        "rmse": round(math.sqrt(sum(d * d for d in differences) / n), 4),
        "spearman": round(spearman(a_values, b_values), 4),
        "pearson": round(pearson(a_values, b_values), 4),
    }
    if cutpoint_mm is not None:
        a_flags = [1 if value >= cutpoint_mm else 0 for value in a_values]
        b_flags = [1 if value >= cutpoint_mm else 0 for value in b_values]
        both = sum(1 for a, b in zip(a_flags, b_flags, strict=False) if a and b)
        a_only = sum(1 for a, b in zip(a_flags, b_flags, strict=False) if a and not b)
        b_only = sum(1 for a, b in zip(a_flags, b_flags, strict=False) if b and not a)
        neither = n - both - a_only - b_only
        stats["exceedance"] = {
            "cutpoint_mm": cutpoint_mm,
            "both": both,
            "a_only": a_only,
            "b_only": b_only,
            "neither": neither,
            "exceedance_rate_a": round((both + a_only) / n, 5),
            "exceedance_rate_b": round((both + b_only) / n, 5),
            "percent_agreement": round((both + neither) / n, 5),
            "cohen_kappa": round(cohen_kappa(a_flags, b_flags), 4),
        }
    return stats


def compare_products(
    a_path: Path,
    b_path: Path,
    *,
    windows: Sequence[int],
    cutpoint_mm: float,
    cutpoint_window: int,
    label_a: str,
    label_b: str,
) -> dict[str, object]:
    from landslide_inventory.analysis.rainfall import read_daily_rainfall

    product_a = read_daily_rainfall(a_path)
    product_b = read_daily_rainfall(b_path)
    keys = common_support(product_a.values, product_b.values)

    days = sorted({day for _, day in keys})
    districts = sorted({district for district, _ in keys})
    overlap = {
        "product_a": {
            "label": label_a,
            "path": str(a_path),
            "start": product_a.start.isoformat(),
            "end": product_a.end.isoformat(),
            "district_days": product_a.row_count,
            "districts": len(product_a.districts),
        },
        "product_b": {
            "label": label_b,
            "path": str(b_path),
            "start": product_b.start.isoformat(),
            "end": product_b.end.isoformat(),
            "district_days": product_b.row_count,
            "districts": len(product_b.districts),
        },
        "common_district_days": len(keys),
        "common_start": days[0].isoformat() if days else None,
        "common_end": days[-1].isoformat() if days else None,
        "common_days": len(days),
        "common_districts": len(districts),
        "district_days_only_in_a": product_a.row_count - len(keys),
        "district_days_only_in_b": product_b.row_count - len(keys),
    }

    result: dict[str, object] = {
        "comparison_is_restricted_to_common_support": True,
        "why": (
            "The products cover different periods. Comparing their full records "
            "would confound product with period, because the non-overlapping "
            "tail is a seasonally non-random slice. Every statistic below is "
            "computed on district-days present in both series."
        ),
        "aggregation_caveat": (
            f"{label_a} district means are area-weighted (ClimateSERV, server-side); "
            f"{label_b} district means are unweighted means of 0.1-degree cell "
            "centres inside each district. This comparison therefore differs in "
            "aggregation as well as in product."
        ),
        "sparse_support_districts": list(SPARSE_SUPPORT_DISTRICTS),
        "overlap": overlap,
    }

    if len(keys) < MINIMUM_COMMON_DISTRICT_DAYS:
        result["insufficient_overlap"] = True
        result["minimum_common_district_days"] = MINIMUM_COMMON_DISTRICT_DAYS
        return result

    a_daily = [product_a.values[key] for key in keys]
    b_daily = [product_b.values[key] for key in keys]
    by_exposure: dict[str, object] = {
        "daily": agreement_statistics(a_daily, b_daily, cutpoint_mm=None)
    }
    for window in windows:
        a_series = window_series(product_a.values, keys, window)
        b_series = window_series(product_b.values, keys, window)
        a_paired, b_paired, _ = paired(a_series, b_series)
        by_exposure[f"R{window}"] = agreement_statistics(
            a_paired,
            b_paired,
            cutpoint_mm=cutpoint_mm if window == cutpoint_window else None,
        )
    result["by_exposure"] = by_exposure

    # Per-district agreement on the exposure the threshold is defined on. A
    # product difference concentrated in a few districts is a different finding
    # from one spread evenly, and only the per-district view separates them.
    a_series = window_series(product_a.values, keys, cutpoint_window)
    b_series = window_series(product_b.values, keys, cutpoint_window)
    per_district: dict[str, object] = {}
    for district in districts:
        indices = [index for index, key in enumerate(keys) if key[0] == district]
        a_values = [a_series[index] for index in indices]
        b_values = [b_series[index] for index in indices]
        a_paired, b_paired, _ = paired(a_values, b_values)
        stats = agreement_statistics(a_paired, b_paired, cutpoint_mm=cutpoint_mm)
        stats["sparse_grid_support"] = district in SPARSE_SUPPORT_DISTRICTS
        per_district[district] = stats
    result["per_district_at_cutpoint_window"] = {
        "window_days": cutpoint_window,
        "cutpoint_mm": cutpoint_mm,
        "districts": per_district,
    }

    # The same headline numbers with the two sparse-support districts removed,
    # so a reader can see whether they drive anything.
    dense_keys = [key for key in keys if key[0] not in SPARSE_SUPPORT_DISTRICTS]
    dense_a = window_series(product_a.values, dense_keys, cutpoint_window)
    dense_b = window_series(product_b.values, dense_keys, cutpoint_window)
    a_paired, b_paired, _ = paired(dense_a, dense_b)
    result["excluding_sparse_support_districts"] = {
        "window_days": cutpoint_window,
        "excluded": list(SPARSE_SUPPORT_DISTRICTS),
        **agreement_statistics(a_paired, b_paired, cutpoint_mm=cutpoint_mm),
    }
    return result


def markdown_report(result: dict[str, object]) -> str:
    overlap = result["overlap"]  # type: ignore[index]
    a = overlap["product_a"]  # type: ignore[index]
    b = overlap["product_b"]  # type: ignore[index]
    lines = [
        "# Rainfall product comparison: CHIRPS vs IMERG",
        "",
        "<!-- Generated by scripts/compare_rainfall_products.py — do not edit by hand. -->",
        "",
        "## What was compared, and on what",
        "",
        f"- **{a['label']}**: {a['district_days']:,} district-days, "
        f"{a['start']} to {a['end']}",
        f"- **{b['label']}**: {b['district_days']:,} district-days, "
        f"{b['start']} to {b['end']}",
        f"- **Common support**: {overlap['common_district_days']:,} district-days, "
        f"{overlap['common_days']:,} days x {overlap['common_districts']} districts, "
        f"{overlap['common_start']} to {overlap['common_end']}",
        f"- District-days in {a['label']} only: {overlap['district_days_only_in_a']:,} "
        f"(the product's later record, which has no IMERG counterpart)",
        "",
        f"{result['why']}",
        "",
    ]
    if result.get("insufficient_overlap"):
        lines += [
            "**The overlap is too small to support a comparison.** "
            f"Fewer than {result['minimum_common_district_days']:,} common district-days.",
            "",
        ]
        return "\n".join(lines)

    lines += [
        "## Agreement by exposure",
        "",
        "| Exposure | n | mean A | mean B | B/A | mean diff | MAE | RMSE | Spearman | Pearson |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, stats in result["by_exposure"].items():  # type: ignore[index]
        if stats.get("insufficient"):
            continue
        lines.append(
            f"| {name} | {stats['n']:,} | {stats['mean_a']:.2f} | {stats['mean_b']:.2f} | "
            f"{stats['ratio_of_means_b_over_a']:.3f} | "
            f"{stats['mean_difference_b_minus_a']:+.2f} | "
            f"{stats['mean_absolute_difference']:.2f} | {stats['rmse']:.2f} | "
            f"{stats['spearman']:.3f} | {stats['pearson']:.3f} |"
        )

    cutpoint_stats = None
    for name, stats in result["by_exposure"].items():  # type: ignore[index]
        if isinstance(stats, dict) and "exceedance" in stats:
            cutpoint_stats = (name, stats["exceedance"])
    if cutpoint_stats is not None:
        name, exceedance = cutpoint_stats
        lines += [
            "",
            f"## Agreement on exceeding {exceedance['cutpoint_mm']} mm at {name}",
            "",
            "This is the comparison that matters operationally: not whether the two "
            "products report the same millimetres, but whether they make the same "
            "call on the same district-day.",
            "",
            "| | B exceeds | B does not |",
            "| --- | ---: | ---: |",
            f"| **A exceeds** | {exceedance['both']:,} | {exceedance['a_only']:,} |",
            f"| **A does not** | {exceedance['b_only']:,} | {exceedance['neither']:,} |",
            "",
            f"- Exceedance rate, {a['label']}: {exceedance['exceedance_rate_a']:.4f}",
            f"- Exceedance rate, {b['label']}: {exceedance['exceedance_rate_b']:.4f}",
            f"- Percentage agreement: {exceedance['percent_agreement']:.4f}",
            f"- Cohen's kappa: {exceedance['cohen_kappa']:.3f}",
            "",
        ]

    dense = result.get("excluding_sparse_support_districts")
    if isinstance(dense, dict) and not dense.get("insufficient"):
        lines += [
            "## Excluding the two districts with almost no IMERG grid support",
            "",
            f"Bhaktapur resolves to one 0.1-degree cell and Kathmandu to three, so "
            f"their IMERG 'district means' are close to point measurements. "
            f"Removing them leaves {dense['n']:,} district-days at R{dense['window_days']}:",
            "",
            f"- ratio of means (B/A): {dense['ratio_of_means_b_over_a']:.3f}",
            f"- Spearman: {dense['spearman']:.3f}",
        ]
        if "exceedance" in dense:
            lines.append(f"- Cohen's kappa on exceedance: {dense['exceedance']['cohen_kappa']:.3f}")
        lines.append("")

    lines += [
        "## Caveats carried into the manuscript",
        "",
        f"1. {result['aggregation_caveat']}",
        "2. Bhaktapur (1 grid cell) and Kathmandu (3) have almost no spatial "
        "support in IMERG and should be caveated in any per-district reading.",
        "3. This comparison establishes how the two products differ **as "
        "measurements**. Whether the threshold itself is product-dependent is a "
        "separate question, answered by re-estimating it on IMERG over this same "
        "period with an identically truncated CHIRPS run as the control.",
        "",
    ]
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--product-a", default="data/external/chirps_daily_districts.csv")
    parser.add_argument("--product-b", default="data/external/imerg_daily_districts.csv")
    parser.add_argument("--label-a", default="UCSB CHIRPS v2.0 Final")
    parser.add_argument("--label-b", default="NASA IMERG Final Run v07")
    parser.add_argument("--windows", default="1,3,5,7")
    parser.add_argument("--cutpoint-mm", type=float, default=51.6)
    parser.add_argument("--cutpoint-window", type=int, default=5)
    parser.add_argument("--output", default="data/outputs/rainfall_product_comparison.json")
    parser.add_argument("--markdown", default="docs/RAINFALL_PRODUCT_COMPARISON.md")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "src"))
    windows = [int(value) for value in args.windows.split(",") if value.strip()]
    result = compare_products(
        root / args.product_a,
        root / args.product_b,
        windows=windows,
        cutpoint_mm=args.cutpoint_mm,
        cutpoint_window=args.cutpoint_window,
        label_a=args.label_a,
        label_b=args.label_b,
    )
    output_path = root / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    markdown_path = root / args.markdown
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(markdown_report(result) + "\n", encoding="utf-8")
    overlap = result["overlap"]
    print(
        f"common support: {overlap['common_district_days']:,} district-days "
        f"({overlap['common_start']} to {overlap['common_end']})"
    )
    print(f"wrote {args.output} and {args.markdown}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
