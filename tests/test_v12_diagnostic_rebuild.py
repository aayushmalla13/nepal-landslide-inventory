"""Tests for the isolated v1.2 rebuild runner."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from landslide_inventory.config import load_config


ROOT = Path(__file__).resolve().parents[1]


def load():
    path = ROOT / "scripts/run_v12_diagnostic_rebuild.py"
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_diagnostic_config_redirects_every_writable_data_path(tmp_path: Path) -> None:
    module = load()
    base = load_config(ROOT / "config.yaml")
    config = module.diagnostic_config(base, tmp_path)
    assert config.sqlite_path == tmp_path / "landslide_inventory.sqlite"
    for key in ("intermediate_dir", "outputs_dir", "caches_dir", "logs_dir"):
        assert config.resolve_path(key).is_relative_to(tmp_path)


def test_rebuild_order_runs_typing_before_export() -> None:
    module = load()
    names = [name for name, _ in module.STAGES]
    assert names[:2] == ["extract", "event_specificity"]
    assert names[-2:] == ["event_typing", "export_final"]


def test_unknown_resume_stage_is_rejected_before_writes(tmp_path: Path) -> None:
    module = load()
    try:
        module.run_rebuild(
            ROOT,
            ROOT / "config.yaml",
            ROOT / "data/raw_sqlite/landslide_inventory.sqlite",
            tmp_path,
            resume_from="not-a-stage",
        )
    except ValueError as exc:
        assert "Unknown resume stage" in str(exc)
    else:
        raise AssertionError("unknown resume stage was accepted")
