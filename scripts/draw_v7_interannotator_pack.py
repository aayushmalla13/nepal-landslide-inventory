#!/usr/bin/env python3
"""Draw a blind, stratified subset of locked v7 for a second human rater."""

from __future__ import annotations

import csv
import hashlib
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "outputs"
N_ROWS = 120
SEED = 20260914
MIN_PER_STRATUM = 5

LABEL_SOURCE = OUTPUT / "locked_test_set_v7_labels_final.csv"
READING_SOURCE = OUTPUT / "locked_test_set_v7_reading_pack.csv"
PREDICTION_SOURCE = OUTPUT / "locked_test_set_v7_predictions.csv"
LABEL_OUTPUT = OUTPUT / "locked_test_set_v7_second_annotator_LABEL_HERE.csv"
READING_OUTPUT = OUTPUT / "locked_test_set_v7_second_annotator_reading_pack.csv"
MANIFEST_OUTPUT = OUTPUT / "locked_test_set_v7_second_annotator_manifest.json"

FROZEN_COLUMNS = ("row_id", "url", "source", "year", "route_lang", "title", "snippet")
TRUTH_COLUMNS = (
    "is_landslide_event_true",
    "in_nepal_true",
    "hazard_type_true",
    "event_granularity_true",
    "article_role_true",
    "district_true",
    "municipality_true",
    "date_true",
    "deaths_true",
    "trigger_true",
    "annotator",
    "notes",
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def allocate_strata(sizes: dict[str, int], total: int) -> dict[str, int]:
    """Allocate a proportional sample while retaining small decision strata."""

    if total > sum(sizes.values()):
        raise ValueError("Requested sample is larger than the source population.")
    quotas = {key: total * size / sum(sizes.values()) for key, size in sizes.items()}
    allocation = {
        key: min(size, max(min(MIN_PER_STRATUM, size), int(quotas[key])))
        for key, size in sizes.items()
    }
    while sum(allocation.values()) > total:
        candidates = [
            key
            for key, size in sizes.items()
            if allocation[key] > min(MIN_PER_STRATUM, size)
        ]
        if not candidates:
            raise ValueError("Minimum stratum allocation exceeds requested sample.")
        key = min(candidates, key=lambda item: (quotas[item] - allocation[item], item))
        allocation[key] -= 1
    while sum(allocation.values()) < total:
        candidates = [key for key, size in sizes.items() if allocation[key] < size]
        key = max(candidates, key=lambda item: (quotas[item] - allocation[item], item))
        allocation[key] += 1
    return allocation


def blank_label_row(row: dict[str, str]) -> dict[str, str]:
    return {**{column: row[column] for column in FROZEN_COLUMNS}, **{c: "" for c in TRUTH_COLUMNS}}


def write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    labels = read_csv(LABEL_SOURCE)
    readings = {row["row_id"]: row for row in read_csv(READING_SOURCE)}
    predictions = {row["row_id"]: row for row in read_csv(PREDICTION_SOURCE)}
    if len(labels) != len(readings) or len(labels) != len(predictions):
        raise ValueError("Locked-v7 labels, reading pack, and predictions differ in size.")

    groups: dict[str, list[str]] = defaultdict(list)
    labels_by_id = {row["row_id"]: row for row in labels}
    for row in labels:
        prediction = predictions.get(row["row_id"])
        if prediction is None:
            raise ValueError(f"Missing prediction for {row['row_id']}")
        groups[prediction["stratum"]].append(row["row_id"])

    allocation = allocate_strata({key: len(value) for key, value in groups.items()}, N_ROWS)
    rng = random.Random(SEED)
    selected: list[str] = []
    for stratum in sorted(groups):
        candidates = sorted(groups[stratum])
        rng.shuffle(candidates)
        selected.extend(candidates[: allocation[stratum]])
    selected.sort()

    label_rows = [blank_label_row(labels_by_id[row_id]) for row_id in selected]
    reading_rows = [readings[row_id] for row_id in selected]
    write_csv(LABEL_OUTPUT, label_rows, [*FROZEN_COLUMNS, *TRUTH_COLUMNS])
    write_csv(READING_OUTPUT, reading_rows, list(reading_rows[0]))

    selected_strata = Counter(predictions[row_id]["stratum"] for row_id in selected)
    manifest = {
        "purpose": "blind independent second annotation for inter-rater agreement",
        "selection_basis": "pipeline decision-by-language stratum only; truth labels not used",
        "rows": len(selected),
        "seed": SEED,
        "minimum_per_stratum": MIN_PER_STRATUM,
        "selected_by_stratum": dict(sorted(selected_strata.items())),
        "first_annotator_ids": sorted({row["annotator"] for row in labels}),
        "source_files": {
            LABEL_SOURCE.name: sha256(LABEL_SOURCE),
            READING_SOURCE.name: sha256(READING_SOURCE),
            PREDICTION_SOURCE.name: sha256(PREDICTION_SOURCE),
        },
        "outputs": {
            LABEL_OUTPUT.name: sha256(LABEL_OUTPUT),
            READING_OUTPUT.name: sha256(READING_OUTPUT),
        },
    }
    MANIFEST_OUTPUT.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {len(selected)} blind rows to {LABEL_OUTPUT}")
    print(f"Reading pack: {READING_OUTPUT}")
    print(f"Manifest: {MANIFEST_OUTPUT}")


if __name__ == "__main__":
    main()
