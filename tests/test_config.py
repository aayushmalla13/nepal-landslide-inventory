"""Tests for configuration loading."""

from __future__ import annotations

from pathlib import Path

from landslide_inventory.config import ConfigError, load_config, validate_config


def test_load_config_supports_placeholder_mode(tmp_path: Path) -> None:
    config = load_config(tmp_path / 'missing.yaml', allow_placeholder=True)
    assert config.is_placeholder is True
    assert config.study_period == (2015, 2026)


def test_load_config_requires_existing_file_without_placeholder(tmp_path: Path) -> None:
    missing_path = tmp_path / 'missing.yaml'
    try:
        load_config(missing_path)
    except ConfigError as exc:
        assert 'config.example.yaml' in str(exc)
    else:  # pragma: no cover - defensive branch
        raise AssertionError('Expected ConfigError for missing config file.')


def test_validate_config_rejects_wrong_source_count(
    config_payload: dict[str, object],
) -> None:
    config_payload['sources'] = list(config_payload['sources'])[:-1]
    try:
        validate_config(config_payload)
    except ConfigError as exc:
        assert 'exactly 8 sources' in str(exc)
    else:  # pragma: no cover - defensive branch
        raise AssertionError('Expected ConfigError for wrong source count.')


def test_validate_config_rejects_missing_required_sections(
    config_payload: dict[str, object],
) -> None:
    config_payload.pop('runtime')
    try:
        validate_config(config_payload)
    except ConfigError as exc:
        assert 'Missing required config sections' in str(exc)
    else:  # pragma: no cover - defensive branch
        raise AssertionError('Expected ConfigError for missing required sections.')


def test_load_config_applies_runtime_env_overrides(monkeypatch, config_file: Path) -> None:
    monkeypatch.setenv('LS_MAX_URLS_PER_SOURCE', '17')
    monkeypatch.setenv('LS_MAX_PAGES_PER_ENTRY', '2')
    monkeypatch.setenv('LS_RATE_LIMIT_SECONDS', '0.2')
    config = load_config(config_file)
    assert config.raw['runtime']['max_urls_per_source'] == 17
    assert config.raw['runtime']['max_pages_per_entry_point'] == 2
    assert config.raw['runtime']['rate_limit_seconds'] == 0.2
