"""Tests for the v1.3 article-mapping wrappers."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load(name: str):
    path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_builder_targets_frozen_v12_candidate() -> None:
    module = load("build_v13_article_mapping_pack.py")
    assert module.core.CANDIDATES.name == "v13_remediation_BATCH_ARTICLE_MAPPING.csv"
    assert module.core.DATABASE.parent.name == (
        "nepal_landslide_inventory_v1.2.0_candidate_20260929"
    )
    assert module.core.DECISIONS.name == "v13_article_mapping_DECISIONS.csv"
    assert module.core.AUDIT_ID == "v13_article_mapping_v1"
    assert Path(module.core.__file__).name == "build_v13_article_mapping_pack.py"


def test_validator_targets_v13_completed_sheet() -> None:
    module = load("validate_v13_article_mapping.py")
    assert module.core.DEFAULT_COMPLETED.name == (
        "v13_article_mapping_DECISIONS_COMPLETED.csv"
    )
    assert module.core.ARTICLE_MAP.name == "v13_article_membership_MAP.csv"
