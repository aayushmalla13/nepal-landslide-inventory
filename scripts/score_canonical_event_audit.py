#!/usr/bin/env python3
"""Validate and score the blind canonical event-level audit."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "outputs"
TEMPLATE = OUTPUT / "canonical_event_audit_LABEL_HERE.csv"
WEIGHTS = OUTPUT / "canonical_event_audit_weights.csv"
MANIFEST = OUTPUT / "canonical_event_audit_manifest.json"
DEFAULT_COMPLETED = OUTPUT / "canonical_event_audit_COMPLETED.csv"
JSON_OUTPUT = OUTPUT / "canonical_event_audit_score.json"
REPORT_OUTPUT = OUTPUT / "canonical_event_audit_report.md"

FROZEN_COLUMNS = (
    "row_id", "event_id", "claimed_event_date", "claimed_district",
    "claimed_municipality", "claimed_event_type", "claimed_hazard_type",
    "claimed_deaths", "claimed_missing", "claimed_injured",
    "cluster_article_count", "representative_title", "representative_url",
)
YES_NO_UNCLEAR = {"yes", "no", "unclear"}
EVENT_TYPES = {"landslide", "road_obstruction", "other", "unclear"}
HAZARD_TYPES = {"landslide", "debris_flow", "rockfall", "other", "unclear"}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate(
    completed: list[dict[str, str]], template: list[dict[str, str]], manifest: dict
) -> None:
    if sha256(TEMPLATE) != manifest["outputs"][TEMPLATE.name]:
        raise ValueError("Blank audit template no longer matches its manifest.")
    if sha256(WEIGHTS) != manifest["outputs"][WEIGHTS.name]:
        raise ValueError("Sampling weights no longer match the audit manifest.")
    if len(completed) != len(template):
        raise ValueError(f"Expected {len(template)} completed rows, found {len(completed)}.")
    if [row["row_id"] for row in completed] != [row["row_id"] for row in template]:
        raise ValueError("Completed row IDs or order differ from the blank audit pack.")
    for row, blank in zip(completed, template, strict=True):
        for column in FROZEN_COLUMNS:
            if row.get(column, "") != blank.get(column, ""):
                raise ValueError(f"{row['row_id']}: frozen column {column} changed.")
        event = row.get("event_really_happened", "").strip().lower()
        if event not in YES_NO_UNCLEAR:
            raise ValueError(f"{row['row_id']}: invalid event_really_happened.")
        if not row.get("annotator", "").strip():
            raise ValueError(f"{row['row_id']}: annotator is blank.")
        if event == "yes":
            for field in ("one_physical_event", "district_correct", "date_correct"):
                if row.get(field, "").strip().lower() not in YES_NO_UNCLEAR:
                    raise ValueError(f"{row['row_id']}: invalid or blank {field}.")
            if blank["claimed_municipality"] and row.get("municipality_correct", "").strip().lower() not in YES_NO_UNCLEAR:
                raise ValueError(f"{row['row_id']}: municipality_correct is required.")
            if row.get("event_type_true", "").strip().lower() not in EVENT_TYPES:
                raise ValueError(f"{row['row_id']}: invalid or blank event_type_true.")
            if row.get("hazard_type_true", "").strip().lower() not in HAZARD_TYPES:
                raise ValueError(f"{row['row_id']}: invalid or blank hazard_type_true.")
            deaths = row.get("deaths_true", "").strip().lower()
            if deaths not in {"unclear", "not_reported"}:
                try:
                    if int(deaths) < 0:
                        raise ValueError
                except ValueError as exc:
                    raise ValueError(f"{row['row_id']}: deaths_true must be a count, not_reported, or unclear.") from exc
            duplicate = row.get("duplicate_merge_correct", "").strip().lower()
            if int(blank["cluster_article_count"]) > 1 and duplicate not in YES_NO_UNCLEAR:
                raise ValueError(f"{row['row_id']}: duplicate_merge_correct is required.")
            if int(blank["cluster_article_count"]) == 1 and duplicate not in {"", "not_applicable"}:
                raise ValueError(f"{row['row_id']}: use not_applicable for a one-article cluster.")


def binary_label(value: str) -> float | None:
    normalized = value.strip().lower()
    if normalized == "yes":
        return 1.0
    if normalized == "no":
        return 0.0
    return None


def event_type_correct(row: dict[str, str]) -> float | None:
    true = row["event_type_true"].strip().lower()
    return None if true in {"", "unclear"} else float(true == row["claimed_event_type"])


def hazard_type_correct(row: dict[str, str]) -> float | None:
    true = row["hazard_type_true"].strip().lower()
    return None if true in {"", "unclear"} else float(true == row["claimed_hazard_type"])


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
    required = [
        row["one_physical_event"].strip().lower(),
        row["district_correct"].strip().lower(),
        row["date_correct"].strip().lower(),
    ]
    if "no" in required:
        return 0.0
    return 1.0 if all(value == "yes" for value in required) else None


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


def stratified_bootstrap_ci(
    rows: list[dict[str, str]],
    getter: Callable[[dict[str, str]], float | None],
    *,
    draws: int = 4000,
    seed: int = 20260916,
) -> list[float] | None:
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[row["stratum"]].append(row)
    rng = random.Random(seed)
    estimates: list[float] = []
    for _ in range(draws):
        sample: list[dict[str, str]] = []
        for group in groups.values():
            sample.extend(rng.choice(group) for _ in group)
        estimate, _weight, _decisive, _unclear = weighted_estimate(sample, getter)
        if estimate is not None:
            estimates.append(estimate)
    if not estimates:
        return None
    estimates.sort()
    return [estimates[int(0.025 * (len(estimates) - 1))], estimates[int(0.975 * (len(estimates) - 1))]]


def metric(
    rows: list[dict[str, str]], getter: Callable[[dict[str, str]], float | None], seed: int
) -> dict[str, object]:
    estimate, represented_weight, decisive, unclear = weighted_estimate(rows, getter)
    return {
        "estimate": estimate,
        "ci95_stratified_bootstrap": stratified_bootstrap_ci(rows, getter, seed=seed),
        "decisive_sample_n": decisive,
        "unclear_or_not_applicable_n": unclear,
        "represented_population_weight": represented_weight,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("completed", nargs="?", type=Path, default=DEFAULT_COMPLETED)
    parser.add_argument("--json-output", type=Path, default=JSON_OUTPUT)
    parser.add_argument("--report-output", type=Path, default=REPORT_OUTPUT)
    args = parser.parse_args()
    completed = read_csv(args.completed)
    template = read_csv(TEMPLATE)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    validate(completed, template, manifest)
    weights = {row["row_id"]: row for row in read_csv(WEIGHTS)}
    rows = [{**row, **weights[row["row_id"]]} for row in completed]
    real_rows = [row for row in rows if row["event_really_happened"].strip().lower() == "yes"]
    multi_rows = [row for row in real_rows if int(row["cluster_article_count"]) > 1]

    getters: list[tuple[str, list[dict[str, str]], Callable[[dict[str, str]], float | None]]] = [
        ("event_existence_precision", rows, lambda row: binary_label(row["event_really_happened"])),
        ("usable_record_precision", rows, usable_record),
        ("single_event_accuracy", real_rows, lambda row: binary_label(row["one_physical_event"])),
        ("district_accuracy", real_rows, lambda row: binary_label(row["district_correct"])),
        ("date_accuracy", real_rows, lambda row: binary_label(row["date_correct"])),
        (
            "municipality_accuracy",
            [row for row in real_rows if row["claimed_municipality"].strip()],
            lambda row: binary_label(row["municipality_correct"]),
        ),
        ("event_type_accuracy", real_rows, event_type_correct),
        ("hazard_type_accuracy", real_rows, hazard_type_correct),
        ("deaths_exact_accuracy", real_rows, deaths_correct),
        ("duplicate_merge_accuracy", multi_rows, lambda row: binary_label(row["duplicate_merge_correct"])),
    ]
    metrics = {name: metric(subset, getter, 20260916 + index) for index, (name, subset, getter) in enumerate(getters)}
    result = {
        "audit": manifest["audit"],
        "inventory_release": manifest["inventory_release"],
        "sample_rows": len(rows),
        "annotators": sorted({row["annotator"].strip() for row in rows}),
        "input_sha256": {
            MANIFEST.name: sha256(MANIFEST),
            TEMPLATE.name: sha256(TEMPLATE),
            WEIGHTS.name: sha256(WEIGHTS),
            args.completed.name: sha256(args.completed),
        },
        "metrics": metrics,
        "interpretation": (
            "Estimates are population-weighted for the frozen 2,885-event inventory. "
            "Unclear labels are excluded from point estimates and reported separately."
        ),
    }
    args.json_output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# Canonical event-level audit",
        "",
        f"Inventory: `{manifest['inventory_release']}`",
        f"Reviewed rows: {len(rows)}",
        "",
        "| Metric | Weighted estimate | 95% stratified-bootstrap CI | Decisive n | Unclear / N.A. |",
        "|---|---:|---:|---:|---:|",
    ]
    for name, values in metrics.items():
        estimate = values["estimate"]
        interval = values["ci95_stratified_bootstrap"]
        estimate_text = "N.A." if estimate is None else f"{estimate:.3f}"
        interval_text = "N.A." if interval is None else f"{interval[0]:.3f}-{interval[1]:.3f}"
        lines.append(
            f"| {name.replace('_', ' ')} | {estimate_text} | {interval_text} | "
            f"{values['decisive_sample_n']} | {values['unclear_or_not_applicable_n']} |"
        )
    lines.extend(
        [
            "",
            "Point estimates exclude unclear labels; their counts are shown explicitly.",
            "The audit evaluates the frozen release and does not silently modify it.",
            "",
        ]
    )
    args.report_output.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {args.json_output}")
    print(f"Wrote {args.report_output}")


if __name__ == "__main__":
    main()
