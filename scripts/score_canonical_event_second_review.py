#!/usr/bin/env python3
"""Score second-review agreement and create a blinded adjudication worksheet."""

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
FIRST_COMPLETED = OUTPUT / "canonical_event_audit_COMPLETED.csv"
SECOND_TEMPLATE = OUTPUT / "canonical_event_audit_second_LABEL_HERE.csv"
SECOND_READING = OUTPUT / "canonical_event_audit_second_reading_pack.csv"
MAPPING = OUTPUT / "canonical_event_audit_second_mapping.csv"
MANIFEST = OUTPUT / "canonical_event_audit_second_manifest.json"
DEFAULT_COMPLETED = OUTPUT / "canonical_event_audit_second_COMPLETED.csv"
JSON_OUTPUT = OUTPUT / "canonical_event_audit_interannotator_agreement.json"
REPORT_OUTPUT = OUTPUT / "canonical_event_audit_interannotator_agreement.md"
ADJUDICATION_OUTPUT = OUTPUT / "canonical_event_audit_ADJUDICATE.csv"

FROZEN_COLUMNS = (
    "row_id", "event_id", "claimed_event_date", "claimed_district",
    "claimed_municipality", "claimed_event_type", "claimed_hazard_type",
    "claimed_deaths", "claimed_missing", "claimed_injured",
    "cluster_article_count", "representative_title", "representative_url",
)
REVIEW_FIELDS = (
    "event_really_happened", "one_physical_event", "district_correct",
    "date_correct", "municipality_correct", "event_type_true",
    "hazard_type_true", "deaths_true", "duplicate_merge_correct",
)
YES_NO_UNCLEAR = {"yes", "no", "unclear"}
EVENT_TYPES = {"landslide", "road_obstruction", "other", "unclear"}
HAZARD_TYPES = {"landslide", "debris_flow", "rockfall", "other", "unclear"}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize(value: str) -> str:
    return " ".join(value.strip().lower().split()) or "not_applicable"


def cohen_kappa(left: list[str], right: list[str]) -> float | None:
    if len(left) != len(right) or not left:
        return None
    observed = sum(a == b for a, b in zip(left, right, strict=True)) / len(left)
    left_counts, right_counts = Counter(left), Counter(right)
    categories = set(left_counts) | set(right_counts)
    expected = sum(left_counts[value] * right_counts[value] for value in categories) / len(left) ** 2
    return None if expected == 1.0 else (observed - expected) / (1.0 - expected)


def agreement(
    pairs: list[tuple[dict[str, str], dict[str, str]]],
    getter: Callable[[dict[str, str]], str],
) -> dict[str, float | int | None]:
    left = [normalize(getter(first)) for first, _second in pairs]
    right = [normalize(getter(second)) for _first, second in pairs]
    exact = sum(a == b for a, b in zip(left, right, strict=True))
    return {
        "n": len(pairs),
        "exact_n": exact,
        "agreement": exact / len(pairs) if pairs else None,
        "cohen_kappa": cohen_kappa(left, right),
    }


def usable_status(row: dict[str, str]) -> str:
    event = normalize(row["event_really_happened"])
    if event == "no":
        return "invalid"
    if event != "yes":
        return "unclear"
    fields = [normalize(row[field]) for field in ("one_physical_event", "district_correct", "date_correct")]
    if "no" in fields:
        return "invalid"
    return "valid" if all(value == "yes" for value in fields) else "unclear"


def validate(second: list[dict[str, str]], template: list[dict[str, str]], first: list[dict[str, str]]) -> None:
    if len(second) != 150 or len(template) != 150:
        raise ValueError("Second review must contain exactly 150 rows.")
    if [row["row_id"] for row in second] != [row["row_id"] for row in template]:
        raise ValueError("Second-review row IDs or order differ from the blank pack.")
    first_annotators = {row["annotator"].strip().casefold() for row in first}
    for row, blank in zip(second, template, strict=True):
        for column in FROZEN_COLUMNS:
            if row[column] != blank[column]:
                raise ValueError(f"{row['row_id']}: frozen column {column} changed.")
        event = normalize(row["event_really_happened"])
        if event not in YES_NO_UNCLEAR:
            raise ValueError(f"{row['row_id']}: invalid event_really_happened.")
        annotator = row["annotator"].strip()
        if not annotator:
            raise ValueError(f"{row['row_id']}: annotator is blank.")
        if annotator.casefold() in first_annotators:
            raise ValueError("The second reviewer ID matches the first reviewer ID.")
        if event == "yes":
            for field in ("one_physical_event", "district_correct", "date_correct"):
                if normalize(row[field]) not in YES_NO_UNCLEAR:
                    raise ValueError(f"{row['row_id']}: invalid or blank {field}.")
            if blank["claimed_municipality"] and normalize(row["municipality_correct"]) not in YES_NO_UNCLEAR:
                raise ValueError(f"{row['row_id']}: municipality_correct is required.")
            if normalize(row["event_type_true"]) not in EVENT_TYPES:
                raise ValueError(f"{row['row_id']}: invalid event_type_true.")
            if normalize(row["hazard_type_true"]) not in HAZARD_TYPES:
                raise ValueError(f"{row['row_id']}: invalid hazard_type_true.")
            deaths = normalize(row["deaths_true"])
            if deaths not in {"unclear", "not_reported"}:
                try:
                    if int(deaths) < 0:
                        raise ValueError
                except ValueError as exc:
                    raise ValueError(f"{row['row_id']}: invalid deaths_true.") from exc
            duplicate = normalize(row["duplicate_merge_correct"])
            if int(blank["cluster_article_count"]) > 1 and duplicate not in YES_NO_UNCLEAR:
                raise ValueError(f"{row['row_id']}: duplicate_merge_correct is required.")
            if int(blank["cluster_article_count"]) == 1 and duplicate != "not_applicable":
                raise ValueError(f"{row['row_id']}: use not_applicable for a one-article cluster.")


def comparable_pairs(
    pairs: list[tuple[dict[str, str], dict[str, str]]], field: str
) -> list[tuple[dict[str, str], dict[str, str]]]:
    result = []
    for first, second in pairs:
        if normalize(first["event_really_happened"]) != "yes" or normalize(second["event_really_happened"]) != "yes":
            continue
        if field == "municipality_correct" and not first["claimed_municipality"].strip():
            continue
        if field == "duplicate_merge_correct" and int(first["cluster_article_count"]) == 1:
            continue
        result.append((first, second))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("completed", nargs="?", type=Path, default=DEFAULT_COMPLETED)
    args = parser.parse_args()
    first = read_csv(FIRST_COMPLETED)
    second = read_csv(args.completed)
    template = read_csv(SECOND_TEMPLATE)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if sha256(SECOND_TEMPLATE) != manifest["outputs"][SECOND_TEMPLATE.name]:
        raise ValueError("Blank second-review pack differs from its manifest.")
    if sha256(MAPPING) != manifest["outputs"][MAPPING.name]:
        raise ValueError("Second-review mapping differs from its manifest.")
    validate(second, template, first)

    first_by_id = {row["row_id"]: row for row in first}
    second_by_id = {row["row_id"]: row for row in second}
    reading_by_id = {row["row_id"]: row for row in read_csv(SECOND_READING)}
    mappings = read_csv(MAPPING)
    pairs = [(first_by_id[item["first_row_id"]], second_by_id[item["second_row_id"]]) for item in mappings]

    metrics = {
        "event_really_happened": agreement(pairs, lambda row: row["event_really_happened"]),
        "usable_record_status": agreement(pairs, usable_status),
    }
    for field in REVIEW_FIELDS[1:]:
        subset = comparable_pairs(pairs, field)
        metrics[field] = agreement(subset, lambda row, name=field: row[name])

    disagreement_rows: list[dict[str, str]] = []
    mapping_by_first = {item["first_row_id"]: item for item in mappings}
    for first_row, second_row in pairs:
        differences = [
            field for field in REVIEW_FIELDS
            if normalize(first_row[field]) != normalize(second_row[field])
        ]
        if usable_status(first_row) != usable_status(second_row):
            differences.append("usable_record_status")
        if not differences:
            continue
        mapping = mapping_by_first[first_row["row_id"]]
        evidence = reading_by_id[mapping["second_row_id"]]["article_evidence"]
        base = {column: first_row[column] for column in FROZEN_COLUMNS if column != "row_id"}
        disagreement_rows.append(
            {
                "adjudication_id": f"ADJ-{len(disagreement_rows) + 1:03d}",
                "event_id": first_row["event_id"],
                **{key: value for key, value in base.items() if key != "event_id"},
                "disagreement_fields": ";".join(dict.fromkeys(differences)),
                **{f"first_{field}": first_row[field] for field in REVIEW_FIELDS},
                "first_annotator": first_row["annotator"],
                "first_notes": first_row["notes"],
                **{f"second_{field}": second_row[field] for field in REVIEW_FIELDS},
                "second_annotator": second_row["annotator"],
                "second_notes": second_row["notes"],
                "article_evidence": evidence,
                **{f"final_{field}": "" for field in REVIEW_FIELDS},
                "adjudicator": "",
                "adjudication_notes": "",
            }
        )

    adjudication_columns = list(disagreement_rows[0]) if disagreement_rows else ["adjudication_id"]
    write_csv(ADJUDICATION_OUTPUT, disagreement_rows, adjudication_columns)
    result = {
        "audit": manifest["audit"],
        "rows": len(pairs),
        "first_annotators": sorted({row["annotator"].strip() for row in first}),
        "second_annotators": sorted({row["annotator"].strip() for row in second}),
        "disagreement_rows": len(disagreement_rows),
        "metrics": metrics,
        "input_sha256": {
            FIRST_COMPLETED.name: sha256(FIRST_COMPLETED),
            args.completed.name: sha256(args.completed),
            MANIFEST.name: sha256(MANIFEST),
            MAPPING.name: sha256(MAPPING),
        },
        "outputs": {ADJUDICATION_OUTPUT.name: sha256(ADJUDICATION_OUTPUT)},
    }
    JSON_OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# Canonical event audit inter-annotator agreement",
        "",
        f"Rows: {len(pairs)}",
        f"Rows requiring adjudication: {len(disagreement_rows)}",
        "",
        "| Field | Comparable n | Agreement | Cohen's kappa |",
        "|---|---:|---:|---:|",
    ]
    for field, values in metrics.items():
        agreement_value = values["agreement"]
        kappa = values["cohen_kappa"]
        lines.append(
            f"| {field.replace('_', ' ')} | {values['n']} | "
            f"{'N.A.' if agreement_value is None else f'{agreement_value:.3f}'} | "
            f"{'N.A.' if kappa is None else f'{kappa:.3f}'} |"
        )
    lines.extend(["", "Disagreements are exported for evidence-based adjudication.", ""])
    REPORT_OUTPUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {JSON_OUTPUT}")
    print(f"Wrote {REPORT_OUTPUT}")
    print(f"Wrote {len(disagreement_rows)} rows to {ADJUDICATION_OUTPUT}")


if __name__ == "__main__":
    main()
