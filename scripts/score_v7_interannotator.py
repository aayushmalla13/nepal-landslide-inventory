#!/usr/bin/env python3
"""Score independent second-rater agreement against frozen locked-v7 labels."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "outputs"
FIRST_LABELS = OUTPUT / "locked_test_set_v7_labels_final.csv"
BLIND_PACK = OUTPUT / "locked_test_set_v7_second_annotator_LABEL_HERE.csv"
DEFAULT_COMPLETED = OUTPUT / "locked_test_set_v7_second_annotator_COMPLETED.csv"
JSON_OUTPUT = OUTPUT / "locked_test_set_v7_interannotator_agreement.json"
REPORT_OUTPUT = OUTPUT / "locked_test_set_v7_interannotator_agreement.md"

FROZEN_COLUMNS = ("row_id", "url", "source", "year", "route_lang", "title", "snippet")
CONTROLLED = {
    "is_landslide_event_true": {"yes", "no", "unclear"},
    "in_nepal_true": {"yes", "no", "unclear"},
    "hazard_type_true": {
        "landslide", "debris_flow", "rockfall", "avalanche", "flood",
        "other_hazard", "not_a_hazard", "unclear",
    },
    "event_granularity_true": {"single", "multi", "roundup", "not_applicable", "unclear"},
    "article_role_true": {
        "first_report", "follow_up", "retrospective", "forecast_or_risk",
        "metaphor_or_nonevent", "unclear",
    },
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def cohen_kappa(left: list[str], right: list[str]) -> float | None:
    if len(left) != len(right) or not left:
        return None
    observed = sum(a == b for a, b in zip(left, right, strict=True)) / len(left)
    left_counts, right_counts = Counter(left), Counter(right)
    categories = set(left_counts) | set(right_counts)
    expected = sum(left_counts[c] * right_counts[c] for c in categories) / len(left) ** 2
    return None if expected == 1.0 else (observed - expected) / (1.0 - expected)


def headline(row: dict[str, str]) -> str:
    event = row["is_landslide_event_true"].strip()
    nepal = row["in_nepal_true"].strip()
    hazard = row["hazard_type_true"].strip()
    granularity = row["event_granularity_true"].strip()
    if "unclear" in {event, nepal, hazard, granularity}:
        return "unclear"
    positive = (
        event == "yes"
        and nepal == "yes"
        and hazard in {"landslide", "debris_flow", "rockfall"}
        and granularity == "single"
    )
    return "yes" if positive else "no"


def categorical_agreement(
    first: list[dict[str, str]], second: list[dict[str, str]], getter: Callable[[dict[str, str]], str]
) -> dict[str, float | int | None]:
    left, right = [getter(row) for row in first], [getter(row) for row in second]
    exact = sum(a == b for a, b in zip(left, right, strict=True))
    return {"n": len(left), "exact_n": exact, "agreement": exact / len(left), "cohen_kappa": cohen_kappa(left, right)}


def extraction_agreement(first: list[dict[str, str]], second: list[dict[str, str]], field: str) -> dict[str, float | int | None]:
    comparable = exact = 0
    first_available = second_available = 0
    for left, right in zip(first, second, strict=True):
        a = " ".join(left[field].strip().casefold().split())
        b = " ".join(right[field].strip().casefold().split())
        first_available += bool(a)
        second_available += bool(b)
        if a and b:
            comparable += 1
            exact += a == b
    return {
        "rows": len(first),
        "first_nonblank_n": first_available,
        "second_nonblank_n": second_available,
        "both_nonblank_n": comparable,
        "exact_n": exact,
        "exact_agreement_when_both_nonblank": exact / comparable if comparable else None,
    }


def validate(first: list[dict[str, str]], second: list[dict[str, str]], blind: list[dict[str, str]]) -> None:
    if len(second) != len(blind):
        raise ValueError(f"Expected {len(blind)} completed rows, found {len(second)}.")
    first_by_id = {row["row_id"]: row for row in first}
    if [row["row_id"] for row in second] != [row["row_id"] for row in blind]:
        raise ValueError("Completed row IDs or order differ from the blind pack.")
    for completed, template in zip(second, blind, strict=True):
        for column in FROZEN_COLUMNS:
            if completed[column] != template[column]:
                raise ValueError(f"{completed['row_id']}: frozen column {column} changed.")
        for field, allowed in CONTROLLED.items():
            if completed[field].strip() not in allowed:
                raise ValueError(f"{completed['row_id']}: invalid or blank {field}.")
        if not completed["annotator"].strip():
            raise ValueError(f"{completed['row_id']}: annotator is blank.")
        original = first_by_id[completed["row_id"]]
        if completed["annotator"].strip() == original["annotator"].strip():
            raise ValueError("Second annotator ID matches the first annotator; this is not inter-rater validation.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("completed", nargs="?", type=Path, default=DEFAULT_COMPLETED)
    args = parser.parse_args()
    first_all, second, blind = read_csv(FIRST_LABELS), read_csv(args.completed), read_csv(BLIND_PACK)
    validate(first_all, second, blind)
    first_by_id = {row["row_id"]: row for row in first_all}
    first = [first_by_id[row["row_id"]] for row in second]

    categorical = {
        field.removesuffix("_true"): categorical_agreement(first, second, lambda row, f=field: row[f].strip())
        for field in CONTROLLED
    }
    categorical["headline"] = categorical_agreement(first, second, headline)
    result = {
        "rows": len(second),
        "first_annotators": sorted({row["annotator"].strip() for row in first}),
        "second_annotators": sorted({row["annotator"].strip() for row in second}),
        "input_sha256": {
            FIRST_LABELS.name: sha256(FIRST_LABELS),
            BLIND_PACK.name: sha256(BLIND_PACK),
            args.completed.name: sha256(args.completed),
        },
        "categorical": categorical,
        "extraction": {
            "district": extraction_agreement(first, second, "district_true"),
            "event_date": extraction_agreement(first, second, "date_true"),
        },
    }
    JSON_OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = ["# Locked-v7 inter-annotator agreement", "", f"Rows: {len(second)}", "", "| Field | Agreement | Cohen's kappa |", "|---|---:|---:|"]
    for field, values in categorical.items():
        kappa = values["cohen_kappa"]
        lines.append(f"| {field} | {values['agreement']:.3f} | {'undefined' if kappa is None else f'{kappa:.3f}'} |")
    lines.extend(["", "District and date agreement are reported in the JSON output among rows where both raters supplied a value.", ""])
    REPORT_OUTPUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {JSON_OUTPUT}")
    print(f"Wrote {REPORT_OUTPUT}")


if __name__ == "__main__":
    main()
