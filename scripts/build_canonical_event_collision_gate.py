#!/usr/bin/env python3
"""Build date-resolution and frozen-inventory collision review packs."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "outputs"
RELEASE_DIR = ROOT / "data" / "releases" / "nepal_landslide_inventory_v0.6.0_v7_20260915"
GROUPS = OUTPUT / "canonical_event_reconstruction_GROUPS.csv"
RECONSTRUCTION_MANIFEST = OUTPUT / "canonical_event_reconstruction_manifest.json"
COMPLETED_DECISIONS = OUTPUT / "canonical_event_article_mapping_DECISIONS_COMPLETED.csv"
ARTICLE_MAP = OUTPUT / "canonical_event_article_membership_MAP.csv"
FROZEN_CANONICAL = RELEASE_DIR / "canonical_events_final.csv"
RELEASE_MANIFEST = RELEASE_DIR / "release_manifest.json"
DATE_REVIEW = OUTPUT / "canonical_event_reconstruction_DATE_REVIEW.csv"
COLLISION_PAIRS = OUTPUT / "canonical_event_reconstruction_COLLISION_PAIRS.csv"
COLLISION_DECISIONS = OUTPUT / "canonical_event_reconstruction_COLLISION_DECISIONS.csv"
MANIFEST_OUTPUT = OUTPUT / "canonical_event_collision_gate_manifest.json"
REPORT_OUTPUT = OUTPUT / "canonical_event_collision_gate_report.md"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]], columns: list[str]) -> None:
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
    return " ".join((value or "").strip().casefold().split())


def parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def urls(row: dict[str, str]) -> set[str]:
    if "article_urls_json" in row:
        return set(json.loads(row["article_urls_json"]))
    payload = json.loads(row["event_payload"])
    values = payload.get("urls", [])
    if not values and row.get("representative_url"):
        values = [row["representative_url"]]
    return {str(value) for value in values}


def compare(candidate: dict[str, str], existing: dict[str, str]) -> dict[str, object] | None:
    candidate_urls = urls(candidate)
    existing_urls = urls(existing)
    overlap = sorted(candidate_urls & existing_urls)
    candidate_date = parse_date(candidate["event_date"])
    existing_date = parse_date(existing["event_date_ad"])
    same_district = normalize(candidate["district"]) == normalize(existing["district"])
    if candidate_date is None or existing_date is None:
        day_diff = None
    else:
        day_diff = abs((candidate_date - existing_date).days)
    if not overlap and (not same_district or day_diff is None or day_diff > 7):
        return None

    score = 0.0
    reasons: list[str] = []
    if overlap:
        score += 100
        reasons.append("source_url_overlap")
    if same_district:
        score += 5
        reasons.append("same_district")
    if day_diff == 0:
        score += 20
        reasons.append("same_date")
    elif day_diff is not None and day_diff <= 1:
        score += 15
        reasons.append("date_within_1_day")
    elif day_diff is not None and day_diff <= 3:
        score += 10
        reasons.append("date_within_3_days")
    elif day_diff is not None and day_diff <= 7:
        score += 5
        reasons.append("date_within_7_days")
    candidate_municipality = normalize(candidate["municipality"])
    existing_municipality = normalize(existing["municipality"])
    if candidate_municipality and candidate_municipality == existing_municipality:
        score += 8
        reasons.append("same_municipality")
    if normalize(candidate["event_type"]) == normalize(existing["event_type"]):
        score += 2
        reasons.append("same_event_type")
    if normalize(candidate["hazard_type"]) == normalize(existing["hazard_type"]):
        score += 1
        reasons.append("same_hazard_type")
    title_similarity = SequenceMatcher(
        None, normalize(candidate["evidence"]), normalize(existing["representative_title"])
    ).ratio()
    score += 5 * title_similarity
    if title_similarity >= 0.45:
        reasons.append("text_similarity")

    if overlap or (day_diff == 0 and "same_municipality" in reasons):
        tier = "high"
    elif day_diff == 0 or (day_diff is not None and day_diff <= 1 and "same_municipality" in reasons):
        tier = "medium"
    else:
        tier = "low"
    return {
        "collision_score": round(score, 6),
        "collision_tier": tier,
        "day_difference": "" if day_diff is None else day_diff,
        "reasons": ";".join(reasons),
        "overlapping_urls_json": json.dumps(overlap, ensure_ascii=False),
    }


def build_date_review(
    groups: list[dict[str, str]], mapping_by_id: dict[str, dict[str, str]]
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for group in groups:
        if parse_date(group["event_date"]) is not None:
            continue
        mapping_ids = json.loads(group["article_mapping_ids_json"])
        evidence_parts = []
        for mapping_id in mapping_ids:
            source = mapping_by_id[mapping_id]
            evidence_parts.append(
                f"{mapping_id}\nTITLE: {source['title']}\n"
                f"PUBLISHED: {source['published_date_ad']}\nTEXT:\n{source['article_text']}"
            )
        rows.append(
            {
                "candidate_event_id": group["candidate_event_id"],
                "candidate_id": group["candidate_id"],
                "old_event_id": group["old_event_id"],
                "district": group["district"],
                "municipality": group["municipality"],
                "event_type": group["event_type"],
                "hazard_type": group["hazard_type"],
                "deaths": group["deaths"],
                "article_mapping_ids_json": group["article_mapping_ids_json"],
                "article_urls_json": group["article_urls_json"],
                "event_evidence": group["evidence"],
                "source_evidence": "\n\n---\n\n".join(evidence_parts),
                "final_action": "",
                "resolved_event_date": "",
                "reviewed_by": "",
                "review_notes": "",
            }
        )
    return rows


def main() -> None:
    reconstruction = json.loads(RECONSTRUCTION_MANIFEST.read_text(encoding="utf-8"))
    if sha256(GROUPS) != reconstruction["outputs"][GROUPS.name]:
        raise ValueError("Reconstruction groups differ from their manifest.")
    release = json.loads(RELEASE_MANIFEST.read_text(encoding="utf-8"))
    frozen_hash = next(
        item["sha256"] for item in release["files"] if item["file"] == FROZEN_CANONICAL.name
    )
    if sha256(FROZEN_CANONICAL) != frozen_hash:
        raise ValueError("Frozen canonical CSV differs from its release manifest.")

    groups = read_csv(GROUPS)
    decisions = read_csv(COMPLETED_DECISIONS)
    old_event_ids = {row["event_id"] for row in decisions}
    unaffected = [row for row in read_csv(FROZEN_CANONICAL) if row["event_id"] not in old_event_ids]
    mapping_by_id = {row["mapping_id"]: row for row in read_csv(ARTICLE_MAP)}
    date_review = build_date_review(groups, mapping_by_id)
    write_csv(DATE_REVIEW, date_review, list(date_review[0]))

    pair_rows: list[dict[str, object]] = []
    pairs_by_candidate: dict[str, list[dict[str, object]]] = defaultdict(list)
    for candidate in groups:
        if parse_date(candidate["event_date"]) is None:
            continue
        for existing in unaffected:
            comparison = compare(candidate, existing)
            if comparison is None:
                continue
            pair = {
                "candidate_event_id": candidate["candidate_event_id"],
                "candidate_date": candidate["event_date"],
                "candidate_district": candidate["district"],
                "candidate_municipality": candidate["municipality"],
                "candidate_event_type": candidate["event_type"],
                "candidate_hazard_type": candidate["hazard_type"],
                "candidate_evidence": candidate["evidence"],
                "existing_event_id": existing["event_id"],
                "existing_date": existing["event_date_ad"],
                "existing_district": existing["district"],
                "existing_municipality": existing["municipality"],
                "existing_event_type": existing["event_type"],
                "existing_hazard_type": existing["hazard_type"],
                "existing_title": existing["representative_title"],
                "existing_url": existing["representative_url"],
                **comparison,
            }
            pair_rows.append(pair)
            pairs_by_candidate[candidate["candidate_event_id"]].append(pair)
    pair_rows.sort(key=lambda row: (str(row["candidate_event_id"]), -float(row["collision_score"]), str(row["existing_event_id"])))
    pair_columns = list(pair_rows[0]) if pair_rows else ["candidate_event_id"]
    write_csv(COLLISION_PAIRS, pair_rows, pair_columns)

    decision_rows: list[dict[str, object]] = []
    for candidate in groups:
        matches = sorted(
            pairs_by_candidate.get(candidate["candidate_event_id"], []),
            key=lambda row: (-float(row["collision_score"]), str(row["existing_event_id"])),
        )
        compact = [
            {
                "existing_event_id": row["existing_event_id"],
                "date": row["existing_date"],
                "district": row["existing_district"],
                "municipality": row["existing_municipality"],
                "title": row["existing_title"],
                "url": row["existing_url"],
                "score": row["collision_score"],
                "tier": row["collision_tier"],
                "reasons": row["reasons"],
            }
            for row in matches[:10]
        ]
        known_date = parse_date(candidate["event_date"]) is not None
        if not known_date:
            proposed_action = "resolve_date_first"
        elif any(row["collision_tier"] in {"high", "medium"} for row in matches):
            proposed_action = "review_possible_collision"
        elif matches:
            proposed_action = "likely_new_event_low_tier_matches"
        else:
            proposed_action = "new_event_no_candidate_collision"
        decision_rows.append(
            {
                **candidate,
                "collision_gate_status": "review_ready" if known_date else "blocked_on_date_review",
                "proposed_collision_action": proposed_action,
                "collision_candidate_count": len(matches),
                "high_collision_count": sum(row["collision_tier"] == "high" for row in matches),
                "medium_collision_count": sum(row["collision_tier"] == "medium" for row in matches),
                "top_collision_candidates_json": json.dumps(compact, ensure_ascii=False),
                "final_collision_action": "",
                "merge_target_event_id": "",
                "reviewed_by_collision": "",
                "collision_review_notes": "",
            }
        )
    write_csv(COLLISION_DECISIONS, decision_rows, list(decision_rows[0]))

    tier_counts = Counter(row["collision_tier"] for row in pair_rows)
    candidates_with_pairs = len(pairs_by_candidate)
    manifest = {
        "reconstruction_candidates": len(groups),
        "unaffected_frozen_events": len(unaffected),
        "date_review_rows": len(date_review),
        "dated_candidates_screened": len(groups) - len(date_review),
        "candidates_with_collision_pairs": candidates_with_pairs,
        "collision_pairs": len(pair_rows),
        "collision_pair_tiers": dict(tier_counts),
        "inputs": {
            GROUPS.name: sha256(GROUPS),
            RECONSTRUCTION_MANIFEST.name: sha256(RECONSTRUCTION_MANIFEST),
            COMPLETED_DECISIONS.name: sha256(COMPLETED_DECISIONS),
            ARTICLE_MAP.name: sha256(ARTICLE_MAP),
            str(FROZEN_CANONICAL.relative_to(ROOT)): sha256(FROZEN_CANONICAL),
        },
        "outputs": {
            DATE_REVIEW.name: sha256(DATE_REVIEW),
            COLLISION_PAIRS.name: sha256(COLLISION_PAIRS),
            COLLISION_DECISIONS.name: sha256(COLLISION_DECISIONS),
        },
        "status": "review_packs_only_no_production_changes",
    }
    MANIFEST_OUTPUT.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    REPORT_OUTPUT.write_text(
        "\n".join(
            [
                "# Canonical event reconstruction collision gate",
                "",
                f"Reconstruction candidates: {len(groups)}",
                f"Unclear-date candidates: {len(date_review)}",
                f"Dated candidates screened: {len(groups) - len(date_review)}",
                f"Candidates with at least one collision pair: {candidates_with_pairs}",
                f"Collision pairs: {len(pair_rows)}",
                f"High-tier pairs: {tier_counts.get('high', 0)}",
                f"Medium-tier pairs: {tier_counts.get('medium', 0)}",
                f"Low-tier pairs: {tier_counts.get('low', 0)}",
                "",
                "No collision has been merged automatically. Unclear-date candidates are",
                "blocked until the separate date review is completed.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"Wrote {len(date_review)} rows to {DATE_REVIEW}")
    print(f"Wrote {len(pair_rows)} pairs to {COLLISION_PAIRS}")
    print(f"Wrote {len(decision_rows)} rows to {COLLISION_DECISIONS}")
    print(f"Wrote {MANIFEST_OUTPUT}")
    print(f"Wrote {REPORT_OUTPUT}")


if __name__ == "__main__":
    main()
