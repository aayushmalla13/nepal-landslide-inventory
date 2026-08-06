"""Pytest fixtures for scaffold tests."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml


@pytest.fixture()
def config_payload() -> dict[str, object]:
    """Return a valid in-memory config payload."""

    return {
        "paper_metadata": {
            "study_area": "Nepal, 77 districts",
            "study_period": "2015-2026",
            "version": "0.1.0",
        },
        "study_period": {"start": "2015-01-01", "end": "2026-12-31"},
        "paths": {
            "raw_sqlite_dir": "data/raw_sqlite",
            "intermediate_dir": "data/intermediate",
            "outputs_dir": "data/outputs",
            "caches_dir": "data/caches",
            "logs_dir": "data/logs",
        },
        "runtime": {
            "rate_limit_seconds": 1.0,
            "retries": 3,
            "timeout_seconds": 30,
            "user_agent": "landslide-inventory-test",
            "max_pages_per_entry_point": 50,
            "max_urls_per_source": 2000,
        },
        "language_detection": {
            "devanagari_threshold": 0.30,
            "mixed_lower": 0.10,
            "mixed_upper": 0.30,
        },
        "dedup": {
            "candidate_window_days": 7,
            "primary_window_days": 3,
            "headline_sim_threshold": 0.82,
            "body_sim_threshold": 0.88,
            "high_body_sim_threshold": 0.96,
            "guard_deaths_delta": 1,
            "prefer_same_municipality": True,
        },
        "geocode": {
            "district_shapefile_path": "/tmp/ocha_districts.shp",
            "centroid_cache_path": "data/caches/district_centroids.csv",
            "nominatim_cache_db_path": "data/caches/nominatim_cache.sqlite",
        },
        "validation": {
            "manual_sample_total": 150,
            "manual_en": 75,
            "manual_np": 75,
            "random_seed": 42,
        },
        "bipad": {
            "bipad_input_path": "/tmp/bipad_landslides.csv",
            "match_windows_days": [1, 3, 7],
        },
        "analysis": {
            "chirps_district_month_path": "/tmp/chirps_district_month.csv",
            "correlation_method": "spearman",
        },
        "keywords": {
            "terms": {
                "en": ["landslide"],
                "np": ["पहिरो"],
            },
            "exclude": {
                "en": ["political landslide"],
                "np": ["राजनीतिक पहिरो"],
            },
            "trigger_terms": {
                "rainfall": {"en": ["rain"], "np": ["वर्षा"]},
            },
            "casualty_terms": {
                "deaths": {"en": ["killed"], "np": ["मृत्यु"]},
            },
        },
        "doctor": {"spacy_model": "en_core_web_sm"},
        "sources": [
            {
                "name": "Kathmandu Post",
                "slug": "kathmandu-post",
                "language": "en",
                "base_url": "https://kathmandupost.com",
                "discovery": {"primary": "googlenews", "secondary": "tag"},
                "entry_points": [
                    {"kind": "googlenews", "url": "https://example.com/kathmandu-post", "pagination": "rss"},
                    {"kind": "tag", "url": "https://example.com/kathmandu-post-tag", "pagination": "next_link"},
                ],
            },
            {
                "name": "The Himalayan Times",
                "slug": "himalayan-times",
                "language": "en",
                "base_url": "https://thehimalayantimes.com",
                "discovery": {"primary": "googlenews"},
                "entry_points": [
                    {"kind": "googlenews", "url": "https://example.com/himalayan-times", "pagination": "rss"},
                ],
            },
            {
                "name": "MyRepublica",
                "slug": "myrepublica",
                "language": "en",
                "base_url": "https://myrepublica.nagariknetwork.com",
                "discovery": {"primary": "tag"},
                "entry_points": [
                    {"kind": "tag", "url": "https://example.com/myrepublica", "pagination": "page"},
                ],
            },
            {
                "name": "The Rising Nepal",
                "slug": "rising-nepal",
                "language": "en",
                "base_url": "https://risingnepaldaily.com",
                "discovery": {"primary": "googlenews"},
                "entry_points": [
                    {"kind": "googlenews", "url": "https://example.com/rising-nepal", "pagination": "rss"},
                ],
            },
            {
                "name": "eKantipur",
                "slug": "ekantipur",
                "language": "np",
                "base_url": "https://ekantipur.com",
                "discovery": {"primary": "googlenews", "secondary": "archive_home"},
                "entry_points": [
                    {"kind": "googlenews", "url": "https://example.com/ekantipur", "pagination": "rss"},
                    {"kind": "archive_home", "url": "https://example.com/ekantipur-home", "pagination": "date_archive"},
                ],
            },
            {
                "name": "Online Khabar",
                "slug": "online-khabar",
                "language": "np",
                "base_url": "https://www.onlinekhabar.com",
                "discovery": {"primary": "trend"},
                "entry_points": [
                    {"kind": "trend", "url": "https://example.com/online-khabar", "pagination": "/page/{page}"},
                ],
            },
            {
                "name": "Setopati",
                "slug": "setopati",
                "language": "np",
                "base_url": "https://www.setopati.com",
                "discovery": {"primary": "tag"},
                "entry_points": [
                    {"kind": "tag", "url": "https://example.com/setopati", "pagination": "next_link"},
                ],
            },
            {
                "name": "Ratopati",
                "slug": "ratopati",
                "language": "np",
                "base_url": "https://www.ratopati.com",
                "discovery": {"primary": "tag"},
                "entry_points": [
                    {"kind": "tag", "url": "https://example.com/ratopati", "pagination": "page"},
                ],
            },
        ],
    }


@pytest.fixture()
def config_file(tmp_path: Path, config_payload: dict[str, object]) -> Path:
    """Write a temporary config file and return its path."""

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(config_payload, sort_keys=False), encoding="utf-8")
    return config_path
