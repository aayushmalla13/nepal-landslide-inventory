#!/usr/bin/env python3
"""Validate and score the locked v1.3 final probability sample."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_core():
    path = Path(__file__).with_name("score_v12_final_validation.py")
    spec = importlib.util.spec_from_file_location("v13_fresh_score_core", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load final-validation score core: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = _load_core()
core = base.core
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/outputs"
MANIFEST = OUTPUT / "v13_final_validation_manifest.json"
TEMPLATE = OUTPUT / "v13_final_validation_LABEL_HERE.csv"
WEIGHTS = OUTPUT / "v13_final_validation_weights.csv"
DEFAULT_COMPLETED = OUTPUT / "v13_final_validation_COMPLETED.csv"
JSON_OUTPUT = OUTPUT / "v13_final_validation_score.json"
REPORT_OUTPUT = OUTPUT / "v13_final_validation_report.md"


def render_report(result):
    return core._v13_original_render_report(result).replace(
        "# v0.8 fresh locked validation", "# v1.3 final locked validation", 1
    )


def configure_core() -> None:
    core.MANIFEST = MANIFEST
    core.TEMPLATE = TEMPLATE
    core.WEIGHTS = WEIGHTS
    core.DEFAULT_COMPLETED = DEFAULT_COMPLETED
    core.JSON_OUTPUT = JSON_OUTPUT
    core.REPORT_OUTPUT = REPORT_OUTPUT
    if not hasattr(core, "_v13_original_render_report"):
        core._v13_original_render_report = getattr(
            core, "_v12_original_render_report", core.render_report
        )
    core.render_report = render_report


configure_core()
validate_completed = core.validate_completed
usable_record = core.usable_record
calculate_metrics = core.calculate_metrics
apply_promotion_rule = core.apply_promotion_rule


def main() -> int:
    configure_core()
    return core.main()


if __name__ == "__main__":
    raise SystemExit(main())
