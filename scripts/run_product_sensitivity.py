#!/usr/bin/env python3
"""Re-estimate the rainfall threshold on IMERG, with period held fixed.

The question
------------
Is the cutpoint a property of Nepali landslides, or of CHIRPS?

The design
----------
Two things differ between the CHIRPS and IMERG series on disk: the product, and
the period (CHIRPS runs to 2026-07-31; IMERG Final ends at 2025-09-30). Varying
both at once cannot answer the question, and the extra ten months are not a
random slice of the record -- they contain a full monsoon and the densest part
of the inventory. So this script holds period fixed and varies only product:

    CHIRPS-truncated   CHIRPS, 2015-01-01 .. IMERG end   <- the control
    IMERG              IMERG,  2015-01-01 .. IMERG end   <- the test

The published v0.5.0 CHIRPS result is left completely alone. It is the frozen
baseline; this analysis does not touch it, and the truncated run is what the
IMERG run is compared against.

Why the configs are derived rather than written by hand
-------------------------------------------------------
A hand-maintained sensitivity config drifts from the primary one silently: a
changed seed, window list or confidence cut would show up as a "product effect".
Both configs here are generated from the primary config in one place, with
exactly three keys overridden -- rainfall path, product label, output directory --
so any difference in the result is attributable to the product by construction.
A test asserts that no other analysis key differs.

Usage::

    PYTHONPATH=src python3 scripts/run_product_sensitivity.py
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from pathlib import Path
from typing import Any

# The only analysis keys either derived config may change. Everything else must
# be inherited verbatim from the primary config, or the comparison is not a
# product comparison.
OVERRIDDEN_ANALYSIS_KEYS = frozenset(
    {"chirps_daily_district_path", "rainfall_product", "release_version", "supersedes_release"}
)

CONCURRENT = "concurrent_incl_event_day"


def series_end(path: Path) -> str:
    """The last date present in a district-day rainfall CSV."""

    last = ""
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["date"] > last:
                last = row["date"]
    if not last:
        raise ValueError(f"No rows in {path}")
    return last


def truncate_series(source: Path, destination: Path, end_date: str) -> tuple[int, int]:
    """Write the rows of ``source`` on or before ``end_date``. Returns (kept, dropped)."""

    kept = dropped = 0
    destination.parent.mkdir(parents=True, exist_ok=True)
    with source.open("r", encoding="utf-8", newline="") as fin:
        reader = csv.DictReader(fin)
        with destination.open("w", encoding="utf-8", newline="") as fout:
            writer = csv.DictWriter(fout, fieldnames=reader.fieldnames or [])
            writer.writeheader()
            for row in reader:
                if row["date"] <= end_date:
                    writer.writerow(row)
                    kept += 1
                else:
                    dropped += 1
    return kept, dropped


def derive_config(
    primary: dict[str, Any],
    *,
    rainfall_path: str,
    rainfall_product: str,
    outputs_dir: str,
    label: str,
) -> dict[str, Any]:
    """Copy the primary config, overriding only what identifies the product."""

    import copy

    derived = copy.deepcopy(primary)
    derived["paths"] = dict(derived.get("paths", {}))
    derived["paths"]["outputs_dir"] = outputs_dir
    analysis = dict(derived.get("analysis", {}))
    analysis["chirps_daily_district_path"] = rainfall_path
    analysis["rainfall_product"] = rainfall_product
    # These runs are sensitivity analyses, not releases. Marking them keeps them
    # from being mistaken for a versioned result if the directory is copied.
    analysis["release_version"] = f"sensitivity-{label}"
    analysis.pop("supersedes_release", None)
    derived["analysis"] = analysis
    return derived


def headline(report: dict[str, Any], exposure: str = CONCURRENT) -> dict[str, Any]:
    """The numbers the product question actually turns on."""

    primary = report["primary_selected_by_exposure"][exposure]
    development = primary["development"]
    test = primary["temporal_test"]
    return {
        "rainfall_product": report.get("rainfall_product"),
        "rainfall_input_sha256": report.get("rainfall_input_sha256"),
        "available_rainfall_end": report.get("available_rainfall_end"),
        "window_days": development["window_days"],
        "threshold_mm": development["threshold_mm"],
        "threshold_ci_low": development["threshold_ci_low"],
        "threshold_ci_high": development["threshold_ci_high"],
        "development_auc": development["auc"],
        "development_n_cases": development["n_cases"],
        "development_n_controls": development["n_controls"],
        "test_auc": test["auc"],
        "test_auc_ci_low": test["auc_ci_low"],
        "test_auc_ci_high": test["auc_ci_high"],
        "test_sensitivity": test["sensitivity"],
        "test_specificity": test["specificity"],
        "test_n_cases": test["n_cases"],
        "test_n_controls": test["n_controls"],
        "events_after_available_rainfall_end": report.get(
            "primary_events_after_available_rainfall_end"
        ),
    }


def window_matched_thresholds(
    control_dir: Path,
    test_dir: Path,
    *,
    variant: str = "primary_conf_ge_0.78",
    exposure: str = CONCURRENT,
    split: str = "development",
) -> dict[str, dict[str, float]]:
    """Development-fitted threshold and AUC at each window, for both runs.

    Read from the development split because that is where the threshold is
    fitted; the temporal-test rows carry the same threshold and only differ in
    the metrics it produces on held-out data.
    """

    def read(directory: Path) -> dict[int, dict[str, float]]:
        path = directory / "rainfall_threshold_metrics.csv"
        out: dict[int, dict[str, float]] = {}
        with path.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                if (
                    row["split"] == split
                    and row["exposure"] == exposure
                    and row["variant"] == variant
                ):
                    out[int(float(row["window_days"]))] = {
                        "threshold_mm": float(row["threshold_mm"]),
                        "auc": float(row["auc"]),
                    }
        return out

    control = read(control_dir)
    test = read(test_dir)
    matched: dict[str, dict[str, float]] = {}
    for window in sorted(set(control) & set(test)):
        control_threshold = control[window]["threshold_mm"]
        matched[f"R{window}"] = {
            "chirps_threshold_mm": round(control_threshold, 4),
            "imerg_threshold_mm": round(test[window]["threshold_mm"], 4),
            "ratio_imerg_over_chirps": round(test[window]["threshold_mm"] / control_threshold, 4)
            if control_threshold
            else None,
            "chirps_auc": round(control[window]["auc"], 4),
            "imerg_auc": round(test[window]["auc"], 4),
            "auc_difference": round(test[window]["auc"] - control[window]["auc"], 4),
        }
    return matched


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--imerg", default="data/external/imerg_daily_districts.csv")
    parser.add_argument("--chirps", default="data/external/chirps_daily_districts.csv")
    parser.add_argument(
        "--work-dir",
        default="data/sensitivity/product",
        help="where the derived configs, truncated series and run outputs go",
    )
    parser.add_argument(
        "--summary", default="data/outputs/rainfall_product_sensitivity.json"
    )
    parser.add_argument("--skip-runs", action="store_true", help="re-summarise existing runs")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "src"))
    import yaml

    from landslide_inventory.analysis import run_rainfall_analysis_stage
    from landslide_inventory.config import load_config

    primary = yaml.safe_load((root / args.config).read_text(encoding="utf-8"))
    work = root / args.work_dir
    work.mkdir(parents=True, exist_ok=True)

    imerg_path = root / args.imerg
    chirps_path = root / args.chirps
    end_date = series_end(imerg_path)
    print(f"IMERG record ends {end_date}; truncating CHIRPS to match.")

    truncated = work / "chirps_daily_districts_truncated.csv"
    kept, dropped = truncate_series(chirps_path, truncated, end_date)
    print(f"CHIRPS control: kept {kept:,} district-days, dropped {dropped:,} after {end_date}")

    runs = {
        "chirps_truncated": {
            "rainfall_path": str(truncated.relative_to(root)),
            "rainfall_product": (
                f"{primary['analysis']['rainfall_product']} (truncated to {end_date})"
            ),
        },
        "imerg": {
            "rainfall_path": str(imerg_path.relative_to(root)),
            "rainfall_product": "NASA IMERG Final Run v07 (GPM_3IMERGDF)",
        },
    }

    summary: dict[str, Any] = {
        "design": (
            "Period is held fixed and only the rainfall product varies. Both runs "
            f"cover 2015-01-01 to {end_date}. The published v0.5.0 CHIRPS result is "
            "untouched and is NOT the comparator: comparing IMERG against it would "
            "vary product and period together."
        ),
        "common_end_date": end_date,
        "chirps_district_days_dropped_for_the_control": dropped,
        "aggregation_caveat": (
            "CHIRPS district means are ClimateSERV's area-weighted server-side mean; "
            "IMERG district means are unweighted means of 0.1-degree cell centres. "
            "The two runs differ in aggregation as well as in product."
        ),
        "runs": {},
    }

    for label, spec in runs.items():
        outputs_dir = f"{args.work_dir}/{label}"
        (root / outputs_dir).mkdir(parents=True, exist_ok=True)
        derived = derive_config(
            primary,
            rainfall_path=spec["rainfall_path"],
            rainfall_product=spec["rainfall_product"],
            outputs_dir=outputs_dir,
            label=label,
        )
        config_path = root / f"config.sensitivity_{label}.yaml"
        config_path.write_text(
            yaml.safe_dump(derived, sort_keys=False, allow_unicode=True), encoding="utf-8"
        )
        if not args.skip_runs:
            print(f"\n=== running {label} ===")
            run_rainfall_analysis_stage(load_config(config_path))
        report_path = root / outputs_dir / "rainfall_analysis_report.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        summary["runs"][label] = headline(report)
        summary["runs"][label]["config"] = config_path.name
        summary["runs"][label]["outputs_dir"] = outputs_dir

    control = summary["runs"]["chirps_truncated"]
    test = summary["runs"]["imerg"]

    # WINDOW-MATCHED, DELIBERATELY.
    #
    # Each run selects its own best window in development, and the two runs do
    # not select the same one. Dividing one run's selected-window threshold by
    # the other's therefore divides millimetres at R3 by millimetres at R5 --
    # a ratio of two different quantities, which looks like a dramatic product
    # effect and means nothing. Thresholds are only comparable within a window.
    by_window = window_matched_thresholds(
        root / f"{args.work_dir}/chirps_truncated",
        root / f"{args.work_dir}/imerg",
    )
    summary["window_matched_thresholds"] = by_window
    summary["comparison"] = {
        "selected_window_chirps": control["window_days"],
        "selected_window_imerg": test["window_days"],
        "windows_agree": control["window_days"] == test["window_days"],
        "threshold_ratios_by_window": {
            window: values["ratio_imerg_over_chirps"] for window, values in by_window.items()
        },
        "note_on_cross_window_ratios": (
            "Thresholds are comparable only within a window. The two runs select "
            "different windows in development, so no ratio between their selected "
            "thresholds is reported: it would divide R3 millimetres by R5 "
            "millimetres."
        ),
        "test_auc_difference_imerg_minus_chirps": round(
            test["test_auc"] - control["test_auc"], 4
        ),
        "imerg_threshold_inside_chirps_bootstrap_interval": bool(
            control["threshold_ci_low"] <= test["threshold_mm"] <= control["threshold_ci_high"]
        ),
        "chirps_threshold_inside_imerg_bootstrap_interval": bool(
            test["threshold_ci_low"] <= control["threshold_mm"] <= test["threshold_ci_high"]
        ),
        "auc_intervals_overlap": bool(
            test["test_auc_ci_low"] <= control["test_auc_ci_high"]
            and control["test_auc_ci_low"] <= test["test_auc_ci_high"]
        ),
    }

    summary_path = root / args.summary
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"\nwrote {args.summary}")
    print(json.dumps(summary["comparison"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
