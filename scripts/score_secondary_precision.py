#!/usr/bin/env python3
"""Score the blind secondary-recovery census and export verified claims only.

The extractor is dry-run only and intentionally disconnected from the canonical
inventory. This script preserves that boundary: it scores all reviewed emitted
claims and exports only claims whose district and date were both confirmed.

This is a precision census. It cannot estimate recall because articles from
which the extractor emitted nothing were not labelled here.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LOCATION_LABELS = frozenset({"yes", "no", "unclear"})
DATE_LABELS = frozenset({"yes", "no", "unclear"})
VERIFIED_STATUS = "confirmed_district_and_date"
SUPPLEMENT_STATUS = "manual_supplement_only_not_integrated"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _require_unique(rows: list[dict[str, str]], fields: tuple[str, ...], name: str) -> None:
    keys = [tuple(row.get(field, "") for field in fields) for row in rows]
    duplicates = [key for key, count in Counter(keys).items() if count > 1]
    if duplicates:
        raise ValueError(f"{name} has duplicate keys: {duplicates[:3]}")


def validate_inputs(
    labels: list[dict[str, str]],
    strata: list[dict[str, str]],
    recovered: list[dict[str, str]],
) -> None:
    if not labels:
        raise ValueError("label file is empty")
    _require_unique(labels, ("row_id",), "labels")
    _require_unique(strata, ("row_id",), "strata")
    _require_unique(recovered, ("url", "district", "event_date_ad"), "recovered claims")
    if [row["row_id"] for row in labels] != [row["row_id"] for row in strata]:
        raise ValueError("labels and strata must contain the same row IDs in the same order")
    recovered_keys = {
        (row["url"], row["district"], row["event_date_ad"]) for row in recovered
    }
    for label, stratum in zip(labels, strata):
        row_id = label["row_id"]
        location = label.get("failure_really_happened_there", "").strip().lower()
        date = label.get("date_is_right", "").strip().lower()
        if location not in LOCATION_LABELS:
            raise ValueError(f"{row_id}: invalid location label {location!r}")
        if location == "yes" and date not in DATE_LABELS:
            raise ValueError(f"{row_id}: date label is required when location=yes")
        if location != "yes" and date:
            raise ValueError(f"{row_id}: date label must be blank when location={location}")
        if label["claimed_district"] != stratum["district"]:
            raise ValueError(f"{row_id}: claimed district differs from strata")
        if label["claimed_date"] != stratum["event_date_ad"]:
            raise ValueError(f"{row_id}: claimed date differs from strata")
        try:
            weight = float(stratum["inclusion_weight"])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{row_id}: invalid inclusion weight") from exc
        if weight <= 0:
            raise ValueError(f"{row_id}: inclusion weight must be positive")
        key = (stratum["url"], stratum["district"], stratum["event_date_ad"])
        if key not in recovered_keys:
            raise ValueError(f"{row_id}: reviewed claim is absent from secondary_failures.csv")


def _classification(label: dict[str, str]) -> str:
    location = label["failure_really_happened_there"].strip().lower()
    date = label.get("date_is_right", "").strip().lower()
    if location == "no":
        return "wrong_location"
    if location == "unclear":
        return "unclear_location"
    if date == "yes":
        return "verified"
    if date == "no":
        return "wrong_date"
    return "unclear_date"


def _metrics(items: list[tuple[dict[str, str], dict[str, str]]]) -> dict[str, Any]:
    counts = Counter(_classification(label) for label, _ in items)
    weights: Counter[str] = Counter()
    for label, stratum in items:
        weights[_classification(label)] += float(stratum["inclusion_weight"])
    total_weight = sum(weights.values())
    location_weight = weights["verified"] + weights["wrong_date"] + weights["unclear_date"]
    location_yes = counts["verified"] + counts["wrong_date"] + counts["unclear_date"]
    return {
        "reviewed_claims": len(items),
        "weighted_population": round(total_weight, 4),
        "verified_claims": counts["verified"],
        "wrong_location": counts["wrong_location"],
        "unclear_location": counts["unclear_location"],
        "wrong_date": counts["wrong_date"],
        "unclear_date": counts["unclear_date"],
        "location_confirmed": location_yes,
        "location_precision": round(location_weight / total_weight, 4),
        "joint_district_date_precision": round(weights["verified"] / total_weight, 4),
        "date_precision_given_location": round(weights["verified"] / location_weight, 4),
    }


def score(
    labels: list[dict[str, str]],
    strata: list[dict[str, str]],
    recovered: list[dict[str, str]],
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    validate_inputs(labels, strata, recovered)
    recovered_by_key = {
        (row["url"], row["district"], row["event_date_ad"]): row for row in recovered
    }
    paired = list(zip(labels, strata))
    by_stratum: dict[str, list[tuple[dict[str, str], dict[str, str]]]] = defaultdict(list)
    for item in paired:
        by_stratum[item[1]["stratum"]].append(item)
    verified: list[dict[str, str]] = []
    for label, stratum in paired:
        if _classification(label) != "verified":
            continue
        key = (stratum["url"], stratum["district"], stratum["event_date_ad"])
        verified.append(
            {
                "row_id": label["row_id"],
                **recovered_by_key[key],
                "human_location": "yes",
                "human_date": "yes",
                "human_annotator": label.get("annotator", ""),
                "human_notes": label.get("notes", ""),
                "manual_verification_status": VERIFIED_STATUS,
                "release_status": SUPPLEMENT_STATUS,
            }
        )
    distinct_days = {(row["district"], row["event_date_ad"]) for row in verified}
    report = {
        "evaluation": "secondary_failure_blind_precision_census",
        "unit": "emitted source-level district-date claim",
        "design": {
            "census": all(float(row["inclusion_weight"]) == 1.0 for row in strata),
            "precision_only": True,
            "recall_estimable": False,
            "note": "Only emitted claims were reviewed; missed district-date events were not measured.",
        },
        "overall": _metrics(paired),
        "by_stratum": {name: _metrics(items) for name, items in sorted(by_stratum.items())},
        "verified_supplement": {
            "source_claims": len(verified),
            "distinct_district_days": len(distinct_days),
            "status": SUPPLEMENT_STATUS,
        },
        "release_gate": {
            "decision": "failed",
            "automated_secondary_recoveries": "exclude_from_canonical_inventory",
            "verified_rows": SUPPLEMENT_STATUS,
            "basis": (
                "Joint district-date precision is near the approximately 40% failure "
                "case documented before labelling, not the high precision needed for release."
            ),
        },
        "limitations": [
            "The supplement confirms particular claims, not extractor generalisation.",
            "A fresh locked district-date test is required after extractor redesign.",
            "No secondary claim is integrated into the database, inventory, analysis, or release.",
        ],
    }
    return report, verified


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels", default="data/outputs/secondary_precision_HUMAN_COMPLETED.csv")
    parser.add_argument("--strata", default="data/outputs/secondary_precision_strata.csv")
    parser.add_argument("--recovered", default="data/outputs/secondary_failures.csv")
    parser.add_argument("--report", default="data/outputs/secondary_precision_report.json")
    parser.add_argument("--verified", default="data/outputs/secondary_failures_manually_verified.csv")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    report, verified = score(
        read_csv(ROOT / args.labels), read_csv(ROOT / args.strata), read_csv(ROOT / args.recovered)
    )
    report_path = ROOT / args.report
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    verified_path = ROOT / args.verified
    verified_path.parent.mkdir(parents=True, exist_ok=True)
    if not verified:
        raise ValueError("no district-date claims were manually verified")
    with verified_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(verified[0]))
        writer.writeheader()
        writer.writerows(verified)
    overall = report["overall"]
    print(f"reviewed {overall['reviewed_claims']} emitted source claims")
    print(f"  location precision: {overall['location_precision']:.4f}")
    print(f"  joint district-date precision: {overall['joint_district_date_precision']:.4f}")
    print(f"  verified supplement: {len(verified)} claims -> {report['verified_supplement']['distinct_district_days']} distinct district-days")
    print("  release gate: FAILED; automated secondary recoveries remain excluded")
    print(f"wrote {args.report} and {args.verified}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
