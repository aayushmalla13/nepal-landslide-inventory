#!/usr/bin/env python3
"""Validate and separately score the fresh and correction-challenge samples."""

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
MANIFEST = OUTPUT / "post_correction_validation_manifest.json"
FRESH_TEMPLATE = OUTPUT / "post_correction_fresh_audit_LABEL_HERE.csv"
FRESH_WEIGHTS = OUTPUT / "post_correction_fresh_audit_weights.csv"
FRESH_COMPLETED = OUTPUT / "post_correction_fresh_audit_COMPLETED.csv"
CHALLENGE_TEMPLATE = OUTPUT / "post_correction_challenge_LABEL_HERE.csv"
CHALLENGE_COMPLETED = OUTPUT / "post_correction_challenge_COMPLETED.csv"
CORRECTION_LOG = (
    ROOT
    / "data"
    / "releases"
    / "nepal_landslide_inventory_v0.7.0_candidate_20260916"
    / "correction_application_log.csv"
)
JSON_OUTPUT = OUTPUT / "post_correction_validation_score.json"
REPORT_OUTPUT = OUTPUT / "post_correction_validation_report.md"

FROZEN_COLUMNS = (
    "row_id",
    "sample_role",
    "correction_layer",
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
    "event_evidence",
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


def validate_completed(
    completed: list[dict[str, str]],
    template: list[dict[str, str]],
    *,
    expected_role: str,
) -> None:
    if len(completed) != len(template):
        raise ValueError(f"Expected {len(template)} rows, found {len(completed)}")
    if [row["row_id"] for row in completed] != [row["row_id"] for row in template]:
        raise ValueError("Completed row IDs or order differ from the locked template")
    for row, blank in zip(completed, template, strict=True):
        for column in FROZEN_COLUMNS:
            if row.get(column, "") != blank.get(column, ""):
                raise ValueError(f"{row['row_id']}: frozen column {column} changed")
        if row["sample_role"] != expected_role:
            raise ValueError(f"{row['row_id']}: wrong sample role")
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
        if int(blank["cluster_article_count"]) == 1 and duplicate not in {
            "",
            "not_applicable",
        }:
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
        row["one_physical_event"].strip().lower(),
        row["district_correct"].strip().lower(),
        row["date_correct"].strip().lower(),
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


def stratified_bootstrap_ci(
    rows: list[dict[str, str]],
    getter: Callable[[dict[str, str]], float | None],
    *,
    draws: int = 4000,
    seed: int,
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


def weighted_metric(
    rows: list[dict[str, str]], getter: Callable[[dict[str, str]], float | None], seed: int
) -> dict[str, Any]:
    estimate, represented_weight, decisive, unclear = weighted_estimate(rows, getter)
    return {
        "estimate": estimate,
        "ci95_stratified_bootstrap": stratified_bootstrap_ci(rows, getter, seed=seed),
        "decisive_sample_n": decisive,
        "unclear_or_not_applicable_n": unclear,
        "represented_population_weight": represented_weight,
    }


def unweighted_metric(
    rows: list[dict[str, str]], getter: Callable[[dict[str, str]], float | None]
) -> dict[str, Any]:
    values = [value for row in rows if (value := getter(row)) is not None]
    return {
        "estimate": sum(values) / len(values) if values else None,
        "decisive_sample_n": len(values),
        "unclear_or_not_applicable_n": len(rows) - len(values),
    }


def correction_log_by_event(log_rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    selected: dict[str, dict[str, str]] = {}
    for row in log_rows:
        if row["action"] not in {"add_reconstructed", "merge_into_existing", "correct_attributes"}:
            continue
        if row["event_id"] in selected:
            raise ValueError(f"Multiple scored correction actions for {row['event_id']}")
        selected[row["event_id"]] = row
    return selected


def _combine_checks(values: list[float | None]) -> float | None:
    if any(value == 0.0 for value in values):
        return 0.0
    if any(value is None for value in values):
        return None
    return 1.0


def targeted_correction_pass(row: dict[str, str], action: dict[str, str]) -> float | None:
    event = binary_label(row["event_really_happened"])
    if event != 1.0:
        return event
    if action["action"] == "merge_into_existing":
        return _combine_checks(
            [
                binary_label(row["one_physical_event"]),
                binary_label(row["duplicate_merge_correct"]),
            ]
        )
    if action["action"] == "add_reconstructed":
        values = [
            binary_label(row["one_physical_event"]),
            binary_label(row["district_correct"]),
            binary_label(row["date_correct"]),
            categorical_correct(row, "event_type_true", "claimed_event_type"),
            categorical_correct(row, "hazard_type_true", "claimed_hazard_type"),
            deaths_correct(row),
        ]
        if row["claimed_municipality"].strip():
            values.append(binary_label(row["municipality_correct"]))
        if int(row["cluster_article_count"]) > 1:
            values.append(binary_label(row["duplicate_merge_correct"]))
        return _combine_checks(values)

    field_getters: dict[str, Callable[[dict[str, str]], float | None]] = {
        "event_date": lambda item: binary_label(item["date_correct"]),
        "district": lambda item: binary_label(item["district_correct"]),
        "municipality": lambda item: binary_label(item["municipality_correct"]),
        "event_type": lambda item: categorical_correct(
            item, "event_type_true", "claimed_event_type"
        ),
        "hazard_type": lambda item: categorical_correct(
            item, "hazard_type_true", "claimed_hazard_type"
        ),
        "deaths": deaths_correct,
    }
    fields = json.loads(action["changed_fields_json"])
    return _combine_checks([field_getters[field](row) for field in fields])


def fresh_metrics(rows: list[dict[str, str]]) -> dict[str, Any]:
    real_rows = [row for row in rows if row["event_really_happened"].strip().lower() == "yes"]
    multi_rows = [row for row in real_rows if int(row["cluster_article_count"]) > 1]
    definitions = [
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
        (
            "event_type_accuracy",
            real_rows,
            lambda row: categorical_correct(row, "event_type_true", "claimed_event_type"),
        ),
        (
            "hazard_type_accuracy",
            real_rows,
            lambda row: categorical_correct(row, "hazard_type_true", "claimed_hazard_type"),
        ),
        ("deaths_exact_accuracy", real_rows, deaths_correct),
        (
            "duplicate_merge_accuracy",
            multi_rows,
            lambda row: binary_label(row["duplicate_merge_correct"]),
        ),
    ]
    return {
        name: weighted_metric(subset, getter, 20260920 + index)
        for index, (name, subset, getter) in enumerate(definitions)
    }


def challenge_metrics(
    rows: list[dict[str, str]], actions: dict[str, dict[str, str]]
) -> dict[str, Any]:
    overall = {
        "event_existence": unweighted_metric(
            rows, lambda row: binary_label(row["event_really_happened"])
        ),
        "usable_record": unweighted_metric(rows, usable_record),
        "targeted_correction_pass": unweighted_metric(
            rows, lambda row: targeted_correction_pass(row, actions[row["event_id"]])
        ),
    }
    by_layer: dict[str, Any] = {}
    for layer in sorted({row["correction_layer"] for row in rows}):
        subset = [row for row in rows if row["correction_layer"] == layer]
        by_layer[layer] = unweighted_metric(
            subset, lambda row: targeted_correction_pass(row, actions[row["event_id"]])
        )
    return {"overall": overall, "targeted_pass_by_layer": by_layer}


def render_report(result: dict[str, Any]) -> str:
    lines = [
        "# Post-correction candidate validation",
        "",
        f"Inventory: `{result['inventory_release']}`",
        "",
        "## Fresh probability sample",
        "",
        "| Metric | Weighted estimate | 95% stratified-bootstrap CI | "
        "Decisive n | Unclear / N.A. |",
        "|---|---:|---:|---:|---:|",
    ]
    for name, values in result["fresh_probability_sample"]["metrics"].items():
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
            "## Correction challenge",
            "",
            "| Layer | Targeted pass | Decisive n | Unclear / N.A. |",
            "|---|---:|---:|---:|",
        ]
    )
    challenge = result["correction_challenge"]
    for name, values in challenge["targeted_pass_by_layer"].items():
        estimate = values["estimate"]
        lines.append(
            f"| {name.replace('_', ' ')} | "
            f"{'N.A.' if estimate is None else f'{estimate:.3f}'} | "
            f"{values['decisive_sample_n']} | {values['unclear_or_not_applicable_n']} |"
        )
    overall = challenge["overall"]["targeted_correction_pass"]
    lines.append(
        f"| **overall** | **{overall['estimate']:.3f}** | "
        f"**{overall['decisive_sample_n']}** | **{overall['unclear_or_not_applicable_n']}** |"
    )
    lines.extend(
        [
            "",
            "Fresh estimates apply only to the untouched 2,723-event eligible frame.",
            "The targeted correction challenge is not an overall precision estimate.",
            "No numeric promotion threshold was prespecified; results must not be "
            "judged by a post hoc cutoff.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fresh", type=Path, default=FRESH_COMPLETED)
    parser.add_argument("--challenge", type=Path, default=CHALLENGE_COMPLETED)
    parser.add_argument("--json-output", type=Path, default=JSON_OUTPUT)
    parser.add_argument("--report-output", type=Path, default=REPORT_OUTPUT)
    args = parser.parse_args()

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for name, expected in manifest["outputs"].items():
        if name.endswith("LABEL_HERE.csv") or name.endswith("weights.csv"):
            if sha256(OUTPUT / name) != expected:
                raise ValueError(f"Locked audit artifact changed: {name}")
    fresh = read_csv(args.fresh)
    challenge = read_csv(args.challenge)
    validate_completed(fresh, read_csv(FRESH_TEMPLATE), expected_role="fresh_probability")
    validate_completed(
        challenge, read_csv(CHALLENGE_TEMPLATE), expected_role="correction_challenge"
    )
    weights = {row["row_id"]: row for row in read_csv(FRESH_WEIGHTS)}
    weighted_fresh = [{**row, **weights[row["row_id"]]} for row in fresh]
    actions = correction_log_by_event(read_csv(CORRECTION_LOG))
    if not {row["event_id"] for row in challenge} <= set(actions):
        raise ValueError("Challenge contains an event without a correction action")

    result = {
        "audit": manifest["audit"],
        "inventory_release": manifest["inventory_release"],
        "fresh_probability_sample": {
            "sample_rows": len(fresh),
            "eligible_frame_rows": manifest["fresh_probability_sample"]["eligible_frame_rows"],
            "annotators": sorted({row["annotator"].strip() for row in fresh}),
            "metrics": fresh_metrics(weighted_fresh),
        },
        "correction_challenge": {
            "sample_rows": len(challenge),
            "annotators": sorted({row["annotator"].strip() for row in challenge}),
            **challenge_metrics(challenge, actions),
        },
        "input_sha256": {
            MANIFEST.name: sha256(MANIFEST),
            args.fresh.name: sha256(args.fresh),
            args.challenge.name: sha256(args.challenge),
            CORRECTION_LOG.name: sha256(CORRECTION_LOG),
        },
        "promotion_threshold_prespecified": False,
    }
    args.json_output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    args.report_output.write_text(render_report(result), encoding="utf-8")
    print(f"Wrote {args.json_output}")
    print(f"Wrote {args.report_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
