#!/usr/bin/env python3
"""Validate the completed v0.9 structured-attribute review."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path


def _load_shared_validator():
    path = Path(__file__).with_name("validate_post_correction_structured_attribute_review.py")
    spec = importlib.util.spec_from_file_location("post_correction_structured_validator_shared", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load shared structured validator: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_shared = _load_shared_validator()
read_csv = _shared.read_csv
sha256 = _shared.sha256
validate = _shared.validate

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "outputs"
TEMPLATE = OUTPUT / "v09_structured_attribute_REVIEW.csv"
MANIFEST = OUTPUT / "v09_structured_attribute_review_manifest.json"
DEFAULT_COMPLETED = OUTPUT / "v09_structured_attribute_REVIEW_COMPLETED.csv"
VALIDATION_OUTPUT = OUTPUT / "v09_structured_attribute_review_validation.json"
REVIEW_STATUS = "blank_v09_structured_attribute_review"
PLAN_LABEL = "v0.9"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("completed", nargs="?", type=Path, default=DEFAULT_COMPLETED)
    args = parser.parse_args()

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest["status"] != REVIEW_STATUS:
        raise ValueError(
            f"{PLAN_LABEL} structured-attribute review is not in a fillable state"
        )
    if sha256(TEMPLATE) != manifest["output_sha256"][TEMPLATE.name]:
        raise ValueError("Structured-attribute template differs from its manifest")

    result = validate(read_csv(args.completed), read_csv(TEMPLATE))
    result["input_sha256"] = {
        args.completed.name: sha256(args.completed),
        TEMPLATE.name: sha256(TEMPLATE),
        MANIFEST.name: sha256(MANIFEST),
    }
    result["status"] = (
        "blocked_unresolved_structured_attributes"
        if result["unresolved_count"]
        else "validated_structured_attributes_not_yet_applied"
    )
    VALIDATION_OUTPUT.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"Validated {result['review_rows']} {PLAN_LABEL} structured-attribute decisions.")
    print(f"Status: {result['status']}")
    print(f"Wrote {VALIDATION_OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
