"""Tests for the generated v1.5 Methods and Data material."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load():
    path = ROOT / "scripts/build_v15_methods_data.py"
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_sampling_strata_are_collapsed_without_double_counting() -> None:
    module = load()
    rows = [
        {"stratum": "a", "population_n": "10", "sample_n": "2", "sampling_weight": "5"},
        {"stratum": "a", "population_n": "10", "sample_n": "2", "sampling_weight": "5"},
        {"stratum": "b", "population_n": "4", "sample_n": "4", "sampling_weight": "1"},
    ]
    strata = module.sampling_strata(rows)
    assert len(strata) == 2
    assert sum(row["population_n"] for row in strata) == 14
    assert sum(row["sample_n"] for row in strata) == 6


def test_attribute_profile_preserves_unknown_as_missing() -> None:
    module = load()
    rows = [
        {
            "municipality": "Pokhara",
            "trigger": "unknown",
            "deaths": "",
            "missing": "0",
            "injured": "",
            "cluster_size": "2",
            "extraction_basis": "full_text",
            "conf_date": "0.80",
        }
    ]
    profile = module.attribute_profile(rows)
    assert profile["municipality"] == 1
    assert profile["known_trigger"] == 0
    assert profile["deaths"] == 0
    assert profile["missing"] == 1
    assert profile["multi_article"] == 1
