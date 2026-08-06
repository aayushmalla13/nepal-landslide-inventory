"""Tests for source configuration helpers."""

from __future__ import annotations

from landslide_inventory.config import load_config
from landslide_inventory.sources import allowed_domains, discovery_entry_points, load_sources


def test_load_sources_returns_exactly_eight(config_file) -> None:
    config = load_config(config_file)
    sources = load_sources(config)
    assert len(sources) == 8


def test_allowed_domains_include_base_and_entry_point_hosts(config_file) -> None:
    config = load_config(config_file)
    source = load_sources(config)[0]
    domains = allowed_domains(source)
    assert "kathmandupost.com" in domains
    assert "example.com" in domains


def test_discovery_entry_points_are_stably_sorted(config_file) -> None:
    config = load_config(config_file)
    source = load_sources(config)[0]
    entry_points = discovery_entry_points(source)
    assert entry_points[0]["kind"] == "googlenews"
