#!/usr/bin/env python3
"""Build the paper-facing inventory and validation summary from frozen v1.5."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RELEASE_ID = "nepal_landslide_inventory_v1.5.0_event_detection_validated_20261004"
EXPECTED_CANONICAL_SHA256 = (
    "313745c27218be7989764cc9614b71cc69a9549ff05c483247a6c89bd276ae19"
)

METRIC_LABELS = {
    "event_existence_precision": "Event-existence precision",
    "usable_record_precision": "Usable-record precision",
    "single_event_accuracy": "Single-event accuracy",
    "district_accuracy": "District accuracy",
    "date_accuracy": "Exact-date accuracy",
    "municipality_accuracy": "Municipality accuracy",
    "event_type_accuracy": "Event-type accuracy",
    "hazard_type_accuracy": "Hazard-type accuracy",
    "deaths_exact_accuracy": "Deaths exact accuracy",
    "duplicate_merge_accuracy": "Duplicate-merge accuracy",
}


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def inventory_profile(rows: list[dict[str, str]]) -> dict[str, object]:
    dates = [date.fromisoformat(row["event_date_ad"]) for row in rows]
    years = Counter(value.year for value in dates)
    months = Counter(value.month for value in dates)
    districts = Counter(row["district"] for row in rows)
    sources = Counter(row["representative_source"] for row in rows)
    event_types = Counter(row["event_type"] or "blank" for row in rows)
    hazard_types = Counter(row["hazard_type"] or "blank" for row in rows)
    granularities = Counter(row["event_granularity"] or "blank" for row in rows)
    cluster_sizes = [int(row["cluster_size"] or 0) for row in rows]
    total = len(rows)
    top_three_sources = sum(count for _, count in sources.most_common(3))
    monsoon = sum(months[month] for month in (6, 7, 8, 9))
    return {
        "events": total,
        "date_min": min(dates).isoformat(),
        "date_max": max(dates).isoformat(),
        "districts_represented": len(districts),
        "representative_sources": len(sources),
        "multi_article_clusters": sum(size > 1 for size in cluster_sizes),
        "multi_article_cluster_share": sum(size > 1 for size in cluster_sizes) / total,
        "monsoon_events_jun_sep": monsoon,
        "monsoon_share_jun_sep": monsoon / total,
        "top_three_source_share": top_three_sources / total,
        "years": dict(sorted(years.items())),
        "months": dict(sorted(months.items())),
        "district_counts": dict(districts.most_common()),
        "source_counts": dict(sources.most_common()),
        "event_type_counts": dict(event_types.most_common()),
        "hazard_type_counts": dict(hazard_types.most_common()),
        "event_granularity_counts": dict(granularities.most_common()),
    }


def metric_result(name: str, score: dict[str, object]) -> str:
    checks = score["promotion_decision"]["checks"]
    if name in checks:
        return "pass" if checks[name]["passed"] else "fail"
    return "descriptive"


def render_summary(
    manifest: dict[str, object],
    score: dict[str, object],
    profile: dict[str, object],
) -> str:
    lines = [
        "# v1.5 paper summary",
        "",
        "**Generated file - do not edit by hand.** Rebuild with",
        "`PYTHONPATH=src python3 scripts/build_v15_paper_summary.py`.",
        "",
        "## Authoritative dataset",
        "",
        f"- Release: `{manifest['release_id']}`",
        f"- Status: `{manifest['status']}`",
        f"- Canonical SHA-256: `{manifest['canonical_summary']['sha256']}`",
        f"- Events: {profile['events']:,}",
        f"- Study period: {profile['date_min']} to {profile['date_max']}",
        f"- Districts represented: {profile['districts_represented']} of 77",
        f"- Representative sources: {profile['representative_sources']}",
        "",
        "## Locked validation",
        "",
        "The fresh audit used 150 rows drawn from a 568-event eligible frame with",
        "stratified probability weights. Confidence intervals are stratified-bootstrap",
        "95% intervals. The audit validates event detection, not the complete record.",
        "",
        "| Metric | Estimate | 95% CI | Decision |",
        "|---|---:|---:|---|",
    ]
    for name, label in METRIC_LABELS.items():
        metric = score["metrics"][name]
        low, high = metric["ci95_stratified_bootstrap"]
        lines.append(
            f"| {label} | {metric['estimate']:.3f} | {low:.3f}-{high:.3f} | "
            f"{metric_result(name, score)} |"
        )

    lines += [
        "",
        "## Inventory composition",
        "",
        f"June-September contains {profile['monsoon_events_jun_sep']:,} events "
        f"({profile['monsoon_share_jun_sep']:.1%}). The three largest representative",
        f"sources account for {profile['top_three_source_share']:.1%} of records. These",
        "figures describe the media-derived inventory and must not be interpreted as",
        "population incidence without accounting for reporting intensity.",
        "",
        "### Events by year",
        "",
        "| Year | Events |",
        "|---:|---:|",
    ]
    for year, count in profile["years"].items():
        lines.append(f"| {year} | {count:,} |")

    lines += [
        "",
        "### Events by representative source",
        "",
        "| Source | Events | Share |",
        "|---|---:|---:|",
    ]
    for source, count in profile["source_counts"].items():
        lines.append(f"| {source} | {count:,} | {count / profile['events']:.1%} |")

    lines += [
        "",
        "## Claim boundary",
        "",
        "Supported primary claim: a validated high-precision web-derived landslide",
        "event-detection inventory for Nepal. District assignment also passed its",
        "prespecified threshold.",
        "",
        "Not supported: a complete census, a high-precision full-record inventory,",
        "or exact-date accuracy sufficient for unqualified daily causal analysis.",
        "Usable-record precision, single-event accuracy, and exact-date accuracy failed",
        "their prespecified thresholds.",
        "",
        "## Downstream-analysis status",
        "",
        "- BIPAD comparison: complete in `nepal_landslide_external_validation_v0.2.0_20261004`.",
        "- Rainfall analysis: complete in `nepal_landslide_rainfall_v1.0.0_20261004`.",
        "- Existing v0.4 manuscript files are historical and must not supply headline counts.",
        "- Date-dependent analysis must include high-confidence and date-window sensitivity checks.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--release",
        default=f"data/releases/{RELEASE_ID}",
        help="event-detection-validated release directory",
    )
    parser.add_argument("--summary", default="docs/V15_PAPER_SUMMARY.md")
    parser.add_argument("--profile", default="data/outputs/v15_inventory_profile.json")
    args = parser.parse_args()

    release = ROOT / args.release
    manifest = json.loads((release / "release_manifest.json").read_text(encoding="utf-8"))
    if manifest["status"] != "validated_event_detection_only":
        raise ValueError("release is not event-detection validated")
    if manifest["canonical_summary"]["sha256"] != EXPECTED_CANONICAL_SHA256:
        raise ValueError("canonical hash does not match frozen v1.5")

    score = json.loads(
        (release / "validation" / "v15_final_validation_score.json").read_text(
            encoding="utf-8"
        )
    )
    rows = read_rows(release / "canonical_events_final.csv")
    profile = inventory_profile(rows)
    if profile["events"] != manifest["canonical_summary"]["rows"]:
        raise ValueError("canonical row count does not match release manifest")

    summary_path = ROOT / args.summary
    profile_path = ROOT / args.profile
    summary_path.write_text(render_summary(manifest, score, profile) + "\n", encoding="utf-8")
    profile_path.write_text(json.dumps(profile, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(summary_path.relative_to(ROOT))
    print(profile_path.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
