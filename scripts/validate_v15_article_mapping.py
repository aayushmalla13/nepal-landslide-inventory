#!/usr/bin/env python3
"""Validate completed v1.5 article-mapping decisions."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_core():
    path = Path(__file__).with_name("validate_v09_article_mapping.py")
    spec = importlib.util.spec_from_file_location("v15_mapping_validation_core", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load mapping validator core: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


core = _load_core()
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/outputs"


def configure_core() -> None:
    core.TEMPLATE = OUTPUT / "v15_article_mapping_DECISIONS.csv"
    core.ARTICLE_MAP = OUTPUT / "v15_article_membership_MAP.csv"
    core.MAPPING_MANIFEST = OUTPUT / "v15_article_mapping_manifest.json"
    core.DEFAULT_COMPLETED = OUTPUT / "v15_article_mapping_DECISIONS_COMPLETED.csv"
    core.VALIDATION_OUTPUT = OUTPUT / "v15_article_mapping_validation.json"


configure_core()
validate = core.validate


def main() -> int:
    configure_core()
    return core.main()


if __name__ == "__main__":
    raise SystemExit(main())
