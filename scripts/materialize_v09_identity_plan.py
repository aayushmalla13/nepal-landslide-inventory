#!/usr/bin/env python3
"""Materialize the reviewed v0.9 identity corrections without applying them."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_shared_materializer():
    path = Path(__file__).with_name("materialize_post_correction_identity_plan.py")
    spec = importlib.util.spec_from_file_location("post_correction_identity_shared", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load shared identity materializer: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_shared = _load_shared_materializer()
candidate_base = _shared.candidate_base
materialize = _shared.materialize
read_csv = _shared.read_csv
sha256 = _shared.sha256
write_csv = _shared.write_csv

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "outputs"
SOURCE_RELEASE = ROOT / "data" / "releases" / "nepal_landslide_inventory_v0.8.0_candidate_20260923"
SOURCE_CANONICAL = SOURCE_RELEASE / "canonical_events_final.csv"

FINAL_DECISIONS = OUTPUT / "v09_reconstruction_FINAL_COLLISION_DECISIONS_COMPLETED.csv"
FINAL_VALIDATION = OUTPUT / "v09_final_collision_validation.json"
EXISTING_MANIFEST = OUTPUT / "v09_existing_collision_outcomes_manifest.json"
EXISTING_NEW = OUTPUT / "v09_existing_collision_NEW_CANDIDATES.csv"
EXISTING_MERGES = OUTPUT / "v09_existing_collision_MERGES.csv"
EXISTING_EXCLUDED = OUTPUT / "v09_existing_collision_EXCLUDED.csv"
EXISTING_BLOCKED = OUTPUT / "v09_existing_collision_BLOCKED_CANDIDATES.csv"
MAPPING_DECISIONS = OUTPUT / "v09_article_mapping_DECISIONS_COMPLETED.csv"
EXCLUDED_ARTICLES = OUTPUT / "v09_reconstruction_EXCLUDED_ARTICLES.csv"
RECONSTRUCTION_MANIFEST = OUTPUT / "v09_reconstruction_manifest.json"

PREFIX = "v09_identity_plan"
REMOVE_OUTPUT = OUTPUT / f"{PREFIX}_REMOVE_OLD_EVENTS.csv"
NEW_OUTPUT = OUTPUT / f"{PREFIX}_NEW_EVENTS.csv"
MERGE_EXISTING_OUTPUT = OUTPUT / f"{PREFIX}_MERGES_EXISTING.csv"
MERGE_CANDIDATE_OUTPUT = OUTPUT / f"{PREFIX}_MERGES_CANDIDATES.csv"
EXCLUDE_OUTPUT = OUTPUT / f"{PREFIX}_EXCLUDED_CANDIDATES.csv"
BLOCKED_OUTPUT = OUTPUT / f"{PREFIX}_BLOCKED_CANDIDATES.csv"
RETAINED_OUTPUT = OUTPUT / f"{PREFIX}_RETAINED_OLD_EVENTS.csv"
MANIFEST_OUTPUT = OUTPUT / f"{PREFIX}_manifest.json"
REPORT_OUTPUT = OUTPUT / f"{PREFIX}_report.md"
IDENTITY_STATUS = "v09_identity_plan_unapplied_true_value_and_structured_attribute_gates_pending"
REPORT_TITLE = "v0.9 identity plan result"
SOURCE_LABEL = "v0.8 candidate"
PLAN_LABEL = "v0.9"


def verify_inputs() -> tuple[dict, dict]:
    final_validation = json.loads(FINAL_VALIDATION.read_text(encoding="utf-8"))
    if final_validation["status"] != "validated_final_candidate_collisions_unapplied":
        raise ValueError("Final candidate collision gate is not validated")
    if sha256(FINAL_DECISIONS) != final_validation["input_sha256"][FINAL_DECISIONS.name]:
        raise ValueError("Final decisions differ from validated provenance")

    existing_manifest = json.loads(EXISTING_MANIFEST.read_text(encoding="utf-8"))
    for path in (EXISTING_NEW, EXISTING_MERGES, EXISTING_EXCLUDED, EXISTING_BLOCKED):
        if sha256(path) != existing_manifest["output_sha256"][path.name]:
            raise ValueError(f"Existing-collision artifact changed: {path.name}")
    mapping_key = str(MAPPING_DECISIONS.relative_to(ROOT))
    if sha256(MAPPING_DECISIONS) != existing_manifest["input_sha256"][mapping_key]:
        raise ValueError("Article-mapping decisions changed after collision review")

    reconstruction_manifest = json.loads(RECONSTRUCTION_MANIFEST.read_text(encoding="utf-8"))
    if sha256(EXCLUDED_ARTICLES) != reconstruction_manifest["output_sha256"][EXCLUDED_ARTICLES.name]:
        raise ValueError("Excluded article memberships changed after reconstruction")
    return existing_manifest, reconstruction_manifest


def expected_counts(
    final_rows: list[dict[str, str]],
    mapping_rows: list[dict[str, str]],
    existing_manifest: dict,
) -> dict[str, int]:
    final_actions = [row["final_candidate_action"] for row in final_rows]
    mapping_unclear = sum(row["final_resolution"] == "unclear" for row in mapping_rows)
    return {
        "remove": existing_manifest["safe_superseded_old_events"],
        "new": final_actions.count("new_event"),
        "merge_existing": existing_manifest["safe_merges_into_existing"],
        "merge_candidate": final_actions.count("merge_candidate"),
        "excluded": existing_manifest["excluded_candidates"]
        + final_actions.count("exclude_duplicate"),
        "blocked_candidates": existing_manifest["blocked_candidates"],
        "retained_old": mapping_unclear + existing_manifest["blocked_old_event_bundles"],
    }


def main() -> int:
    existing_manifest, _reconstruction_manifest = verify_inputs()
    final_rows = read_csv(FINAL_DECISIONS)
    mapping_rows = read_csv(MAPPING_DECISIONS)
    source_rows = read_csv(SOURCE_CANONICAL)
    result = materialize(
        final_rows,
        read_csv(EXISTING_NEW),
        read_csv(EXISTING_MERGES),
        read_csv(EXISTING_EXCLUDED),
        read_csv(EXISTING_BLOCKED),
        mapping_rows,
        [],
        source_rows,
    )
    expected = expected_counts(final_rows, mapping_rows, existing_manifest)
    actual = {key: len(rows) for key, rows in result.items()}
    if actual != expected:
        raise ValueError(
            f"Unexpected {PLAN_LABEL} identity-plan counts: {actual}; expected {expected}"
        )

    base_columns = list(candidate_base({}))
    remove_columns = [
        "old_event_id", "old_cluster_id", "old_event_date", "old_district",
        "final_resolution", "reviewed_by", "reason", "production_status",
    ]
    retained_columns = remove_columns[:-1] + ["blocked_reason", "production_status"]
    outputs = {
        REMOVE_OUTPUT: (result["remove"], remove_columns),
        NEW_OUTPUT: (
            result["new"],
            base_columns + ["reviewed_by_final", "final_collision_notes", "production_status"],
        ),
        MERGE_EXISTING_OUTPUT: (
            result["merge_existing"],
            base_columns + [
                "merge_existing_event_id", "target_date", "target_district",
                "target_municipality", "reviewed_by", "review_notes", "production_status",
            ],
        ),
        MERGE_CANDIDATE_OUTPUT: (
            result["merge_candidate"],
            base_columns + [
                "merge_candidate_event_id", "reviewed_by_final",
                "final_collision_notes", "production_status",
            ],
        ),
        EXCLUDE_OUTPUT: (
            result["excluded"],
            base_columns + [
                "exclusion_stage", "duplicate_of_candidate_event_id", "reviewed_by",
                "review_notes", "production_status",
            ],
        ),
        BLOCKED_OUTPUT: (
            result["blocked_candidates"],
            base_columns + ["blocked_reason", "production_status"],
        ),
        RETAINED_OUTPUT: (result["retained_old"], retained_columns),
    }
    for path, (rows, columns) in outputs.items():
        write_csv(path, rows, columns)

    source_count = len(source_rows)
    planned_count = source_count - len(result["remove"]) + len(result["new"])
    mapping_unclear = sum(
        row["final_resolution"] == "unclear" for row in mapping_rows
    )
    blocked_bundles = existing_manifest["blocked_old_event_bundles"]
    inputs = (
        FINAL_DECISIONS, FINAL_VALIDATION, EXISTING_MANIFEST, EXISTING_NEW,
        EXISTING_MERGES, EXISTING_EXCLUDED, EXISTING_BLOCKED, MAPPING_DECISIONS,
        EXCLUDED_ARTICLES, RECONSTRUCTION_MANIFEST, SOURCE_CANONICAL,
    )
    manifest = {
        "source_release": SOURCE_RELEASE.name,
        "source_inventory_rows": source_count,
        "superseded_old_events": len(result["remove"]),
        "planned_new_events": len(result["new"]),
        "planned_merges_into_existing": len(result["merge_existing"]),
        "planned_merges_into_candidates": len(result["merge_candidate"]),
        "excluded_reconstruction_candidates": len(result["excluded"]),
        "blocked_reconstruction_candidates": len(result["blocked_candidates"]),
        "reviewed_old_events_retained": len(result["retained_old"]),
        "excluded_article_memberships": len(read_csv(EXCLUDED_ARTICLES)),
        "planned_identity_layer_rows": planned_count,
        "net_identity_layer_delta": planned_count - source_count,
        "input_sha256": {str(path.relative_to(ROOT)): sha256(path) for path in inputs},
        "output_sha256": {path.name: sha256(path) for path in outputs},
        "status": IDENTITY_STATUS,
    }
    MANIFEST_OUTPUT.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    REPORT_OUTPUT.write_text(
        "\n".join(
            [
                f"# {REPORT_TITLE}", "",
                f"Source {SOURCE_LABEL} rows: {source_count}",
                f"Superseded old events: {len(result['remove'])}",
                f"Planned new physical events: {len(result['new'])}",
                f"Candidates merged into existing events: {len(result['merge_existing'])}",
                f"Candidates merged into retained candidates: {len(result['merge_candidate'])}",
                f"Excluded reconstruction candidates: {len(result['excluded'])}",
                f"Blocked reconstruction candidates: {len(result['blocked_candidates'])}",
                f"Reviewed old events retained unchanged: {len(result['retained_old'])}",
                f"Excluded article memberships preserved: {len(read_csv(EXCLUDED_ARTICLES))}",
                f"Provisional identity-layer rows: {planned_count}",
                f"Net identity-layer delta: {planned_count - source_count:+d}", "",
                f"The plan is validated but unapplied. {mapping_unclear} mapping-unclear old events and",
                f"{blocked_bundles} collision-blocked old-event bundles remain unchanged. Complete the",
                f"true-value and structured-attribute gates before assembling {PLAN_LABEL}.", "",
            ]
        ),
        encoding="utf-8",
    )
    for path, (rows, _columns) in outputs.items():
        print(f"Wrote {len(rows)} rows to {path}")
    print(f"Wrote {MANIFEST_OUTPUT}")
    print(f"Wrote {REPORT_OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
