#!/usr/bin/env python3
"""Measure what the integrity-flagged case-days do to the rainfall threshold.

The audit reports flags; this asks whether they matter. It recomputes the
cutpoint and AUC with the flagged case-days removed and compares against the
same quantities computed on the full set, so the comparison is like-for-like
rather than against a number copied out of the v0.6.0 report.

Two framings, kept separate on purpose:

* **violations only** -- the logically impossible rows (an event dated after its
  own publication). There is no judgement involved in removing these, so this
  is the conservative floor of the effect.
* **violations + contamination** -- adds the articles that are not event reports
  at all: no landslide term anywhere, a rainfall forecast, or a burial by placed
  earth the trigger classifier missed. These need judgement, so the number is
  reported as a robustness bound rather than as a correction.

**Nothing here changes the inventory or any release.** A material result is an
argument for cutting a new version with the defects fixed at source; it is not
itself that version, and the v0.6.0 numbers stand until one exists.

Usage::

    PYTHONPATH=src python3 scripts/run_integrity_sensitivity.py
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

csv.field_size_limit(50_000_000)

WINDOWS = (1, 3, 5, 7)
BOOTSTRAP_ITERATIONS = 2000
BOOTSTRAP_SEED = 20260912


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--cases", default="data/outputs/event_antecedent_rainfall.csv")
    parser.add_argument("--controls", default="data/outputs/rainfall_controls.csv")
    parser.add_argument("--findings", default="data/outputs/case_integrity_findings.csv")
    parser.add_argument("--output", default="data/outputs/case_integrity_sensitivity.json")
    return parser


def evaluate(rows: list[dict[str, str]]) -> dict[str, object]:
    """Return cutpoint, AUC and counts for one set of matched records."""

    from landslide_inventory.analysis.rainfall import (
        RainRecord,
        auc,
        bootstrap_threshold_interval,
        youden_threshold,
    )

    from datetime import date as _date

    records = [
        RainRecord(
            record_id=row["record_id"],
            matched_event_id=row.get("matched_event_id", ""),
            event_date=_date.fromisoformat(row["date"]),
            district=row["district"],
            label=int(row["label"]),
            confidence=float(row.get("conf_date") or 0.0),
            values={window: float(row[f"r{window}_mm"]) for window in WINDOWS},
            lagged_values={
                window: float(row.get(f"r{window}_lag1_mm") or 0.0) for window in WINDOWS
            },
            case_event_count=int(row.get("case_event_count") or 1),
        )
        for row in rows
        if all(row.get(f"r{window}_mm") not in (None, "") for window in WINDOWS)
    ]
    result: dict[str, object] = {
        "records": len(records),
        "cases": sum(1 for record in records if record.label == 1),
        "controls": sum(1 for record in records if record.label == 0),
        "districts": len({record.district for record in records}),
    }
    for window in WINDOWS:
        labels = [record.label for record in records]
        scores = [record.values[window] for record in records]
        interval = bootstrap_threshold_interval(
            records,
            window,
            iterations=BOOTSTRAP_ITERATIONS,
            seed=BOOTSTRAP_SEED,
        )
        result[f"r{window}"] = {
            "cutpoint_mm": round(youden_threshold(labels, scores), 4),
            "auc": round(auc(labels, scores), 4),
            "cutpoint_ci95": [round(v, 4) for v in interval] if interval else None,
        }
    return result


def main() -> int:
    args = build_parser().parse_args()

    # Cases and their matched controls are written to separate files; the
    # design only makes sense with both.
    rows = read_csv(ROOT / args.cases) + read_csv(ROOT / args.controls)
    findings = read_csv(ROOT / args.findings)

    violations = {
        (f["district"], f["event_date_ad"]) for f in findings if f["severity"] == "violation"
    }
    contamination = {
        (f["district"], f["event_date_ad"])
        for f in findings
        if f["severity"] == "contamination"
    }
    excludable = violations | contamination

    def drop(rows_in: list[dict[str, str]], removed: set[tuple[str, str]]):
        """Remove flagged CASE days and the controls matched to them.

        Dropping a case while keeping its matched controls would leave orphan
        controls and change the case-control ratio, which moves the cutpoint
        for reasons that have nothing to do with the flagged days.
        """

        dropped_ids = {
            row["record_id"]
            for row in rows_in
            if row["label"] == "1" and (row["district"], row["date"]) in removed
        }
        kept = []
        for row in rows_in:
            if row["record_id"] in dropped_ids:
                continue
            if row.get("matched_event_id") and row["matched_event_id"] in dropped_ids:
                continue
            if row["label"] == "1" and (row["district"], row["date"]) in removed:
                continue
            kept.append(row)
        return kept

    baseline = evaluate(rows)
    without_violations = evaluate(drop(rows, violations))
    without_all = evaluate(drop(rows, excludable))

    def delta(variant: dict[str, object]) -> dict[str, object]:
        out: dict[str, object] = {}
        for window in WINDOWS:
            base = baseline[f"r{window}"]
            alt = variant[f"r{window}"]
            out[f"r{window}"] = {
                "cutpoint_shift_mm": round(alt["cutpoint_mm"] - base["cutpoint_mm"], 4),
                "auc_shift": round(alt["auc"] - base["auc"], 4),
                "inside_baseline_ci": (
                    base["cutpoint_ci95"] is not None
                    and base["cutpoint_ci95"][0] <= alt["cutpoint_mm"] <= base["cutpoint_ci95"][1]
                ),
            }
        return out

    result = {
        "note": (
            "Sensitivity only. No inventory or release was modified. A material "
            "shift is an argument for cutting a new version with the defects "
            "fixed at source, not a correction in itself."
        ),
        "flagged_case_days": {
            "violations": len(violations),
            "contamination": len(contamination),
            "excludable_total": len(excludable),
        },
        "baseline_full_case_set": baseline,
        "without_violations": without_violations,
        "without_violations_and_contamination": without_all,
        "shift_without_violations": delta(without_violations),
        "shift_without_all": delta(without_all),
    }
    (ROOT / args.output).write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    print(
        f"baseline: {baseline['cases']} cases / {baseline['controls']} controls"
        f"  R3 cutpoint {baseline['r3']['cutpoint_mm']} mm  AUC {baseline['r3']['auc']}"
    )
    print(f"  baseline R3 cutpoint 95% CI: {baseline['r3']['cutpoint_ci95']}")
    for name, variant, shift in (
        ("violations removed", without_violations, result["shift_without_violations"]),
        ("violations + contamination removed", without_all, result["shift_without_all"]),
    ):
        print(f"\n{name}  ({variant['cases']} cases)")
        for window in WINDOWS:
            cell = variant[f"r{window}"]
            move = shift[f"r{window}"]
            print(
                f"  R{window}: cutpoint {cell['cutpoint_mm']:8.3f} mm "
                f"({move['cutpoint_shift_mm']:+.3f})   AUC {cell['auc']:.4f} "
                f"({move['auc_shift']:+.4f})   inside baseline CI: {move['inside_baseline_ci']}"
            )
    print(f"\nwrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
