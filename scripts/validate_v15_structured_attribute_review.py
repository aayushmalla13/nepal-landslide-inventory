#!/usr/bin/env python3
"""Validate the completed v1.5 structured-attribute review."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_core():
    path = Path(__file__).with_name("validate_v09_structured_attribute_review.py")
    spec = importlib.util.spec_from_file_location("v15_structured_validation_core", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load structured validator core: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


core = _load_core()
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/outputs"


def configure_core() -> None:
    core.TEMPLATE = OUTPUT / "v15_structured_attribute_REVIEW.csv"
    core.MANIFEST = OUTPUT / "v15_structured_attribute_review_manifest.json"
    core.DEFAULT_COMPLETED = OUTPUT / "v15_structured_attribute_REVIEW_COMPLETED.csv"
    core.VALIDATION_OUTPUT = OUTPUT / "v15_structured_attribute_review_validation.json"
    core.REVIEW_STATUS = "blank_v15_structured_attribute_review"
    core.PLAN_LABEL = "v1.5"


configure_core()
validate = core.validate


def main() -> int:
    configure_core()
    return core.main()


if __name__ == "__main__":
    raise SystemExit(main())
