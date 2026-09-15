"""Tests for the src/ shadowing guard."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / 'scripts' / 'check_shadowing.py'


def _load_shadowing_module():
    spec = importlib.util.spec_from_file_location('check_shadowing', SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f'Unable to load {SCRIPT_PATH}')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_shadowing_guard_finds_no_issues_in_src_tree() -> None:
    module = _load_shadowing_module()
    assert module.find_shadowing_issues(REPO_ROOT / 'src') == []


def test_shadowing_guard_script_exits_successfully() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert 'no shadowing issues found' in result.stdout


def test_config_example_is_valid_yaml() -> None:
    data = yaml.safe_load((REPO_ROOT / 'config.example.yaml').read_text(encoding='utf-8'))
    assert isinstance(data, dict)
    assert 'sources' in data
    slugs = {source['slug'] for source in data['sources']}
    assert {
        'kathmandu-post',
        'himalayan-times',
        'myrepublica',
        'rising-nepal',
        'ekantipur',
        'online-khabar',
        'setopati',
        'ratopati',
    } <= slugs
