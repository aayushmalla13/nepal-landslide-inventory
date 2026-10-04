"""Tests for v1.1 candidate assembler configuration."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def load():
    path = ROOT / "scripts/assemble_v11_candidate_release.py"
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_v11_release_configuration() -> None:
    module = load()
    assert module.SOURCE_RELEASE_ID == (
        "nepal_landslide_inventory_v1.0.0_candidate_20260927"
    )
    assert module.EXPECTED_SOURCE_ROWS == 2605
    assert module.EXPECTED_ROWS == 2589
    assert module.PLAN_FILES["new"] == "v11_identity_plan_NEW_EVENTS.csv"
    assert module.core.ARTICLE_DATABASE_RELATIVE.name == "landslide_inventory.sqlite"


def test_v11_candidate_suffix() -> None:
    module = load()
    assert module.candidate_suffix("v11_candidate_abc") == "abc"
    with pytest.raises(ValueError, match="Unexpected v1.1"):
        module.candidate_suffix("v09_candidate_abc")


def test_empty_location_log_has_stable_schema(tmp_path: Path) -> None:
    module = load()
    path = tmp_path / "locations.csv"
    columns = [
        "candidate_event_id",
        "raw_district",
        "final_district",
        "raw_municipality",
        "final_municipality",
        "reason",
    ]
    module.core.write_csv(path, [], columns)
    assert path.read_text().strip() == ",".join(columns)
