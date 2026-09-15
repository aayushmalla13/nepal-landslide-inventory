#!/usr/bin/env python3
"""Generate the manuscript tables from the analysis release outputs.

Why this is generated rather than written
-----------------------------------------
``docs/RAINFALL_MANUSCRIPT_TABLES.md`` was maintained by hand. It held roughly
sixty numbers copied out of the analysis, and by v0.5.0 every one of them was
stale: the file still reported the v0.2.0 cutpoint of 45.4 mm and a
leave-one-year-out threshold range of 45.38-45.42 mm that no longer existed. A
hand-copied table is a second source of truth that silently diverges from the
first, and in a paper it is the version a reader would quote.

Everything here is read from ``rainfall_analysis_report.json`` and the release
CSVs, so the tables cannot disagree with the analysis. Re-run it after every
``rainfall_release``.

Usage::

    PYTHONPATH=src python3 scripts/build_manuscript_tables.py
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CONCURRENT = "concurrent_incl_event_day"
ANTECEDENT = "strictly_antecedent_excl_event_day"


def fmt(value: object, places: int = 3) -> str:
    if value is None or value == "":
        return "—"
    if isinstance(value, str):
        try:
            value = float(value)
        except ValueError:
            return value
    if isinstance(value, float):
        return f"{value:.{places}f}"
    return str(value)


def mm(value: object) -> str:
    return fmt(value, 1)


def interval(low: object, high: object, places: int = 3) -> str:
    if low in (None, "") or high in (None, ""):
        return "—"
    return f"{fmt(low, places)}–{fmt(high, places)}"


def read_csv(path: Path) -> list[dict[str, str]]:
    csv.field_size_limit(sys.maxsize)
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


PRIMARY_VARIANT = "primary_conf_ge_0.78"


def window_table(rows: list[dict[str, str]], exposure: str, selected: int | None) -> list[str]:
    lines = [
        "| Window | Development AUC | Threshold (mm) | Threshold 95% CI (development) "
        "| Test AUC (95% CI) | Test sensitivity | Test specificity |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    by_window: dict[int, dict[str, dict[str, str]]] = {}
    for row in rows:
        if row.get("exposure") != exposure:
            continue
        # The metrics file holds every sensitivity variant. Tables 1 and 2 are
        # the primary analysis; without this filter the last variant to appear
        # wins and the table silently reports, say, the strict-matched-set run.
        if row.get("variant") != PRIMARY_VARIANT:
            continue
        window = int(float(row["window_days"]))
        by_window.setdefault(window, {})[row["split"]] = row
    for window in sorted(by_window):
        development = by_window[window].get("development")
        test = by_window[window].get("temporal_test")
        if development is None or test is None:
            continue
        label = f"{window} day" + ("" if window == 1 else "s")
        if window == selected:
            label = f"**{label} (selected)**"
        lines.append(
            "| {label} | {dev_auc} | {thr} | {thr_ci} | {test_auc} | {sens} | {spec} |".format(
                label=label,
                dev_auc=fmt(development["auc"]),
                thr=mm(development["threshold_mm"]),
                thr_ci=interval(
                    development.get("threshold_ci_low"),
                    development.get("threshold_ci_high"),
                    1,
                ),
                test_auc=f"{fmt(test['auc'])} ({interval(test.get('auc_ci_low'), test.get('auc_ci_high'))})",
                sens=fmt(test["sensitivity"]),
                spec=fmt(test["specificity"]),
            )
        )
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outputs", default="data/outputs")
    parser.add_argument("--out", default="docs/RAINFALL_MANUSCRIPT_TABLES.md")
    args = parser.parse_args()

    outputs = ROOT / args.outputs
    report = json.loads((outputs / "rainfall_analysis_report.json").read_text(encoding="utf-8"))
    metrics = read_csv(outputs / "rainfall_threshold_metrics.csv")
    conditional = read_csv(outputs / "rainfall_conditional_models.csv")
    resampled = read_csv(outputs / "rainfall_resampled_validation.csv")
    sensitivity = read_csv(outputs / "rainfall_sensitivity_summary.csv")
    seasons = read_csv(outputs / "rainfall_season_stratified.csv")

    primary = report["primary_selected_by_exposure"]
    concurrent_test = primary[CONCURRENT]["temporal_test"]
    antecedent_test = primary[ANTECEDENT]["temporal_test"]
    selected_concurrent = None
    selected_antecedent = None
    for row in metrics:
        if row.get("split") != "temporal_test":
            continue
        if row.get("exposure") == CONCURRENT and abs(
            float(row["threshold_mm"]) - float(concurrent_test["threshold_mm"])
        ) < 1e-6:
            selected_concurrent = int(float(row["window_days"]))
        if row.get("exposure") == ANTECEDENT and abs(
            float(row["threshold_mm"]) - float(antecedent_test["threshold_mm"])
        ) < 1e-6:
            selected_antecedent = int(float(row["window_days"]))

    import yaml

    version = str(
        yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))["analysis"][
            "release_version"
        ]
    )
    lines: list[str] = [
        "# Rainfall manuscript tables",
        "",
        "**Generated file — do not edit by hand.** Rebuild with",
        "`PYTHONPATH=src python3 scripts/build_manuscript_tables.py` after every",
        "`rainfall_release`. Every number is read from the analysis outputs, so these",
        "tables cannot drift away from the analysis the way a hand-maintained copy did.",
        "",
        f"Analysis version {version}. Threshold confidence intervals are estimated in the",
        "development split; performance intervals in the untouched temporal test split.",
        "",
        "## Table 1. Primary exposure — concurrent windows, including the reported event day",
        "",
    ]
    lines += window_table(metrics, CONCURRENT, selected_concurrent)
    lines += [
        "",
        "## Table 2. Co-primary exposure — strictly antecedent windows, excluding the event day",
        "",
    ]
    lines += window_table(metrics, ANTECEDENT, selected_antecedent)

    lines += [
        "",
        "## Table 3. Conditional (within-matched-set) logistic models",
        "",
        "| Split | Exposure | Window | Odds ratio per 10 mm | 95% CI | Within-stratum concordance |",
        "|---|---|---:|---:|---:|---:|",
    ]
    exposure_label = {CONCURRENT: "Concurrent", ANTECEDENT: "Strictly antecedent"}
    split_label = {
        "all_years": "All years",
        "development": "Development",
        "temporal_test": "Temporal test",
    }
    for row in conditional:
        window = int(float(row["window_days"]))
        exposure = row["exposure"]
        if (exposure == CONCURRENT and window != selected_concurrent) or (
            exposure == ANTECEDENT and window != selected_antecedent
        ):
            continue
        lines.append(
            "| {split} | {exposure} | {window} | {odds} | {ci} | {conc} |".format(
                split=split_label.get(row["split"], row["split"]),
                exposure=exposure_label.get(exposure, exposure),
                window=window,
                odds=fmt(row["odds_ratio_per_10mm"]),
                ci=interval(row["odds_ratio_ci_low"], row["odds_ratio_ci_high"]),
                conc=fmt(row["within_stratum_concordance"]),
            )
        )

    lines += [
        "",
        "## Table 4. Resampled validation",
        "",
        "| Scheme | Exposure | Window | Folds | Median AUC | AUC range | SD | Threshold range (mm) |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    # The per-fold CSV is the raw material; the fold summaries live in the report.
    for key, summary in report["resampled_validation"].items():
        scheme, _, exposure = key.partition(":")
        lines.append(
            "| {scheme} | {exposure} | {window} | {folds} | {median} | {rng} | {sd} | {thr} |".format(
                scheme=scheme.replace("_", " "),
                exposure=exposure_label.get(exposure, exposure),
                window=int(summary["window_days"]),
                folds=int(summary["folds"]),
                median=fmt(summary["auc_median"]),
                rng=interval(summary["auc_min"], summary["auc_max"]),
                sd=fmt(summary["auc_sd"]),
                thr=interval(summary["threshold_min_mm"], summary["threshold_max_mm"], 1),
            )
        )
    assert resampled, "per-fold resampled validation rows must exist"

    lines += [
        "",
        "## Table 5. Sensitivity analyses",
        "",
        "| Variant | Exposure | Window | Threshold (mm) | Test cases | Test controls "
        "| Development AUC | Test AUC | Sensitivity | Specificity |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in sensitivity:
        lines.append(
            "| `{variant}` | {exposure} | {window} | {thr} | {cases} | {controls} "
            "| {dev} | {test} | {sens} | {spec} |".format(
                variant=row["variant"],
                exposure=exposure_label.get(row["exposure"], row["exposure"]),
                window=int(float(row["selected_window_days"])),
                thr=mm(row["threshold_mm"]),
                cases=row["test_cases"],
                controls=row["test_controls"],
                dev=fmt(row["development_auc"]),
                test=fmt(row["test_auc"]),
                sens=fmt(row["test_sensitivity"]),
                spec=fmt(row["test_specificity"]),
            )
        )

    lines += [
        "",
        "## Table 6. Season stratification",
        "",
        "| Season | Exposure | Window | Threshold (mm) | Development AUC | Test AUC "
        "| Sensitivity | Specificity |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in seasons:
        window = int(float(row["window_days"]))
        exposure = row["exposure"]
        if (exposure == CONCURRENT and window != selected_concurrent) or (
            exposure == ANTECEDENT and window != selected_antecedent
        ):
            continue
        lines.append(
            "| {season} | {exposure} | {window} | {thr} | {dev} | {test} | {sens} | {spec} |".format(
                season=row["season"].replace("_", " "),
                exposure=exposure_label.get(exposure, exposure),
                window=window,
                thr=mm(row["threshold_mm"]),
                dev=fmt(row["development_auc"]),
                test=fmt(row["test_auc"]),
                sens=fmt(row["test_sensitivity"]),
                spec=fmt(row["test_specificity"]),
            )
        )

    diagnostics = report["matching_diagnostics"]
    inventory = report["inventory_descriptive"]
    lines += [
        "",
        "## Table 7. Design and matching diagnostics",
        "",
        "| Quantity | Value |",
        "|---|---:|",
        f"| Canonical event records read | {report.get('canonical_events_read')} |",
        f"| Distinct district-days in the inventory | {inventory.get('distinct_district_days_in_inventory')} |",
        f"| Records sharing a district-day | {inventory.get('events_sharing_a_district_day')} |",
        f"| Districts with at least one event | {inventory.get('districts_with_events')} |",
        f"| Monsoon share of events | {fmt(inventory.get('monsoon_event_share'))} |",
        f"| Primary events before the rainfall join | {report.get('primary_events_before_rainfall_join')} |",
        f"| Excluded: event after the rainfall record ends | {report.get('primary_events_after_available_rainfall_end')} |",
        f"| Rainfall record ends | {report.get('available_rainfall_end')} |",
        f"| Matched sets (case-days) | {concurrent_test['n_cases'] + primary[CONCURRENT]['development']['n_cases']} |",
        f"| Control rows | {diagnostics.get('control_rows')} |",
        f"| Cases with no eligible control | {diagnostics.get('strata_without_controls')} "
        f"({fmt(diagnostics.get('strata_without_controls_fraction'))}) |",
        f"| Duplicate control rows | {fmt(diagnostics.get('duplicate_control_row_fraction'))} |",
        f"| Maximum reuse of one control district-day | {diagnostics.get('max_control_reuse')} |",
    ]

    out_path = ROOT / args.out
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {out_path.relative_to(ROOT)} ({len(lines)} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
