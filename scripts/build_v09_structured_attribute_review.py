#!/usr/bin/env python3
"""Build the final v0.9 structured-attribute review sheet."""

from __future__ import annotations

import importlib.util
import json
from collections import Counter
from pathlib import Path


def _load_shared_builder():
    path = Path(__file__).with_name("build_post_correction_structured_attribute_review.py")
    spec = importlib.util.spec_from_file_location("post_correction_structured_builder_shared", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load shared structured-review builder: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_shared = _load_shared_builder()
read_csv = _shared.read_csv
write_csv = _shared.write_csv
sha256 = _shared.sha256
build = _shared.build

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "outputs"
SOURCE = OUTPUT / "v09_remediation_BATCH_STRUCTURED_ATTRIBUTES.csv"
REMEDIATION_MANIFEST = OUTPUT / "v09_remediation_manifest.json"
IDENTITY_REMOVE = OUTPUT / "v09_identity_plan_REMOVE_OLD_EVENTS.csv"
IDENTITY_MERGES = OUTPUT / "v09_identity_plan_MERGES_EXISTING.csv"
IDENTITY_MANIFEST = OUTPUT / "v09_identity_plan_manifest.json"
TRUE_VALUE_COMPLETED = OUTPUT / "v09_remediation_BATCH_TRUE_VALUE_REVIEW_COMPLETED.csv"
TRUE_VALUE_CORRECTIONS = OUTPUT / "v09_true_value_plan_CORRECTIONS.csv"
TRUE_VALUE_EXCLUSIONS = OUTPUT / "v09_true_value_plan_EXCLUSIONS.csv"
TRUE_VALUE_NO_CHANGE = OUTPUT / "v09_true_value_plan_NO_CHANGE.csv"
TRUE_VALUE_MANIFEST = OUTPUT / "v09_true_value_plan_manifest.json"
REVIEW_OUTPUT = OUTPUT / "v09_structured_attribute_REVIEW.csv"
MANIFEST_OUTPUT = OUTPUT / "v09_structured_attribute_review_manifest.json"
REPORT_OUTPUT = OUTPUT / "v09_structured_attribute_review_report.md"
IDENTITY_STATUS = "v09_identity_plan_unapplied_true_value_and_structured_attribute_gates_pending"
TRUE_VALUE_STATUS = "v09_true_value_plan_unapplied_structured_attribute_gate_pending"
REVIEW_STATUS = "blank_v09_structured_attribute_review"
PLAN_LABEL = "v0.9"


def prior_event_ids() -> set[str]:
    ids = {row["old_event_id"] for row in read_csv(IDENTITY_REMOVE)}
    ids.update(row["merge_existing_event_id"] for row in read_csv(IDENTITY_MERGES))
    for path in (TRUE_VALUE_CORRECTIONS, TRUE_VALUE_EXCLUSIONS, TRUE_VALUE_NO_CHANGE):
        ids.update(row["event_id"] for row in read_csv(path))
    return ids


def verify_inputs() -> tuple[dict, dict, dict]:
    remediation = json.loads(REMEDIATION_MANIFEST.read_text(encoding="utf-8"))
    if sha256(SOURCE) != remediation["output_sha256"][SOURCE.name]:
        raise ValueError("Structured-attribute source differs from remediation provenance")

    identity = json.loads(IDENTITY_MANIFEST.read_text(encoding="utf-8"))
    if identity["status"] != IDENTITY_STATUS:
        raise ValueError(f"{PLAN_LABEL} identity plan is not ready")

    true_value = json.loads(TRUE_VALUE_MANIFEST.read_text(encoding="utf-8"))
    if true_value["status"] != TRUE_VALUE_STATUS:
        raise ValueError(f"{PLAN_LABEL} true-value plan is not ready")
    for path in (TRUE_VALUE_CORRECTIONS, TRUE_VALUE_EXCLUSIONS, TRUE_VALUE_NO_CHANGE):
        if sha256(path) != true_value["output_sha256"][path.name]:
            raise ValueError(f"True-value artifact changed: {path.name}")
    return remediation, identity, true_value


def main() -> int:
    verify_inputs()
    source_rows = read_csv(SOURCE)
    overlap = {row["event_id"] for row in source_rows} & prior_event_ids()
    if overlap:
        raise ValueError(f"Structured-attribute rows overlap earlier plans: {sorted(overlap)}")

    review = build(source_rows)
    write_csv(REVIEW_OUTPUT, review)
    actions = Counter(
        action for row in review for action in row["recommended_actions"].split(";")
    )
    inputs = (
        SOURCE, REMEDIATION_MANIFEST, IDENTITY_REMOVE, IDENTITY_MERGES,
        IDENTITY_MANIFEST, TRUE_VALUE_COMPLETED, TRUE_VALUE_CORRECTIONS,
        TRUE_VALUE_EXCLUSIONS, TRUE_VALUE_NO_CHANGE, TRUE_VALUE_MANIFEST,
    )
    manifest = {
        "review_rows": len(review),
        "action_counts": dict(actions),
        "prior_gate_overlap_count": 0,
        "input_sha256": {str(path.relative_to(ROOT)): sha256(path) for path in inputs},
        "output_sha256": {REVIEW_OUTPUT.name: sha256(REVIEW_OUTPUT)},
        "status": REVIEW_STATUS,
    }
    MANIFEST_OUTPUT.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    lines = [
        f"# {PLAN_LABEL} structured-attribute review", "", f"Rows: {len(review)}",
        "Prior-gate overlap: 0", "", "| Required action | Rows |", "|---|---:|",
    ]
    for action, count in actions.most_common():
        lines.append(f"| {action} | {count} |")
    lines.append("")
    REPORT_OUTPUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {len(review)} rows to {REVIEW_OUTPUT}")
    print(f"Wrote {MANIFEST_OUTPUT}")
    print(f"Wrote {REPORT_OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
