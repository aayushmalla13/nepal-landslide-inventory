"""Tests for the v1.4 article-mapping wrappers."""

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


def test_builder_targets_v13_candidate_and_pinned_v12_articles() -> None:
    module = load("build_v14_article_mapping_pack.py")
    assert module.RELEASE_DIR.name == "nepal_landslide_inventory_v1.3.0_candidate_20260930"
    assert module.ARTICLE_RELEASE_DIR.name == "nepal_landslide_inventory_v1.2.0_candidate_20260929"
    assert module.core.CANDIDATES.name == "v14_remediation_BATCH_ARTICLE_MAPPING.csv"
    assert module.core.DECISIONS.name == "v14_article_mapping_DECISIONS.csv"
    assert module.core.AUDIT_ID == "v14_article_mapping_v1"


def test_validator_targets_v14_outputs() -> None:
    module = load("validate_v14_article_mapping.py")
    assert module.core.TEMPLATE.name == "v14_article_mapping_DECISIONS.csv"
    assert module.core.ARTICLE_MAP.name == "v14_article_membership_MAP.csv"
    assert module.core.DEFAULT_COMPLETED.name == "v14_article_mapping_DECISIONS_COMPLETED.csv"
