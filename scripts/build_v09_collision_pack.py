#!/usr/bin/env python3
"""Build existing-event collision evidence for v0.9 reconstruction candidates."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "outputs"
RELEASE_DIR = ROOT / "data/releases/nepal_landslide_inventory_v0.8.0_candidate_20260923"
CANONICAL = RELEASE_DIR / "canonical_events_final.csv"
RELEASE_MANIFEST = RELEASE_DIR / "release_manifest.json"
GROUPS = OUTPUT / "v09_reconstruction_GROUPS.csv"
RECONSTRUCTION_MANIFEST = OUTPUT / "v09_reconstruction_manifest.json"
MAPPING_DECISIONS = OUTPUT / "v09_article_mapping_DECISIONS_COMPLETED.csv"
MAPPING_VALIDATION = OUTPUT / "v09_article_mapping_validation.json"
COLLISION_PAIRS = OUTPUT / "v09_reconstruction_COLLISION_PAIRS.csv"
COLLISION_DECISIONS = OUTPUT / "v09_reconstruction_COLLISION_DECISIONS.csv"
MANIFEST_OUTPUT = OUTPUT / "v09_collision_manifest.json"
REPORT_OUTPUT = OUTPUT / "v09_collision_report.md"
SCRIPT_PATH = Path(__file__).resolve()
AUDIT_NAME = "v09_existing_event_collision_v1"
REPORT_TITLE = "v0.9 existing-event collision screen"
RELEASE_LABEL = "v0.8 candidate"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
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


def compare(candidate: dict[str, str], existing: dict[str, str]) -> dict[str, Any] | None:
    overlap = sorted(urls(candidate) & urls(existing))
    candidate_date = parse_date(candidate["event_date"])
    existing_date = parse_date(existing["event_date_ad"])
    same_district = normalize(candidate["district"]) == normalize(existing["district"])
    day_diff = (
        None
        if candidate_date is None or existing_date is None
        else abs((candidate_date - existing_date).days)
    )
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
    similarity = SequenceMatcher(
        None, normalize(candidate["evidence"]), normalize(existing["representative_title"])
    ).ratio()
    score += 5 * similarity
    if similarity >= 0.45:
        reasons.append("text_similarity")

    if overlap or (day_diff == 0 and "same_municipality" in reasons):
        tier = "high"
    elif day_diff == 0 or (
        day_diff is not None and day_diff <= 1 and "same_municipality" in reasons
    ):
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


def build_pairs(
    candidates: list[dict[str, str]], unaffected: list[dict[str, str]]
) -> list[dict[str, Any]]:
    pairs: list[dict[str, Any]] = []
    for candidate in candidates:
        for existing in unaffected:
            comparison = compare(candidate, existing)
            if comparison is None:
                continue
            pairs.append(
                {
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
            )
    return sorted(
        pairs,
        key=lambda row: (
            str(row["candidate_event_id"]),
            -float(row["collision_score"]),
            str(row["existing_event_id"]),
        ),
    )


def build_decisions(
    candidates: list[dict[str, str]], pairs: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    by_candidate: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for pair in pairs:
        by_candidate[str(pair["candidate_event_id"])].append(pair)
    rows: list[dict[str, Any]] = []
    for candidate in candidates:
        matches = by_candidate.get(candidate["candidate_event_id"], [])
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
        if any(row["collision_tier"] in {"high", "medium"} for row in matches):
            proposed = "review_possible_collision"
        elif matches:
            proposed = "likely_new_event_low_tier_matches"
        else:
            proposed = "new_event_no_candidate_collision"
        rows.append(
            {
                **candidate,
                "collision_match_count": len(matches),
                "top_collision_tier": matches[0]["collision_tier"] if matches else "none",
                "top_collision_score": matches[0]["collision_score"] if matches else "",
                "candidate_matches_json": json.dumps(compact, ensure_ascii=False),
                "proposed_action": proposed,
                "final_action": "",
                "merge_existing_event_id": "",
                "reviewed_by": "",
                "collision_review_notes": "",
            }
        )
    return rows


def verify_inputs() -> None:
    reconstruction = json.loads(RECONSTRUCTION_MANIFEST.read_text(encoding="utf-8"))
    if sha256(GROUPS) != reconstruction["output_sha256"][GROUPS.name]:
        raise ValueError("Reconstruction groups differ from their manifest")
    validation = json.loads(MAPPING_VALIDATION.read_text(encoding="utf-8"))
    if sha256(MAPPING_DECISIONS) != validation["inputs"][MAPPING_DECISIONS.name]:
        raise ValueError("Mapping decisions differ from validation provenance")
    release = json.loads(RELEASE_MANIFEST.read_text(encoding="utf-8"))
    if sha256(CANONICAL) != release["canonical_summary"]["sha256"]:
        raise ValueError("Candidate canonical CSV differs from release manifest")


def main() -> int:
    verify_inputs()
    candidates = read_csv(GROUPS)
    mapping_decisions = read_csv(MAPPING_DECISIONS)
    superseded = {
        row["event_id"] for row in mapping_decisions if row["final_resolution"] != "unclear"
    }
    canonical = read_csv(CANONICAL)
    if not superseded <= {row["event_id"] for row in canonical}:
        raise ValueError(f"A superseded event is absent from the {RELEASE_LABEL}")
    unaffected = [row for row in canonical if row["event_id"] not in superseded]
    pairs = build_pairs(candidates, unaffected)
    decisions = build_decisions(candidates, pairs)
    write_csv(COLLISION_PAIRS, pairs, list(pairs[0]) if pairs else ["candidate_event_id"])
    write_csv(COLLISION_DECISIONS, decisions, list(decisions[0]))
    proposed_counts = Counter(str(row["proposed_action"]) for row in decisions)
    tier_counts = Counter(str(row["top_collision_tier"]) for row in decisions)
    input_paths = (
        GROUPS,
        RECONSTRUCTION_MANIFEST,
        MAPPING_DECISIONS,
        MAPPING_VALIDATION,
        CANONICAL,
        RELEASE_MANIFEST,
        SCRIPT_PATH,
    )
    manifest = {
        "audit": AUDIT_NAME,
        "candidate_rows": len(candidates),
        "superseded_old_events_removed_from_frame": len(superseded),
        "unaffected_comparison_events": len(unaffected),
        "collision_pairs": len(pairs),
        "proposed_action_counts": dict(proposed_counts),
        "top_tier_counts": dict(tier_counts),
        "status": "collision_review_template_no_production_changes",
        "input_sha256": {str(path.relative_to(ROOT)): sha256(path) for path in input_paths},
        "output_sha256": {
            path.name: sha256(path) for path in (COLLISION_PAIRS, COLLISION_DECISIONS)
        },
    }
    MANIFEST_OUTPUT.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    lines = [
        f"# {REPORT_TITLE}",
        "",
        f"Reconstruction candidates: {len(candidates)}",
        f"Unaffected comparison events: {len(unaffected)}",
        f"Candidate-existing pairs: {len(pairs)}",
        "",
        "| Proposed action | Candidates |",
        "|---|---:|",
    ]
    lines.extend(f"| {name} | {count} |" for name, count in proposed_counts.most_common())
    lines.extend(
        [
            "",
            "This screen applies no merges, exclusions, or insertions. Candidate-to-",
            "candidate collision review remains a separate final identity gate.",
            "",
        ]
    )
    REPORT_OUTPUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {len(pairs)} collision pairs to {COLLISION_PAIRS}")
    print(f"Wrote {len(decisions)} decision rows to {COLLISION_DECISIONS}")
    print(f"Wrote {MANIFEST_OUTPUT}")
    print(f"Wrote {REPORT_OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
