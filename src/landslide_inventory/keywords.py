"""Keyword taxonomy helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import AppConfig
from .utils import ensure_directory


def build_keyword_taxonomy(config: AppConfig) -> dict[str, Any]:
    """Build the configured keyword taxonomy."""

    keywords = dict(config.raw["keywords"])
    return {
        "landslide_terms": {
            "en": list(keywords["terms"]["en"]),
            "np": list(keywords["terms"]["np"]),
        },
        "exclude_terms": {
            "en": list(keywords["exclude"]["en"]),
            "np": list(keywords["exclude"]["np"]),
        },
        "trigger_terms": _sorted_nested_terms(dict(keywords["trigger_terms"])),
        "casualty_terms": _sorted_nested_terms(dict(keywords["casualty_terms"])),
    }


def export_keyword_taxonomy(config: AppConfig) -> Path:
    """Export the keyword taxonomy to the configured intermediate directory."""

    output_path = config.resolve_path("intermediate_dir") / "keyword_taxonomy.json"
    ensure_directory(output_path.parent)
    taxonomy = build_keyword_taxonomy(config)
    output_path.write_text(
        json.dumps(taxonomy, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    return output_path


def _sorted_nested_terms(section: dict[str, Any]) -> dict[str, dict[str, list[str]]]:
    """Return nested keyword sections with deterministic ordering."""

    normalized: dict[str, dict[str, list[str]]] = {}
    for label in sorted(section):
        values = dict(section[label])
        normalized[label] = {
            "en": sorted(str(item) for item in values.get("en", [])),
            "np": sorted(str(item) for item in values.get("np", [])),
        }
    return normalized
