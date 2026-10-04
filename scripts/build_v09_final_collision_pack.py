#!/usr/bin/env python3
"""Build the final v0.9 candidate-to-candidate identity collision pack."""

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
CANDIDATES = OUTPUT / "v09_existing_collision_NEW_CANDIDATES.csv"
OUTCOME_MANIFEST = OUTPUT / "v09_existing_collision_outcomes_manifest.json"
PAIRS = OUTPUT / "v09_reconstruction_FINAL_COLLISION_PAIRS.csv"
DECISIONS = OUTPUT / "v09_reconstruction_FINAL_COLLISION_DECISIONS.csv"
MANIFEST = OUTPUT / "v09_final_collision_manifest.json"
REPORT = OUTPUT / "v09_final_collision_report.md"
SCRIPT_PATH = Path(__file__).resolve()
AUDIT_NAME = "v09_candidate_to_candidate_collision_v1"
REPORT_TITLE = "Final v0.9 candidate collision screen"


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


def compare(first: dict[str, str], second: dict[str, str]) -> dict[str, Any] | None:
    first_urls = set(json.loads(first["article_urls_json"]))
    second_urls = set(json.loads(second["article_urls_json"]))
    overlap = sorted(first_urls & second_urls)
    same_district = normalize(first["district"]) == normalize(second["district"])
    first_date = parse_date(first["event_date"])
    second_date = parse_date(second["event_date"])
    day_diff = (
        None
        if first_date is None or second_date is None
        else abs((first_date - second_date).days)
    )
    same_old = first["old_event_id"] == second["old_event_id"]
    if not overlap and not same_old and (
        not same_district or day_diff is None or day_diff > 3
    ):
        return None
    same_municipality = bool(normalize(first["municipality"])) and normalize(
        first["municipality"]
    ) == normalize(second["municipality"])
    similarity = SequenceMatcher(
        None, normalize(first["evidence"]), normalize(second["evidence"])
    ).ratio()
    score = 0.0
    reasons: list[str] = []
    if overlap:
        score += 3
        reasons.append("source_url_overlap_expected_for_decomposition")
    if same_district:
        score += 5
        reasons.append("same_district")
    if day_diff is None:
        reasons.append("unresolved_date")
    elif day_diff == 0:
        score += 20
        reasons.append("same_date")
    elif day_diff <= 1:
        score += 15
        reasons.append("date_within_1_day")
    else:
        score += 10
        reasons.append("date_within_3_days")
    if same_municipality:
        score += 8
        reasons.append("same_municipality")
    if normalize(first["event_type"]) == normalize(second["event_type"]):
        score += 2
        reasons.append("same_event_type")
    if normalize(first["hazard_type"]) == normalize(second["hazard_type"]):
        score += 1
        reasons.append("same_hazard_type")
    score += 10 * similarity
    if similarity >= 0.45:
        reasons.append("evidence_similarity")
    if same_old:
        reasons.append("same_reconstruction_source")
    if day_diff == 0 and same_municipality and similarity >= 0.45:
        tier = "high"
    elif day_diff == 0 and same_district and similarity >= 0.25:
        tier = "medium"
    else:
        tier = "low"
    return {
        "collision_score": round(score, 6),
        "collision_tier": tier,
        "day_difference": "" if day_diff is None else day_diff,
        "evidence_similarity": round(similarity, 6),
        "same_old_event": str(same_old).lower(),
        "overlapping_urls_json": json.dumps(overlap, ensure_ascii=False),
        "reasons": ";".join(reasons),
    }


def build_pairs(candidates: list[dict[str, str]]) -> list[dict[str, Any]]:
    pairs: list[dict[str, Any]] = []
    for index, first in enumerate(candidates):
        for second in candidates[index + 1 :]:
            comparison = compare(first, second)
            if comparison is None:
                continue
            pairs.append(
                {
                    "candidate_event_id_a": first["candidate_event_id"],
                    "candidate_event_id_b": second["candidate_event_id"],
                    "date_a": first["event_date"],
                    "date_b": second["event_date"],
                    "district_a": first["district"],
                    "district_b": second["district"],
                    "municipality_a": first["municipality"],
                    "municipality_b": second["municipality"],
                    "evidence_a": first["evidence"],
                    "evidence_b": second["evidence"],
                    **comparison,
                }
            )
    return sorted(
        pairs,
        key=lambda row: (
            str(row["candidate_event_id_a"]),
            -float(row["collision_score"]),
            str(row["candidate_event_id_b"]),
        ),
    )


def build_decisions(
    candidates: list[dict[str, str]], pairs: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    matches: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for pair in pairs:
        for current, other in (
            (pair["candidate_event_id_a"], pair["candidate_event_id_b"]),
            (pair["candidate_event_id_b"], pair["candidate_event_id_a"]),
        ):
            matches[str(current)].append(
                {
                    "candidate_event_id": other,
                    "score": pair["collision_score"],
                    "tier": pair["collision_tier"],
                    "reasons": pair["reasons"],
                }
            )
    rows: list[dict[str, Any]] = []
    for candidate in candidates:
        candidate_matches = sorted(
            matches.get(candidate["candidate_event_id"], []),
            key=lambda row: (-float(row["score"]), str(row["candidate_event_id"])),
        )
        top_tier = candidate_matches[0]["tier"] if candidate_matches else "none"
        proposed = (
            "review_candidate_collision"
            if top_tier in {"high", "medium"}
            else "likely_distinct_candidate"
            if candidate_matches
            else "new_event_no_candidate_match"
        )
        rows.append(
            {
                **candidate,
                "candidate_match_count": len(candidate_matches),
                "top_candidate_collision_tier": top_tier,
                "candidate_matches_json": json.dumps(candidate_matches[:10]),
                "proposed_final_action": proposed,
                "final_candidate_action": "",
                "merge_candidate_event_id": "",
                "reviewed_by_final": "",
                "final_collision_notes": "",
            }
        )
    return rows


def main() -> int:
    outcome = json.loads(OUTCOME_MANIFEST.read_text(encoding="utf-8"))
    if sha256(CANDIDATES) != outcome["output_sha256"][CANDIDATES.name]:
        raise ValueError("New candidates differ from existing-collision outcome manifest")
    candidates = read_csv(CANDIDATES)
    pairs = build_pairs(candidates)
    decisions = build_decisions(candidates, pairs)
    write_csv(PAIRS, pairs, list(pairs[0]) if pairs else ["candidate_event_id_a"])
    write_csv(DECISIONS, decisions, list(decisions[0]))
    tiers = Counter(str(row["top_candidate_collision_tier"]) for row in decisions)
    proposed = Counter(str(row["proposed_final_action"]) for row in decisions)
    input_paths = (CANDIDATES, OUTCOME_MANIFEST, SCRIPT_PATH)
    manifest = {
        "audit": AUDIT_NAME,
        "candidate_rows": len(candidates),
        "candidate_pairs": len(pairs),
        "top_tier_counts": dict(tiers),
        "proposed_action_counts": dict(proposed),
        "input_sha256": {str(path.relative_to(ROOT)): sha256(path) for path in input_paths},
        "output_sha256": {path.name: sha256(path) for path in (PAIRS, DECISIONS)},
        "status": "final_candidate_collision_template_no_production_changes",
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    REPORT.write_text(
        "\n".join(
            [
                f"# {REPORT_TITLE}",
                "",
                f"Eligible proposed new events: {len(candidates)}",
                f"Candidate-candidate pairs: {len(pairs)}",
                f"High-tier candidates: {tiers['high']}",
                f"Medium-tier candidates: {tiers['medium']}",
                f"Low-tier candidates: {tiers['low']}",
                f"Candidates with no pair: {tiers['none']}",
                "",
                "No identity decision has been applied.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"Wrote {len(pairs)} candidate pairs to {PAIRS}")
    print(f"Wrote {len(decisions)} final decisions to {DECISIONS}")
    print(f"Wrote {MANIFEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
