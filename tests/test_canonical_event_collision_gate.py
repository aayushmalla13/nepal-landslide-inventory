"""Tests for reconstruction date and collision review pack generation."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load():
    path = ROOT / "scripts" / "build_canonical_event_collision_gate.py"
    spec = importlib.util.spec_from_file_location("build_collision_gate", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def event(*, candidate: bool, date_value: str, municipality: str = "") -> dict[str, str]:
    common = {
        "district": "Chitwan", "municipality": municipality,
        "event_type": "landslide", "hazard_type": "landslide",
    }
    if candidate:
        return {
            **common, "event_date": date_value, "evidence": "Slide at Kalikhola",
            "article_urls_json": '["https://candidate"]',
        }
    return {
        **common, "event_date_ad": date_value,
        "representative_title": "Kalikhola landslide",
        "representative_url": "https://existing",
        "event_payload": '{"urls":["https://existing"]}',
    }


def test_collision_requires_url_overlap_or_district_date_window() -> None:
    module = load()
    candidate = event(candidate=True, date_value="2025-07-10")
    close = event(candidate=False, date_value="2025-07-12")
    far = event(candidate=False, date_value="2025-08-12")
    assert module.compare(candidate, close) is not None
    assert module.compare(candidate, far) is None


def test_url_overlap_is_high_tier_even_outside_date_window() -> None:
    module = load()
    candidate = event(candidate=True, date_value="2025-07-10")
    existing = event(candidate=False, date_value="2024-01-01")
    existing["event_payload"] = json.dumps({"urls": ["https://candidate"]})
    result = module.compare(candidate, existing)
    assert result is not None
    assert result["collision_tier"] == "high"
    assert "source_url_overlap" in result["reasons"]


def test_same_date_and_municipality_is_high_tier() -> None:
    module = load()
    candidate = event(candidate=True, date_value="2025-07-10", municipality="Ichchhakamana")
    existing = event(candidate=False, date_value="2025-07-10", municipality="Ichchhakamana")
    result = module.compare(candidate, existing)
    assert result is not None
    assert result["collision_tier"] == "high"
