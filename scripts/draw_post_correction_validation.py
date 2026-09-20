#!/usr/bin/env python3
"""Draw locked fresh and correction-challenge samples from the v0.7 candidate."""

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
RELEASE_ID = "nepal_landslide_inventory_v0.7.0_candidate_20260916"
RELEASE_DIR = ROOT / "data" / "releases" / RELEASE_ID
CANONICAL = RELEASE_DIR / "canonical_events_final.csv"
CORRECTION_LOG = RELEASE_DIR / "correction_application_log.csv"
DATABASE = ROOT / "data" / "raw_sqlite" / "landslide_inventory.sqlite"
PRIOR_RELEASE = (
    ROOT
    / "data"
    / "releases"
    / "nepal_landslide_inventory_v0.6.0_v7_20260915"
    / "canonical_events_final.csv"
)
PRIOR_AUDIT = OUTPUT / "canonical_event_audit_LABEL_HERE.csv"

FRESH_LABELS = OUTPUT / "post_correction_fresh_audit_LABEL_HERE.csv"
FRESH_READING = OUTPUT / "post_correction_fresh_audit_reading_pack.csv"
FRESH_WEIGHTS = OUTPUT / "post_correction_fresh_audit_weights.csv"
CHALLENGE_LABELS = OUTPUT / "post_correction_challenge_LABEL_HERE.csv"
CHALLENGE_READING = OUTPUT / "post_correction_challenge_reading_pack.csv"
MANIFEST = OUTPUT / "post_correction_validation_manifest.json"

FRESH_ROWS = 150
CHALLENGE_ROWS = 50
SEED = 20260920
MIN_PER_FRESH_STRATUM = 3
MIN_PER_CHALLENGE_STRATUM = 5
CANONICAL_SHA256 = "182071353abd87fed8404d0ae82b172b64d410599bf6e36a532c363cb6fdf663"

CLAIM_COLUMNS = (
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
    with path.open(encoding="utf-8-sig", newline="") as handle:
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


def title_language(title: str) -> str:
    return "np" if any("\u0900" <= char <= "\u097f" for char in title) else "en"


def period(event_date: str) -> str:
    year = int(event_date[:4])
    if year <= 2018:
        return "2015-2018"
    if year <= 2022:
        return "2019-2022"
    return "2023-2026"


def fresh_stratum(row: dict[str, str]) -> str:
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
    if sum(min(size, minimum) for size in sizes.values()) > total:
        raise ValueError("Minimum allocations exceed the requested sample")
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


def stratified_select(
    rows: list[dict[str, str]],
    key_fn: Any,
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
        candidates = sorted(groups[key], key=lambda row: row["event_id"])
        random.Random(seed + index).shuffle(candidates)
        selected.extend(candidates[: allocation[key]])
    random.Random(seed + 10_000).shuffle(selected)
    return selected, sizes, allocation


def prior_audit_exclusions(
    prior_rows: list[dict[str, str]], prior_audit: list[dict[str, str]]
) -> tuple[set[str], set[str]]:
    by_id = {row["event_id"]: row for row in prior_rows}
    event_ids = {row["event_id"] for row in prior_audit}
    missing = event_ids - set(by_id)
    if missing:
        raise ValueError(
            f"Prior audit IDs are absent from the frozen release: {sorted(missing)[:3]}"
        )
    urls = set().union(*(event_urls(by_id[event_id]) for event_id in event_ids))
    return event_ids, urls


def correction_category(log_row: dict[str, str]) -> str | None:
    action = log_row["action"]
    if action == "add_reconstructed":
        return "identity_add"
    if action == "merge_into_existing":
        return "identity_merge"
    if action == "correct_attributes":
        return f"{log_row['layer']}_correction"
    return None


def correction_frame(
    canonical: list[dict[str, str]], log_rows: list[dict[str, str]]
) -> list[dict[str, str]]:
    by_id = {row["event_id"]: row for row in canonical}
    categories: dict[str, str] = {}
    for log_row in log_rows:
        category = correction_category(log_row)
        if category is None:
            continue
        event_id = log_row["event_id"]
        if event_id in categories:
            raise ValueError(f"Corrected event appears in multiple challenge strata: {event_id}")
        if event_id not in by_id:
            raise ValueError(f"Correction challenge event is absent from candidate: {event_id}")
        categories[event_id] = category
    return [
        {**by_id[event_id], "_correction_layer": category}
        for event_id, category in categories.items()
    ]


def event_evidence(row: dict[str, str]) -> str:
    payload = parse_payload(row)
    reconstruction = payload.get("manual_reconstruction")
    if isinstance(reconstruction, dict):
        return str(reconstruction.get("evidence") or "")
    merges = payload.get("manual_identity_merges")
    if isinstance(merges, list):
        return " | ".join(
            str(item.get("evidence") or "") for item in merges if isinstance(item, dict)
        )
    return ""


def claim_row(
    row: dict[str, str], row_id: str, sample_role: str, correction_layer: str = ""
) -> dict[str, str]:
    return {
        "row_id": row_id,
        "sample_role": sample_role,
        "correction_layer": correction_layer,
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
        "event_evidence": event_evidence(row),
    }


def load_article_evidence(connection: sqlite3.Connection, row: dict[str, str]) -> str:
    sections: list[str] = []
    for index, url in enumerate(sorted(event_urls(row)), start=1):
        article = connection.execute(
            "SELECT source, title, published_date_ad, text FROM raw_articles WHERE url = ?",
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


def build_review_rows(
    selected: list[dict[str, str]], prefix: str, role: str, connection: sqlite3.Connection
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    labels: list[dict[str, str]] = []
    readings: list[dict[str, str]] = []
    for number, row in enumerate(selected, start=1):
        row_id = f"{prefix}-{number:03d}"
        claims = claim_row(row, row_id, role, row.get("_correction_layer", ""))
        labels.append({**claims, **{column: "" for column in LABEL_COLUMNS}})
        readings.append({**claims, "article_evidence": load_article_evidence(connection, row)})
    return labels, readings


def main() -> None:
    if sha256(CANONICAL) != CANONICAL_SHA256:
        raise RuntimeError("Candidate canonical CSV differs from the locked v0.7 candidate")
    canonical = read_csv(CANONICAL)
    prior_ids, prior_urls = prior_audit_exclusions(read_csv(PRIOR_RELEASE), read_csv(PRIOR_AUDIT))
    challenge_frame = correction_frame(canonical, read_csv(CORRECTION_LOG))
    challenge_ids = {row["event_id"] for row in challenge_frame}
    fresh_frame = [
        row
        for row in canonical
        if row["event_id"] not in prior_ids
        and row["event_id"] not in challenge_ids
        and not (event_urls(row) & prior_urls)
    ]
    fresh, fresh_sizes, fresh_allocation = stratified_select(
        fresh_frame, fresh_stratum, FRESH_ROWS, MIN_PER_FRESH_STRATUM, SEED
    )
    challenge, challenge_sizes, challenge_allocation = stratified_select(
        challenge_frame,
        lambda row: row["_correction_layer"],
        CHALLENGE_ROWS,
        MIN_PER_CHALLENGE_STRATUM,
        SEED + 50_000,
    )
    if {row["event_id"] for row in fresh} & {row["event_id"] for row in challenge}:
        raise ValueError("Fresh and correction-challenge samples overlap")

    with sqlite3.connect(DATABASE) as connection:
        fresh_labels, fresh_reading = build_review_rows(
            fresh, "PCF", "fresh_probability", connection
        )
        challenge_labels, challenge_reading = build_review_rows(
            challenge, "PCC", "correction_challenge", connection
        )

    weights = []
    for label, row in zip(fresh_labels, fresh, strict=True):
        key = fresh_stratum(row)
        sample_n = fresh_allocation[key]
        weights.append(
            {
                "row_id": label["row_id"],
                "event_id": row["event_id"],
                "stratum": key,
                "population_n": fresh_sizes[key],
                "sample_n": sample_n,
                "inclusion_probability": round(sample_n / fresh_sizes[key], 10),
                "sampling_weight": round(fresh_sizes[key] / sample_n, 10),
            }
        )

    write_csv(FRESH_LABELS, fresh_labels, [*CLAIM_COLUMNS, *LABEL_COLUMNS])
    write_csv(FRESH_READING, fresh_reading, [*CLAIM_COLUMNS, "article_evidence"])
    write_csv(
        FRESH_WEIGHTS,
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
    write_csv(CHALLENGE_LABELS, challenge_labels, [*CLAIM_COLUMNS, *LABEL_COLUMNS])
    write_csv(CHALLENGE_READING, challenge_reading, [*CLAIM_COLUMNS, "article_evidence"])

    manifest = {
        "audit": "post_correction_candidate_validation_v1",
        "inventory_release": RELEASE_ID,
        "canonical_rows": len(canonical),
        "canonical_sha256": sha256(CANONICAL),
        "seed": SEED,
        "fresh_probability_sample": {
            "purpose": "precision and attribute accuracy on untouched candidate events",
            "eligible_frame_rows": len(fresh_frame),
            "sample_rows": len(fresh),
            "prior_audit_event_ids_excluded": len(prior_ids),
            "prior_audit_article_urls_excluded": len(prior_urls),
            "correction_touched_event_ids_excluded": len(challenge_ids),
            "stratification": [
                "title_language",
                "period",
                "event_type",
                "article_support",
            ],
            "population_by_stratum": dict(sorted(fresh_sizes.items())),
            "sample_by_stratum": dict(sorted(Counter(fresh_stratum(row) for row in fresh).items())),
        },
        "correction_challenge_sample": {
            "purpose": (
                "targeted verification of applied corrections; not an overall precision sample"
            ),
            "eligible_frame_rows": len(challenge_frame),
            "sample_rows": len(challenge),
            "population_by_action": dict(sorted(challenge_sizes.items())),
            "sample_by_action": dict(
                sorted(Counter(row["_correction_layer"] for row in challenge).items())
            ),
        },
        "blinding": (
            "prior labels, scores, confidence, specificity, scope, and location-consistency "
            "fields are omitted"
        ),
        "outputs": {
            path.name: sha256(path)
            for path in (
                FRESH_LABELS,
                FRESH_READING,
                FRESH_WEIGHTS,
                CHALLENGE_LABELS,
                CHALLENGE_READING,
            )
        },
        "inputs": {
            str(PRIOR_RELEASE.relative_to(ROOT)): sha256(PRIOR_RELEASE),
            str(PRIOR_AUDIT.relative_to(ROOT)): sha256(PRIOR_AUDIT),
            str(CORRECTION_LOG.relative_to(ROOT)): sha256(CORRECTION_LOG),
        },
        "scoring_rule": "fresh and correction-challenge samples must be reported separately",
    }
    MANIFEST.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(fresh_labels)} fresh rows to {FRESH_LABELS}")
    print(f"Wrote {len(challenge_labels)} correction-challenge rows to {CHALLENGE_LABELS}")
    print(f"Wrote manifest to {MANIFEST}")


if __name__ == "__main__":
    main()
