"""Tests for stage dispatch and smoke stage behavior."""

from __future__ import annotations

from landslide_inventory.config import load_config
from landslide_inventory.db import list_tables
from landslide_inventory.run import dispatch_stage


def test_stage_runner_dispatches_smoke_stage(config_file) -> None:
    config = load_config(config_file)
    dispatch_stage("smoke", config)
    database_path = config.sqlite_path
    assert database_path.exists()
    assert "raw_articles" in list_tables(database_path)


def test_stage_runner_rejects_unknown_stage(config_file) -> None:
    config = load_config(config_file)
    try:
        dispatch_stage("unknown", config)
    except ValueError as exc:
        assert "Unknown stage" in str(exc)
    else:  # pragma: no cover - defensive branch
        raise AssertionError("Expected ValueError for unknown stage.")
