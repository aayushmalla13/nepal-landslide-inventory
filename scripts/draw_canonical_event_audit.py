#!/usr/bin/env python3
"""Draw a blind, stratified event-level audit from the frozen canonical CSV."""

from __future__ import annotations

import csv
import hashlib
import json
import random
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "outputs"
CANONICAL = OUTPUT / "canonical_events_final.csv"
DATABASE = ROOT / "data" / "raw_sqlite" / "landslide_inventory.sqlite"

LABEL_OUTPUT = OUTPUT / "canonical_event_audit_LABEL_HERE.csv"
READING_OUTPUT = OUTPUT / "canonical_event_audit_reading_pack.csv"
WEIGHTS_OUTPUT = OUTPUT / "canonical_event_audit_weights.csv"
MANIFEST_OUTPUT = OUTPUT / "canonical_event_audit_manifest.json"

N_ROWS = 150
SEED = 20260916
MIN_PER_STRATUM = 3
CANONICAL_SHA256 = "3b335babbfcbe0b50d2aad9023e08e55a2ca6e8e0881729615df33e2c9b9d0e8"

CLAIM_COLUMNS = (
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
LABEL_COLUMNS = (
    "event_really_happened",
    "one_physical_event",
    "district_correct",
    "date_correct",
    "municipality_correct",
    "event_type_true",
    "hazard_type_true",
    "deaths_true",
    "duplicate_merge_correct",
    "annotator",
    "notes",
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
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


def title_language(title: str) -> str:
    return "np" if any("\u0900" <= char <= "\u097f" for char in title) else "en"


def period(event_date: str) -> str:
    year = int(event_date[:4])
    if year <= 2018:
        return "2015-2018"
    if year <= 2022:
        return "2019-2022"
    return "2023-2026"


def stratum(row: dict[str, str]) -> str:
    support = "multi_article" if int(row["cluster_size"]) > 1 else "single_article"
    return "|".join(
        (
            title_language(row["representative_title"]),
            period(row["event_date_ad"]),
            row["event_type"],
            support,
        )
    )


def allocate_strata(
    sizes: dict[str, int], total: int, minimum: int = MIN_PER_STRATUM
) -> dict[str, int]:
    """Use proportional allocation with a minimum for every populated stratum."""

    population = sum(sizes.values())
    if total > population:
        raise ValueError("Requested sample exceeds the canonical population.")
    if sum(min(size, minimum) for size in sizes.values()) > total:
        raise ValueError("Minimum stratum allocation exceeds the requested sample.")
    quotas = {key: total * size / population for key, size in sizes.items()}
    allocation = {key: min(size, max(minimum, int(quotas[key]))) for key, size in sizes.items()}
    while sum(allocation.values()) > total:
        eligible = [key for key in sizes if allocation[key] > min(sizes[key], minimum)]
        key = min(eligible, key=lambda item: (quotas[item] - allocation[item], item))
        allocation[key] -= 1
    while sum(allocation.values()) < total:
        eligible = [key for key in sizes if allocation[key] < sizes[key]]
        key = max(eligible, key=lambda item: (quotas[item] - allocation[item], item))
        allocation[key] += 1
    return allocation


def select_rows(
    rows: list[dict[str, str]], total: int = N_ROWS, seed: int = SEED
) -> tuple[list[dict[str, str]], dict[str, int], dict[str, int]]:
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[stratum(row)].append(row)
    sizes = {key: len(value) for key, value in groups.items()}
    allocation = allocate_strata(sizes, total)
    selected: list[dict[str, str]] = []
    for index, key in enumerate(sorted(groups)):
        candidates = sorted(groups[key], key=lambda row: row["event_id"])
        random.Random(seed + index).shuffle(candidates)
        selected.extend(candidates[: allocation[key]])
    random.Random(seed + 10_000).shuffle(selected)
    return selected, sizes, allocation


def parse_urls(row: dict[str, str]) -> list[str]:
    try:
        payload = json.loads(row.get("event_payload") or "{}")
    except json.JSONDecodeError:
        payload = {}
    urls = payload.get("urls") if isinstance(payload, dict) else []
    ordered = [str(url) for url in (urls or []) if str(url).strip()]
    representative = row.get("representative_url", "").strip()
    if representative and representative not in ordered:
        ordered.insert(0, representative)
    return ordered


def load_article_evidence(connection: sqlite3.Connection, row: dict[str, str]) -> str:
    sections: list[str] = []
    for index, url in enumerate(parse_urls(row), start=1):
        article = connection.execute(
            """
            SELECT source, title, published_date_ad, text
            FROM raw_articles
            WHERE url = ?
            """,
            (url,),
        ).fetchone()
        if article is None:
            sections.append(f"ARTICLE {index}\nURL: {url}\nEVIDENCE UNAVAILABLE IN LOCAL CORPUS")
            continue
        source, title, published, text = article
        sections.append(
            "\n".join(
                (
                    f"ARTICLE {index}",
                    f"SOURCE: {source or ''}",
                    f"PUBLISHED: {published or ''}",
                    f"TITLE: {title or ''}",
                    f"URL: {url}",
                    "TEXT:",
                    str(text or "").strip(),
                )
            )
        )
    return "\n\n====================\n\n".join(sections)


def claim_row(row: dict[str, str], row_id: str) -> dict[str, str]:
    return {
        "row_id": row_id,
        "event_id": row["event_id"],
        "claimed_event_date": row["event_date_ad"],
        "claimed_district": row["district"],
        "claimed_municipality": row["municipality"],
        "claimed_event_type": row["event_type"],
        "claimed_hazard_type": row["hazard_type"],
        "claimed_deaths": row["deaths"],
        "claimed_missing": row["missing"],
        "claimed_injured": row["injured"],
        "cluster_article_count": row["cluster_size"],
        "representative_title": row["representative_title"],
        "representative_url": row["representative_url"],
    }


def main() -> None:
    if sha256(CANONICAL) != CANONICAL_SHA256:
        raise RuntimeError("Frozen canonical CSV hash differs from inventory v0.6.0.")
    canonical = read_csv(CANONICAL)
    selected, population_sizes, allocation = select_rows(canonical)
    labels: list[dict[str, str]] = []
    readings: list[dict[str, str]] = []
    weights: list[dict[str, Any]] = []
    connection = sqlite3.connect(DATABASE)
    try:
        for number, row in enumerate(selected, start=1):
            row_id = f"CEA-{number:03d}"
            claims = claim_row(row, row_id)
            labels.append({**claims, **{column: "" for column in LABEL_COLUMNS}})
            readings.append({**claims, "article_evidence": load_article_evidence(connection, row)})
            key = stratum(row)
            sample_n = allocation[key]
            weights.append(
                {
                    "row_id": row_id,
                    "event_id": row["event_id"],
                    "stratum": key,
                    "population_n": population_sizes[key],
                    "sample_n": sample_n,
                    "inclusion_probability": round(sample_n / population_sizes[key], 10),
                    "sampling_weight": round(population_sizes[key] / sample_n, 10),
                }
            )
    finally:
        connection.close()

    write_csv(LABEL_OUTPUT, labels, [*CLAIM_COLUMNS, *LABEL_COLUMNS])
    write_csv(READING_OUTPUT, readings, [*CLAIM_COLUMNS, "article_evidence"])
    write_csv(
        WEIGHTS_OUTPUT,
        weights,
        [
            "row_id", "event_id", "stratum", "population_n", "sample_n",
            "inclusion_probability", "sampling_weight",
        ],
    )
    selected_counts = Counter(row["stratum"] for row in weights)
    manifest = {
        "audit": "canonical_event_level_v1",
        "purpose": "publication-grade blind audit of frozen canonical event records",
        "inventory_release": "nepal_landslide_inventory_v0.6.0_v7_20260915",
        "canonical_rows": len(canonical),
        "sample_rows": len(selected),
        "seed": SEED,
        "stratification": ["title_language", "period", "event_type", "article_support"],
        "minimum_per_populated_stratum": MIN_PER_STRATUM,
        "canonical_sha256": sha256(CANONICAL),
        "population_by_stratum": dict(sorted(population_sizes.items())),
        "sample_by_stratum": dict(sorted(selected_counts.items())),
        "outputs": {
            LABEL_OUTPUT.name: sha256(LABEL_OUTPUT),
            READING_OUTPUT.name: sha256(READING_OUTPUT),
            WEIGHTS_OUTPUT.name: sha256(WEIGHTS_OUTPUT),
        },
        "blinding": "confidence, specificity, scope, and location-consistency fields omitted",
    }
    MANIFEST_OUTPUT.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {len(labels)} labels to {LABEL_OUTPUT}")
    print(f"Wrote reading pack to {READING_OUTPUT}")
    print(f"Wrote sampling weights to {WEIGHTS_OUTPUT}")
    print(f"Wrote manifest to {MANIFEST_OUTPUT}")


if __name__ == "__main__":
    main()
