"""Tests for the v1.1 article-mapping wrappers."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load(name: str):
    path = ROOT / 'scripts' / name
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_builder_targets_frozen_v10_candidate() -> None:
    module = load('build_v11_article_mapping_pack.py')
    assert module.core.CANDIDATES.name == 'v11_remediation_BATCH_ARTICLE_MAPPING.csv'
    assert module.core.DATABASE.parent.name == (
        'nepal_landslide_inventory_v1.0.0_candidate_20260927'
    )
    assert module.core.DECISIONS.name == 'v11_article_mapping_DECISIONS.csv'


def test_validator_targets_v11_completed_sheet() -> None:
    module = load('validate_v11_article_mapping.py')
    assert module.core.DEFAULT_COMPLETED.name == (
        'v11_article_mapping_DECISIONS_COMPLETED.csv'
    )
    assert module.core.ARTICLE_MAP.name == 'v11_article_membership_MAP.csv'
