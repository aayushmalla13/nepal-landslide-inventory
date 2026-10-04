#!/usr/bin/env python3
"""Validate and score the locked v0.8 fresh probability sample."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "outputs"
MANIFEST = OUTPUT / "v08_fresh_validation_manifest.json"
TEMPLATE = OUTPUT / "v08_fresh_validation_LABEL_HERE.csv"
WEIGHTS = OUTPUT / "v08_fresh_validation_weights.csv"
DEFAULT_COMPLETED = OUTPUT / "v08_fresh_validation_COMPLETED.csv"
JSON_OUTPUT = OUTPUT / "v08_fresh_validation_score.json"
REPORT_OUTPUT = OUTPUT / "v08_fresh_validation_report.md"

FROZEN_COLUMNS = (
    "row_id",
    "event_id",
    "claimed_event_date",
    "claimed_district",
    "claimed_municipality",
    "claimed_event_type",
    "claimed_hazard_type",
    "claimed_deaths",
    "claimed_missing",
    "claimed_injured",
    "cluster_article_count",
    "representative_title",
    "representative_url",
)
YES_NO_UNCLEAR = {"yes", "no", "unclear"}
EVENT_TYPES = {"landslide", "road_obstruction", "other", "unclear"}
HAZARD_TYPES = {"landslide", "debris_flow", "rockfall", "other", "unclear"}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_completed(completed: list[dict[str, str]], template: list[dict[str, str]]) -> None:
    if len(completed) != len(template):
        raise ValueError(f"Expected {len(template)} rows, found {len(completed)}")
    if [row["row_id"] for row in completed] != [row["row_id"] for row in template]:
        raise ValueError("Completed row IDs or order differ from the locked template")
    for row, blank in zip(completed, template, strict=True):
        for column in FROZEN_COLUMNS:
            if row.get(column, "") != blank.get(column, ""):
                raise ValueError(f"{row['row_id']}: frozen column {column} changed")
        event = row.get("event_really_happened", "").strip().lower()
        if event not in YES_NO_UNCLEAR:
            raise ValueError(f"{row['row_id']}: invalid event_really_happened")
        if not row.get("annotator", "").strip():
            raise ValueError(f"{row['row_id']}: annotator is blank")
        if event != "yes":
            continue
        for field in ("one_physical_event", "district_correct", "date_correct"):
            if row.get(field, "").strip().lower() not in YES_NO_UNCLEAR:
                raise ValueError(f"{row['row_id']}: invalid or blank {field}")
        if blank["claimed_municipality"]:
            if row.get("municipality_correct", "").strip().lower() not in YES_NO_UNCLEAR:
                raise ValueError(f"{row['row_id']}: invalid or blank municipality_correct")
        if row.get("event_type_true", "").strip().lower() not in EVENT_TYPES:
            raise ValueError(f"{row['row_id']}: invalid event_type_true")
        if row.get("hazard_type_true", "").strip().lower() not in HAZARD_TYPES:
            raise ValueError(f"{row['row_id']}: invalid hazard_type_true")
        deaths = row.get("deaths_true", "").strip().lower()
        if deaths not in {"not_reported", "unclear"}:
            try:
                if int(deaths) < 0:
                    raise ValueError
            except ValueError as error:
                raise ValueError(f"{row['row_id']}: invalid deaths_true") from error
        duplicate = row.get("duplicate_merge_correct", "").strip().lower()
        if int(blank["cluster_article_count"]) > 1 and duplicate not in YES_NO_UNCLEAR:
            raise ValueError(f"{row['row_id']}: duplicate_merge_correct is required")
        if int(blank["cluster_article_count"]) == 1 and duplicate not in {"", "not_applicable"}:
            raise ValueError(f"{row['row_id']}: invalid one-article duplicate label")


def binary_label(value: str) -> float | None:
    normalized = value.strip().lower()
    if normalized == "yes":
        return 1.0
    if normalized == "no":
        return 0.0
    return None


def categorical_correct(row: dict[str, str], truth: str, claim: str) -> float | None:
    value = row[truth].strip().lower()
    return None if value in {"", "unclear"} else float(value == row[claim].strip().lower())


def deaths_correct(row: dict[str, str]) -> float | None:
    true = row["deaths_true"].strip().lower()
    if true in {"", "unclear"}:
        return None
    claimed = row["claimed_deaths"].strip()
    if true == "not_reported":
        return float(not claimed)
    return float(bool(claimed) and int(claimed) == int(true))


def usable_record(row: dict[str, str]) -> float | None:
    event = row["event_really_happened"].strip().lower()
    if event == "no":
        return 0.0
    if event != "yes":
        return None
    values = [
        row[field].strip().lower()
        for field in ("one_physical_event", "district_correct", "date_correct")
    ]
    if "no" in values:
        return 0.0
    return 1.0 if all(value == "yes" for value in values) else None


def weighted_estimate(
    rows: list[dict[str, str]], getter: Callable[[dict[str, str]], float | None]
) -> tuple[float | None, float, int, int]:
    numerator = denominator = 0.0
    decisive = unclear = 0
    for row in rows:
        value = getter(row)
        if value is None:
            unclear += 1
            continue
        weight = float(row["sampling_weight"])
        numerator += weight * value
        denominator += weight
        decisive += 1
    return (numerator / denominator if denominator else None, denominator, decisive, unclear)


def bootstrap_ci(
    rows: list[dict[str, str]],
    getter: Callable[[dict[str, str]], float | None],
    *,
    seed: int,
    draws: int = 4000,
) -> list[float] | None:
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[row["stratum"]].append(row)
    rng = random.Random(seed)
    estimates: list[float] = []
    for _ in range(draws):
        sample = [rng.choice(group) for group in groups.values() for _ in group]
        estimate, _weight, _decisive, _unclear = weighted_estimate(sample, getter)
        if estimate is not None:
            estimates.append(estimate)
    if not estimates:
        return None
    estimates.sort()
    return [
        estimates[int(0.025 * (len(estimates) - 1))],
        estimates[int(0.975 * (len(estimates) - 1))],
    ]


def metric(
    rows: list[dict[str, str]], getter: Callable[[dict[str, str]], float | None], seed: int
) -> dict[str, Any]:
    estimate, represented_weight, decisive, unclear = weighted_estimate(rows, getter)
    return {
        "estimate": estimate,
        "ci95_stratified_bootstrap": bootstrap_ci(rows, getter, seed=seed),
        "decisive_sample_n": decisive,
        "unclear_or_not_applicable_n": unclear,
        "represented_population_weight": represented_weight,
    }


def calculate_metrics(rows: list[dict[str, str]]) -> dict[str, Any]:
    real = [row for row in rows if row["event_really_happened"].strip().lower() == "yes"]
    multi = [row for row in real if int(row["cluster_article_count"]) > 1]
    definitions = (
        ("event_existence_precision", rows, lambda row: binary_label(row["event_really_happened"])),
        ("usable_record_precision", rows, usable_record),
        ("single_event_accuracy", real, lambda row: binary_label(row["one_physical_event"])),
        ("district_accuracy", real, lambda row: binary_label(row["district_correct"])),
        ("date_accuracy", real, lambda row: binary_label(row["date_correct"])),
        (
            "municipality_accuracy",
            [row for row in real if row["claimed_municipality"].strip()],
            lambda row: binary_label(row["municipality_correct"]),
        ),
        (
            "event_type_accuracy",
            real,
            lambda row: categorical_correct(row, "event_type_true", "claimed_event_type"),
        ),
        (
            "hazard_type_accuracy",
            real,
            lambda row: categorical_correct(row, "hazard_type_true", "claimed_hazard_type"),
        ),
        ("deaths_exact_accuracy", real, deaths_correct),
        (
            "duplicate_merge_accuracy",
            multi,
            lambda row: binary_label(row["duplicate_merge_correct"]),
        ),
    )
    return {
        name: metric(subset, getter, 20260923 + index)
        for index, (name, subset, getter) in enumerate(definitions)
    }


def apply_promotion_rule(
    metrics: dict[str, Any], rule: dict[str, Any], sample_rows: int
) -> dict[str, Any]:
    checks: dict[str, dict[str, Any]] = {}
    for name in (
        "event_existence_precision",
        "usable_record_precision",
        "single_event_accuracy",
        "district_accuracy",
        "date_accuracy",
    ):
        values = metrics[name]
        threshold = rule[name]
        interval = values["ci95_stratified_bootstrap"]
        passed = (
            values["estimate"] is not None
            and interval is not None
            and values["estimate"] >= threshold["minimum_estimate"]
            and interval[0] >= threshold["minimum_ci95_lower"]
        )
        checks[name] = {"passed": passed, **threshold}
    unclear_fraction = (
        metrics["event_existence_precision"]["unclear_or_not_applicable_n"] / sample_rows
    )
    checks["event_existence_unclear_fraction"] = {
        "passed": unclear_fraction <= rule["maximum_event_existence_unclear_fraction"],
        "observed": unclear_fraction,
        "maximum": rule["maximum_event_existence_unclear_fraction"],
    }
    return {"passed": all(check["passed"] for check in checks.values()), "checks": checks}


def render_report(result: dict[str, Any]) -> str:
    decision = "promote" if result["promotion_decision"]["passed"] else "retain candidate status"
    lines = [
        "# v0.8 fresh locked validation",
        "",
        f"**Decision:** {decision}",
        "",
        f"**Candidate:** `{result['inventory_release']}`",
        "",
        "## Results",
        "",
        "| Metric | Weighted estimate | 95% CI | Decisive n | Unclear / N.A. |",
        "|---|---:|---:|---:|---:|",
    ]
    for name, values in result["metrics"].items():
        estimate = values["estimate"]
        interval = values["ci95_stratified_bootstrap"]
        estimate_text = "N.A." if estimate is None else f"{estimate:.3f}"
        interval_text = "N.A." if interval is None else f"{interval[0]:.3f}-{interval[1]:.3f}"
        decisive = values["decisive_sample_n"]
        unclear = values["unclear_or_not_applicable_n"]
        lines.append(
            f"| {name.replace('_', ' ')} | {estimate_text} | {interval_text} | "
            f"{decisive} | {unclear} |"
        )
    lines.extend(["", "## Prespecified decision checks", "", "| Check | Pass |", "|---|---:|"])
    for name, check in result["promotion_decision"]["checks"].items():
        lines.append(f"| {name.replace('_', ' ')} | {'yes' if check['passed'] else 'no'} |")
    lines.extend(
        [
            "",
            "The decision rule and thresholds were frozen in the draw manifest "
            "before labels existed.",
            "Estimates apply to the eligible frame after excluding all previously "
            "reviewed events and article evidence.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--completed", type=Path, default=DEFAULT_COMPLETED)
    parser.add_argument("--json-output", type=Path, default=JSON_OUTPUT)
    parser.add_argument("--report-output", type=Path, default=REPORT_OUTPUT)
    args = parser.parse_args()

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for name, expected in manifest["outputs"].items():
        if sha256(OUTPUT / name) != expected:
            raise ValueError(f"Locked audit artifact changed: {name}")
    completed = read_csv(args.completed)
    validate_completed(completed, read_csv(TEMPLATE))
    weights = {row["row_id"]: row for row in read_csv(WEIGHTS)}
    if set(weights) != {row["row_id"] for row in completed}:
        raise ValueError("Weight rows do not match completed audit rows")
    weighted = [{**row, **weights[row["row_id"]]} for row in completed]
    metrics = calculate_metrics(weighted)
    decision = apply_promotion_rule(
        metrics, manifest["promotion_rule_prespecified"], len(completed)
    )
    result = {
        "audit": manifest["audit"],
        "inventory_release": manifest["inventory_release"],
        "sample_rows": len(completed),
        "eligible_frame_rows": manifest["eligible_frame_rows"],
        "annotators": sorted({row["annotator"].strip() for row in completed}),
        "metrics": metrics,
        "promotion_rule_prespecified": manifest["promotion_rule_prespecified"],
        "promotion_decision": decision,
        "input_sha256": {
            MANIFEST.name: sha256(MANIFEST),
            args.completed.name: sha256(args.completed),
        },
    }
    args.json_output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    args.report_output.write_text(render_report(result), encoding="utf-8")
    print(f"Decision: {'promote' if decision['passed'] else 'retain candidate status'}")
    print(f"Wrote {args.json_output}")
    print(f"Wrote {args.report_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
