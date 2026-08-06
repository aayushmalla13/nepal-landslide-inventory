"""Tests for the smoke harness helpers."""

from __future__ import annotations

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / 'scripts' / 'smoke.py'


def _load_smoke_module():
    spec = importlib.util.spec_from_file_location('smoke', SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f'Unable to load {SCRIPT_PATH}')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_resolve_stage_name_maps_scrape_alias() -> None:
    module = _load_smoke_module()
    assert module.resolve_stage_name('scrape') == 'collect'
    assert module.resolve_stage_name('dedup') == 'dedup'
    assert module.resolve_stage_name('inventory_audit') == 'inventory_audit'


def test_build_stage_env_sets_dev_overrides() -> None:
    module = _load_smoke_module()
    env = module.build_stage_env()
    assert env['LS_MAX_URLS_PER_SOURCE'] == '20'
    assert env['LS_MAX_PAGES_PER_ENTRY'] == '1'
    assert env['LS_RATE_LIMIT_SECONDS'] == '0'
    assert env['PYTHONPATH'] == 'src'


def test_file_has_data_rows_detects_header_and_row(tmp_path: Path) -> None:
    module = _load_smoke_module()
    path = tmp_path / 'sample.csv'
    path.write_text('a,b\n1,2\n', encoding='utf-8')
    assert module.file_has_data_rows(path) is True
    path.write_text('a,b\n', encoding='utf-8')
    assert module.file_has_data_rows(path) is False
