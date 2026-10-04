#!/usr/bin/env python3
"""Freeze actionable v1.4 validation findings into the v1.5 remediation queue."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_core():
    path = Path(__file__).with_name("build_v09_remediation_queue.py")
    spec = importlib.util.spec_from_file_location("v15_remediation_core", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load remediation core: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


core = _load_core()
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/outputs"


def configure_core() -> None:
    core.COMPLETED = OUTPUT / "v14_final_validation_COMPLETED.csv"
    core.READING = OUTPUT / "v14_final_validation_reading_pack.csv"
    core.WEIGHTS = OUTPUT / "v14_final_validation_weights.csv"
    core.VALIDATION_MANIFEST = OUTPUT / "v14_final_validation_manifest.json"
    core.VALIDATION_SCORE = OUTPUT / "v14_final_validation_score.json"
    core.QUEUE = OUTPUT / "v15_remediation_queue.csv"
    core.SUMMARY = OUTPUT / "v15_remediation_summary.json"
    core.REPORT = OUTPUT / "v15_remediation_report.md"
    core.MANIFEST = OUTPUT / "v15_remediation_manifest.json"
    core.BATCH_OUTPUTS = {
        "requires_article_mapping": OUTPUT / "v15_remediation_BATCH_ARTICLE_MAPPING.csv",
        "requires_true_value_review": OUTPUT / "v15_remediation_BATCH_TRUE_VALUE_REVIEW.csv",
        "structured_attribute_candidate": (
            OUTPUT / "v15_remediation_BATCH_STRUCTURED_ATTRIBUTES.csv"
        ),
    }
    if not hasattr(core, "_v15_original_build_summary"):
        core._v15_original_build_summary = core.build_summary
    if not hasattr(core, "_v15_original_render_report"):
        core._v15_original_render_report = core.render_report
    if not hasattr(core, "_v15_original_build_queue_rows"):
        core._v15_original_build_queue_rows = core.build_queue_rows

    def build_queue_rows(labels, reading_by_id, weights_by_id):
        rows = core._v15_original_build_queue_rows(labels, reading_by_id, weights_by_id)
        for number, row in enumerate(rows, start=1):
            row["queue_id"] = f"V15R-{number:03d}"
            row["sample_role"] = "v14_final_probability"
            row["correction_layer"] = "v15_remediation"
        return rows

    def build_summary(all_rows, queue):
        result = core._v15_original_build_summary(all_rows, queue)
        result.update(
            {
                "audit": "v15_remediation_queue_v1",
                "source_candidate": "nepal_landslide_inventory_v1.4.0_candidate_20261002",
                "target_candidate": "nepal_landslide_inventory_v1.5.0_candidate",
            }
        )
        return result

    def render_report(summary):
        return (
            core._v15_original_render_report(summary)
            .replace("# v0.9 remediation queue", "# v1.5 remediation queue", 1)
            .replace("The v0.8 audit", "The v1.4 audit", 1)
        )

    core.build_summary = build_summary
    core.build_queue_rows = build_queue_rows
    core.render_report = render_report
    core.__file__ = __file__


configure_core()
build_queue_rows = core.build_queue_rows
build_summary = core.build_summary
verify_inputs = core.verify_inputs
validate_alignment = core.validate_alignment


def main() -> int:
    configure_core()
    return core.main()


if __name__ == "__main__":
    raise SystemExit(main())
