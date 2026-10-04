#!/usr/bin/env python3
"""Generate the v1.5 rainfall manuscript core from frozen analysis outputs."""

from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INVENTORY_RELEASE = (
    ROOT
    / "data/releases/nepal_landslide_inventory_v1.5.0_event_detection_validated_20261004"
)
EXTERNAL_RELEASE = ROOT / "data/releases/nepal_landslide_external_validation_v0.2.0_20261004"
OUTPUT = ROOT / "docs/RAINFALL_MANUSCRIPT_DRAFT_V15.md"

CONCURRENT = "concurrent_incl_event_day"
ANTECEDENT = "strictly_antecedent_excl_event_day"


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def sensitivity_rows(rows: list[dict[str, str]], exposure: str) -> list[dict[str, str]]:
    wanted = {
        "primary_conf_ge_0.78",
        "high_conf_ge_0.80",
        "very_high_conf_ge_0.90",
        "primary_date_minus_1d",
        "primary_date_plus_1d",
        "primary_date_minus_3d",
        "primary_date_plus_3d",
    }
    return [row for row in rows if row["variant"] in wanted and row["exposure"] == exposure]


def render() -> str:
    inventory_manifest = read_json(INVENTORY_RELEASE / "release_manifest.json")
    validation = read_json(
        INVENTORY_RELEASE / "validation/v15_final_validation_score.json"
    )
    rainfall = read_json(ROOT / "data/outputs/rainfall_analysis_report.json")
    external = read_json(EXTERNAL_RELEASE / "external_agreement.json")
    integrity = read_json(ROOT / "data/outputs/rainfall_case_integrity_audit.json")
    integrity_sensitivity = read_json(
        ROOT / "data/outputs/rainfall_integrity_sensitivity.json"
    )
    sensitivities = read_csv(ROOT / "data/outputs/rainfall_sensitivity_summary.csv")

    canonical = inventory_manifest["canonical_summary"]
    event_metric = validation["metrics"]["event_existence_precision"]
    district_metric = validation["metrics"]["district_accuracy"]
    date_metric = validation["metrics"]["date_accuracy"]
    concurrent = rainfall["primary_selected_by_exposure"][CONCURRENT]
    antecedent = rainfall["primary_selected_by_exposure"][ANTECEDENT]
    dev = concurrent["development"]
    test = concurrent["temporal_test"]
    ant_dev = antecedent["development"]
    ant_test = antecedent["temporal_test"]
    loo = rainfall["resampled_validation"][f"leave_one_year_out:{CONCURRENT}"]
    external_a = external["layer3_chance_corrected"]["tier_A"]
    aggregate = external["layer5_aggregate"]
    primary_integrity = integrity_sensitivity["baseline_full_case_set"]
    clean_integrity = integrity_sensitivity["without_violations_and_contamination"]

    lines = [
        "# Media-reported landslide occurrence and antecedent rainfall in Nepal: a validated event-detection inventory and district-day analysis, 2015-2026",
        "",
        "**Generated manuscript core - do not edit numeric results by hand.** Rebuild with",
        "`PYTHONPATH=src python3 scripts/build_v15_rainfall_manuscript.py`.",
        "",
        "**Authors:** [complete before submission]",
        "",
        "**Analysis version:** 1.0.0 (2026-10-04). Inventory release",
        f"`{inventory_manifest['release_id']}`; rainfall release",
        "`nepal_landslide_rainfall_v1.0.0_20261004`.",
        "",
        "## Abstract",
        "",
        f"We assembled {canonical['rows']:,} media-derived landslide event records across",
        f"{canonical['districts']} Nepal districts from {canonical['date_min']} to",
        f"{canonical['date_max']}. A fresh 150-row stratified probability audit estimated",
        f"event-existence precision at {event_metric['estimate']:.3f} (95% CI",
        f"{event_metric['ci95_stratified_bootstrap'][0]:.3f}-",
        f"{event_metric['ci95_stratified_bootstrap'][1]:.3f}) and district accuracy at",
        f"{district_metric['estimate']:.3f}; exact-date accuracy was",
        f"{date_metric['estimate']:.3f}, requiring explicit temporal sensitivity analysis.",
        f"We linked {rainfall['variants']['primary_conf_ge_0.78']['cases']:,} district-day",
        f"cases to {rainfall['variants']['primary_conf_ge_0.78']['controls']:,} controls",
        "matched on district, calendar month, and year. Windows and thresholds were",
        "selected through 2022 and tested without retuning from 2023 onward.",
        f"The primary concurrent analysis selected R{int(dev['window_days'])} at",
        f"{dev['threshold_mm']:.1f} mm and achieved test AUC {test['auc']:.3f}",
        f"(95% CI {test['auc_ci_low']:.3f}-{test['auc_ci_high']:.3f}), sensitivity",
        f"{test['sensitivity']:.3f}, and specificity {test['specificity']:.3f}.",
        f"The strictly antecedent co-primary selected R{int(ant_dev['window_days'])} at",
        f"{ant_dev['threshold_mm']:.1f} mm with test AUC {ant_test['auc']:.3f}.",
        f"Leave-one-year-out AUC had median {loo['auc_median']:.3f} and range",
        f"{loo['auc_min']:.3f}-{loo['auc_max']:.3f}. The threshold changed under deliberate",
        "date shifts, so it is an empirical association measure rather than an",
        "operational warning threshold. Independent BIPAD comparison showed Tier-A",
        f"overlap {external_a['observed_overlap']:.3f} versus",
        f"{external_a['expected_by_chance']:.3f} expected by date permutation",
        f"(chance-corrected {external_a['chance_corrected']:.3f},",
        f"empirical p={external_a['empirical_p']:.4f}).",
        "",
        "**Keywords:** landslide inventory; media mining; Nepal; CHIRPS; antecedent rainfall; matched case-control; external agreement",
        "",
        "## 1. Study design",
        "",
        "The inventory is a source-bounded record of media-detected events, not a complete",
        "census. The primary unit for rainfall analysis is the district-day. Multiple",
        "records in the same district on the same date are collapsed to one case-day.",
        "Controls are sampled in the same district, calendar month, and year and must be",
        "at least seven days from any reported event. Five controls are requested per case.",
        "Concurrent rainfall windows include the reported event day; strictly antecedent",
        "windows end the day before it. Development ends on 2022-12-31.",
        "",
        "## 2. Inventory validation",
        "",
        "| Metric | Estimate | 95% CI | Prespecified decision |",
        "|---|---:|---:|---|",
    ]
    checks = validation["promotion_decision"]["checks"]
    for key, label in (
        ("event_existence_precision", "Event-existence precision"),
        ("usable_record_precision", "Usable-record precision"),
        ("single_event_accuracy", "Single-event accuracy"),
        ("district_accuracy", "District accuracy"),
        ("date_accuracy", "Exact-date accuracy"),
    ):
        metric = validation["metrics"][key]
        low, high = metric["ci95_stratified_bootstrap"]
        result = "pass" if checks[key]["passed"] else "fail"
        lines.append(
            f"| {label} | {metric['estimate']:.3f} | {low:.3f}-{high:.3f} | {result} |"
        )

    lines += [
        "",
        "The validated claim is therefore high-precision event detection. The data do",
        "not support an unqualified high-precision full-record or exact-date claim.",
        "",
        "## 3. Rainfall results",
        "",
        f"The primary development sample contained {dev['n_cases']:,} case-days and "
        f"{dev['n_controls']:,} matched controls. The temporal test set contained "
        f"{test['n_cases']:,} case-days and {test['n_controls']:,} controls. The "
        f"development-selected {dev['threshold_mm']:.1f} mm threshold was carried "
        f"forward unchanged. Test AUC was {test['auc']:.3f}.",
        "",
        "| Exposure | Window | Development threshold (95% CI), mm | Test AUC (95% CI) | Sensitivity | Specificity |",
        "|---|---:|---:|---:|---:|---:|",
        f"| Concurrent, includes event day | R{int(dev['window_days'])} | {dev['threshold_mm']:.1f} ({dev['threshold_ci_low']:.1f}-{dev['threshold_ci_high']:.1f}) | {test['auc']:.3f} ({test['auc_ci_low']:.3f}-{test['auc_ci_high']:.3f}) | {test['sensitivity']:.3f} | {test['specificity']:.3f} |",
        f"| Strictly antecedent | R{int(ant_dev['window_days'])} | {ant_dev['threshold_mm']:.1f} ({ant_dev['threshold_ci_low']:.1f}-{ant_dev['threshold_ci_high']:.1f}) | {ant_test['auc']:.3f} ({ant_test['auc_ci_low']:.3f}-{ant_test['auc_ci_high']:.3f}) | {ant_test['sensitivity']:.3f} | {ant_test['specificity']:.3f} |",
        "",
        f"The primary matched-set conditional model gave an odds ratio of {next(row['odds_ratio_per_10mm'] for row in rainfall['conditional_models'] if row['split'] == 'all_years' and row['exposure'] == CONCURRENT and int(row['window_days']) == int(dev['window_days'])):.3f} per 10 mm.",
        f"There were {rainfall['matching_diagnostics']['strata_without_controls']} cases",
        f"without an eligible control ({rainfall['matching_diagnostics']['strata_without_controls_fraction']:.1%})",
        f"and {rainfall['matching_diagnostics']['duplicate_control_row_fraction']:.1%} of control rows",
        "repeated a district-day; the strict matched-set variant is reported separately.",
        "",
        "## 4. Date sensitivity",
        "",
        "| Variant | Window | Threshold (mm) | Test AUC | Sensitivity | Specificity |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in sensitivity_rows(sensitivities, CONCURRENT):
        lines.append(
            f"| `{row['variant']}` | R{int(float(row['selected_window_days']))} | "
            f"{float(row['threshold_mm']):.1f} | {float(row['test_auc']):.3f} | "
            f"{float(row['test_sensitivity']):.3f} | {float(row['test_specificity']):.3f} |"
        )
    if rainfall["variants"]["very_high_conf_ge_0.90"]["cases"] < 30:
        lines += [
            "",
            f"The confidence >=0.90 variant contained only {rainfall['variants']['very_high_conf_ge_0.90']['cases']} cases and was too sparse for a stable temporal estimate.",
        ]

    lines += [
        "",
        "## 5. Integrity and external agreement",
        "",
        f"The refreshed integrity audit examined {integrity['case_days_examined']:,} case-days",
        f"and found {integrity['flagged_case_days_violations_only']} logically impossible rows.",
        f"Only {integrity['excludable_case_days']} case-days ({integrity['excludable_case_days_pct']:.2f}%)",
        "were potentially excludable contamination. Removing them changed the R3 AUC by",
        f"{clean_integrity['r3']['auc'] - primary_integrity['r3']['auc']:+.4f} and the",
        f"cutpoint by {clean_integrity['r3']['cutpoint_mm'] - primary_integrity['r3']['cutpoint_mm']:+.1f} mm.",
        "",
        f"The common BIPAD comparison contained {external['layer2_overlap']['news_total']:,}",
        f"news events and {external['layer2_overlap']['bipad_total']:,} harmonized BIPAD clusters.",
        f"District-year counts correlated at rho={aggregate['district_year']['spearman_rho']:.3f},",
        f"whereas district-month counts correlated at rho={aggregate['district_month']['spearman_rho']:.3f}.",
        "BIPAD is incomplete and not ground truth; these are agreement measures, not",
        "precision or recall.",
        "",
        "## 6. Limitations and defensible claims",
        "",
        "The inventory is affected by publisher turnover, geographic and severity-related",
        "reporting bias, and imperfect exact dates and event granularity. June-September",
        "accounts for 81.1% of records, and the three largest publishers account for 47.0%.",
        "Daily associations are sensitive to date displacement, and district-mean CHIRPS",
        "smooths localized rainfall extremes. Absolute risk, calibration, completeness,",
        "and operational warning performance are not identifiable from this design.",
        "",
        "The paper may claim a validated high-precision web-derived event-detection",
        "inventory and a reproducible association between reported district-days and",
        "antecedent rainfall. It must not claim a complete landslide census, validated",
        "full-record precision, exact daily timing, or an operational warning threshold.",
        "",
        "## Data and code availability",
        "",
        f"Canonical inventory: `{inventory_manifest['release_id']}` (SHA-256",
        f"`{canonical['sha256']}`). External agreement:",
        "`nepal_landslide_external_validation_v0.2.0_20261004`. Rainfall analysis:",
        "`nepal_landslide_rainfall_v1.0.0_20261004`. Full article text should not be",
        "redistributed; source URLs, derived fields, code, manifests, and checksums are",
        "included for reproducibility.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    OUTPUT.write_text(render() + "\n", encoding="utf-8")
    print(OUTPUT.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
