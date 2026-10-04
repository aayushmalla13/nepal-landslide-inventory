#!/usr/bin/env python3
"""Draw the locked, blinded fresh validation sample for the v0.8 candidate."""

from __future__ import annotations

import csv
import hashlib
import json
import random
import re
import sqlite3
from collections import Counter, defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "outputs"
RELEASE_ID = "nepal_landslide_inventory_v0.8.0_candidate_20260923"
RELEASE_DIR = ROOT / "data" / "releases" / RELEASE_ID
CANONICAL = RELEASE_DIR / "canonical_events_final.csv"
RELEASE_MANIFEST = RELEASE_DIR / "release_manifest.json"
DATABASE = ROOT / "data" / "raw_sqlite" / "landslide_inventory.sqlite"
DRAW_SCRIPT = Path(__file__).resolve()
SCORER_SCRIPT = ROOT / "scripts" / "score_v08_fresh_validation.py"

LABELS = OUTPUT / "v08_fresh_validation_LABEL_HERE.csv"
READING = OUTPUT / "v08_fresh_validation_reading_pack.csv"
WEIGHTS = OUTPUT / "v08_fresh_validation_weights.csv"
MANIFEST = OUTPUT / "v08_fresh_validation_manifest.json"

CANONICAL_SHA256 = "0822515b56693af22daf2e3cc6e63b178eb41fefa46a8b607a47d6da9efdcd07"
SAMPLE_ROWS = 150
SEED = 20260923
MIN_PER_STRATUM = 3

# These files record human exposure to events or article evidence before this draw.
# Keep the list explicit so rerunning the draw cannot silently change its frame.
REVIEWED_FILES = (
    "canonical_event_audit_COMPLETED.csv",
    "canonical_event_audit_second_COMPLETED.csv",
    "canonical_event_audit_ADJUDICATE_COMPLETED.csv",
    "canonical_event_article_mapping_DECISIONS_COMPLETED.csv",
    "canonical_event_true_value_REVIEW_COMPLETED.csv",
    "canonical_event_structured_attribute_REVIEW_COMPLETED.csv",
    "post_correction_fresh_audit_COMPLETED.csv",
    "post_correction_challenge_COMPLETED.csv",
    "post_correction_article_mapping_DECISIONS_COMPLETED.csv",
    "post_correction_remediation_BATCH_TRUE_VALUE_REVIEW_COMPLETED.csv",
    "post_correction_structured_attribute_REVIEW_COMPLETED.csv",
    "granularity_class1_COMPLETED.csv",
    "granularity_development_COMPLETED.csv",
    "locked_test_set_v7_COMPLETED.csv",
    "place_backfill_review_pack_COMPLETED.csv",
    "secondary_locked_v8_COMPLETED.csv",
    "secondary_precision_HUMAN_COMPLETED.csv",
    "secondary_precision_SPOTCHECK_COMPLETED.csv",
)

# Audit event IDs must be resolved against the release from which each sample was drawn
# so every article in a reviewed cluster, not only its representative URL, is excluded.
HISTORICAL_AUDITS = (
    (
        ROOT
        / "data/releases/nepal_landslide_inventory_v0.6.0_v7_20260915/canonical_events_final.csv",
        OUTPUT / "canonical_event_audit_LABEL_HERE.csv",
    ),
    (
        ROOT
        / "data/releases/nepal_landslide_inventory_v0.7.0_candidate_20260916"
        / "canonical_events_final.csv",
        OUTPUT / "post_correction_fresh_audit_LABEL_HERE.csv",
    ),
    (
        ROOT
        / "data/releases/nepal_landslide_inventory_v0.7.0_candidate_20260916"
        / "canonical_events_final.csv",
        OUTPUT / "post_correction_challenge_LABEL_HERE.csv",
    ),
)

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

PROMOTION_RULE = {
    "event_existence_precision": {"minimum_estimate": 0.90, "minimum_ci95_lower": 0.85},
    "usable_record_precision": {"minimum_estimate": 0.70, "minimum_ci95_lower": 0.60},
    "single_event_accuracy": {"minimum_estimate": 0.85, "minimum_ci95_lower": 0.75},
    "district_accuracy": {"minimum_estimate": 0.85, "minimum_ci95_lower": 0.75},
    "date_accuracy": {"minimum_estimate": 0.85, "minimum_ci95_lower": 0.75},
    "maximum_event_existence_unclear_fraction": 0.05,
    "decision": "promote only if every threshold passes; otherwise retain candidate status",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], columns: tuple[str, ...]) -> None:
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


def parse_payload(row: dict[str, str]) -> dict[str, Any]:
    try:
        payload = json.loads(row.get("event_payload") or "{}")
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def event_urls(row: dict[str, str]) -> set[str]:
    payload = parse_payload(row)
    urls = {str(url).strip() for url in payload.get("urls", []) if str(url).strip()}
    representative = row.get("representative_url", "").strip()
    if representative:
        urls.add(representative)
    return urls


def embedded_urls(value: str) -> set[str]:
    """Extract article links from plain, JSON, or evidence-text cells."""
    return {match.rstrip(").,;]") for match in re.findall(r"https?://[^\s\"'|,}]+", value or "")}


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


def allocate_strata(sizes: dict[str, int], total: int, minimum: int) -> dict[str, int]:
    population = sum(sizes.values())
    if total > population:
        raise ValueError("Requested sample exceeds its population")
    floors = {key: min(size, minimum) for key, size in sizes.items()}
    if sum(floors.values()) > total:
        raise ValueError("Minimum allocations exceed the requested sample")
    quotas = {key: total * size / population for key, size in sizes.items()}
    allocation = {key: min(sizes[key], max(floors[key], int(quotas[key]))) for key in sizes}
    while sum(allocation.values()) > total:
        eligible = [key for key in sizes if allocation[key] > floors[key]]
        key = min(eligible, key=lambda item: (quotas[item] - allocation[item], item))
        allocation[key] -= 1
    while sum(allocation.values()) < total:
        eligible = [key for key in sizes if allocation[key] < sizes[key]]
        key = max(eligible, key=lambda item: (quotas[item] - allocation[item], item))
        allocation[key] += 1
    return allocation


def stratified_select(
    rows: list[dict[str, str]],
    key_fn: Callable[[dict[str, str]], str],
    total: int,
    minimum: int,
    seed: int,
) -> tuple[list[dict[str, str]], dict[str, int], dict[str, int]]:
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[key_fn(row)].append(row)
    sizes = {key: len(group) for key, group in groups.items()}
    allocation = allocate_strata(sizes, total, minimum)
    selected: list[dict[str, str]] = []
    for index, key in enumerate(sorted(groups)):
        candidates = sorted(groups[key], key=lambda item: item["event_id"])
        random.Random(seed + index).shuffle(candidates)
        selected.extend(candidates[: allocation[key]])
    random.Random(seed + 10_000).shuffle(selected)
    return selected, sizes, allocation


def reviewed_exclusions(
    canonical: list[dict[str, str]],
) -> tuple[set[str], set[str], dict[str, dict[str, int]]]:
    current_by_id = {row["event_id"]: row for row in canonical}
    reviewed_ids: set[str] = set()
    reviewed_urls: set[str] = set()
    counts: dict[str, dict[str, int]] = {}

    for name in REVIEWED_FILES:
        path = OUTPUT / name
        rows = read_csv(path)
        file_ids = {row.get("event_id", "").strip() for row in rows} - {""}
        file_urls: set[str] = set()
        for row in rows:
            for value in row.values():
                file_urls.update(embedded_urls(value))
        reviewed_ids.update(file_ids)
        reviewed_urls.update(file_urls)
        counts[name] = {"event_ids": len(file_ids), "direct_urls": len(file_urls)}

    for event_id in reviewed_ids & set(current_by_id):
        reviewed_urls.update(event_urls(current_by_id[event_id]))

    for release_path, audit_path in HISTORICAL_AUDITS:
        release_by_id = {row["event_id"]: row for row in read_csv(release_path)}
        audit_ids = {row["event_id"] for row in read_csv(audit_path)}
        missing = audit_ids - set(release_by_id)
        if missing:
            raise ValueError(
                f"Historical audit IDs absent from {release_path.name}: {sorted(missing)[:3]}"
            )
        historical_urls = set().union(
            *(event_urls(release_by_id[event_id]) for event_id in audit_ids)
        )
        reviewed_urls.update(historical_urls)
        counts[str(audit_path.relative_to(ROOT))] = {
            "event_ids": len(audit_ids),
            "all_cluster_urls": len(historical_urls),
        }

    return reviewed_ids, reviewed_urls, counts


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


def load_article_evidence(connection: sqlite3.Connection, row: dict[str, str]) -> tuple[str, int]:
    sections: list[str] = []
    unavailable = 0
    for index, url in enumerate(sorted(event_urls(row)), start=1):
        article = connection.execute(
            "SELECT source, title, published_date_ad, text FROM raw_articles WHERE url = ?", (url,)
        ).fetchone()
        if article is None:
            unavailable += 1
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
    return "\n\n====================\n\n".join(sections), unavailable


def main() -> None:
    if sha256(CANONICAL) != CANONICAL_SHA256:
        raise RuntimeError("Canonical CSV differs from the locked v0.8 candidate")
    release_manifest = json.loads(RELEASE_MANIFEST.read_text(encoding="utf-8"))
    if release_manifest["status"] != "pending_fresh_validation":
        raise RuntimeError("v0.8 candidate is not awaiting fresh validation")

    canonical = read_csv(CANONICAL)
    reviewed_ids, reviewed_urls, exclusion_counts = reviewed_exclusions(canonical)
    frame = [
        row
        for row in canonical
        if row["event_id"] not in reviewed_ids and not (event_urls(row) & reviewed_urls)
    ]
    selected, sizes, allocation = stratified_select(
        frame, stratum, SAMPLE_ROWS, MIN_PER_STRATUM, SEED
    )

    labels: list[dict[str, str]] = []
    readings: list[dict[str, str]] = []
    unavailable_articles = 0
    with sqlite3.connect(DATABASE) as connection:
        for number, row in enumerate(selected, start=1):
            claims = claim_row(row, f"V8F-{number:03d}")
            labels.append({**claims, **{column: "" for column in LABEL_COLUMNS}})
            evidence, unavailable = load_article_evidence(connection, row)
            unavailable_articles += unavailable
            readings.append({**claims, "article_evidence": evidence})

    weights = []
    for label, row in zip(labels, selected, strict=True):
        key = stratum(row)
        sample_n = allocation[key]
        weights.append(
            {
                "row_id": label["row_id"],
                "event_id": row["event_id"],
                "stratum": key,
                "population_n": sizes[key],
                "sample_n": sample_n,
                "inclusion_probability": round(sample_n / sizes[key], 10),
                "sampling_weight": round(sizes[key] / sample_n, 10),
            }
        )

    write_csv(LABELS, labels, (*CLAIM_COLUMNS, *LABEL_COLUMNS))
    write_csv(READING, readings, (*CLAIM_COLUMNS, "article_evidence"))
    write_csv(
        WEIGHTS,
        weights,
        (
            "row_id",
            "event_id",
            "stratum",
            "population_n",
            "sample_n",
            "inclusion_probability",
            "sampling_weight",
        ),
    )

    reviewed_paths = [OUTPUT / name for name in REVIEWED_FILES]
    input_paths = [
        CANONICAL,
        RELEASE_MANIFEST,
        DATABASE,
        DRAW_SCRIPT,
        SCORER_SCRIPT,
        *reviewed_paths,
    ]
    for release_path, audit_path in HISTORICAL_AUDITS:
        input_paths.extend((release_path, audit_path))
    unique_inputs = list(dict.fromkeys(input_paths))
    manifest = {
        "audit": "v08_fresh_locked_validation_v1",
        "inventory_release": RELEASE_ID,
        "canonical_rows": len(canonical),
        "canonical_sha256": sha256(CANONICAL),
        "seed": SEED,
        "eligible_frame_rows": len(frame),
        "sample_rows": len(selected),
        "reviewed_event_ids_excluded": len(reviewed_ids),
        "reviewed_article_urls_excluded": len(reviewed_urls),
        "exclusion_sources": exclusion_counts,
        "stratification": ["title_language", "period", "event_type", "article_support"],
        "population_by_stratum": dict(sorted(sizes.items())),
        "sample_by_stratum": dict(sorted(Counter(stratum(row) for row in selected).items())),
        "evidence_unavailable_article_count": unavailable_articles,
        "blinding": (
            "prior labels, scores, confidence, parser, scope, and correction fields are omitted"
        ),
        "promotion_rule_prespecified": PROMOTION_RULE,
        "outputs": {path.name: sha256(path) for path in (LABELS, READING, WEIGHTS)},
        "inputs": {str(path.relative_to(ROOT)): sha256(path) for path in unique_inputs},
    }
    MANIFEST.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"Wrote {len(labels)} locked fresh rows from an eligible frame of {len(frame)}")
    print(f"Excluded {len(reviewed_ids)} reviewed event IDs and {len(reviewed_urls)} reviewed URLs")
    print(f"Evidence unavailable for {unavailable_articles} sampled article(s)")
    print(f"Wrote {LABELS}")
    print(f"Wrote {MANIFEST}")


if __name__ == "__main__":
    main()
