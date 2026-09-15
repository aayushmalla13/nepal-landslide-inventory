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


def test_validate_config_rejects_dropping_a_source(
    config_payload: dict[str, object],
) -> None:
    """Removing one of the original eight must still hard-fail.

    Every coverage baseline in docs/log.md is stated against that source set, so
    a silently shorter list would invalidate them without any visible error.
    """

    config_payload['sources'] = list(config_payload['sources'])[:-1]
    try:
        validate_config(config_payload)
    except ConfigError as exc:
        assert 'at least 8 sources' in str(exc)
    else:  # pragma: no cover - defensive branch
        raise AssertionError('Expected ConfigError for a missing source.')


def test_validate_config_accepts_added_sources(
    config_payload: dict[str, object],
) -> None:
    """Adding a NEW source must be allowed.

    The check was `len(sources) != 8` plus `slugs != EXPECTED_SOURCE_SLUGS`, so
    the config validator refused to start the moment a source was added --
    blocking the project's highest-value remaining work (2026-08-08 prospecting
    showed Nepali coverage before 2023 barely exists). Extra sources are now the
    intended direction of travel; only losing an original one is an error.
    """

    sources = list(config_payload['sources'])
    extra = dict(sources[0])
    extra.update({'name': 'Deshsanchar', 'slug': 'deshsanchar',
                  'language': 'np', 'base_url': 'https://deshsanchar.com'})
    config_payload['sources'] = sources + [extra]
    validate_config(config_payload)      # must not raise


def test_validate_config_rejects_duplicate_slugs(
    config_payload: dict[str, object],
) -> None:
    """Relaxing the count check must not let a copy-paste duplicate through."""

    sources = list(config_payload['sources'])
    config_payload['sources'] = sources + [dict(sources[0])]
    try:
        validate_config(config_payload)
    except ConfigError as exc:
        assert 'Duplicate source slugs' in str(exc)
    else:  # pragma: no cover - defensive branch
        raise AssertionError('Expected ConfigError for duplicate slugs.')


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
