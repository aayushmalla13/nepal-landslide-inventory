"""Tests for keyword taxonomy export."""

from __future__ import annotations

import json

from landslide_inventory.config import load_config
from landslide_inventory.keywords import build_keyword_taxonomy, export_keyword_taxonomy


def test_build_keyword_taxonomy_returns_expected_sections(config_file) -> None:
    config = load_config(config_file)
    taxonomy = build_keyword_taxonomy(config)
    assert sorted(taxonomy) == [
        "casualty_terms",
        "exclude_terms",
        "landslide_terms",
        "trigger_terms",
    ]


def test_export_keyword_taxonomy_writes_json(config_file) -> None:
    config = load_config(config_file)
    output_path = export_keyword_taxonomy(config)
    exported = json.loads(output_path.read_text(encoding="utf-8"))
    assert output_path.name == "keyword_taxonomy.json"
    assert exported["landslide_terms"]["np"] == ["पहिरो"]
