"""Configuration loading and validation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import os
from pathlib import Path
from typing import Any

import yaml

EXPECTED_SOURCE_COUNT = 8
EXPECTED_STUDY_PERIOD = (date(2015, 1, 1), date(2026, 12, 31))
RUNTIME_ENV_OVERRIDES = {
    "LS_MAX_URLS_PER_SOURCE": ("max_urls_per_source", int),
    "LS_MAX_PAGES_PER_ENTRY": ("max_pages_per_entry_point", int),
    "LS_RATE_LIMIT_SECONDS": ("rate_limit_seconds", float),
}
REQUIRED_TOP_LEVEL_KEYS = {
    "paper_metadata",
    "study_period",
    "paths",
    "runtime",
    "language_detection",
    "dedup",
    "geocode",
    "validation",
    "bipad",
    "analysis",
    "keywords",
    "sources",
}
REQUIRED_PATH_KEYS = {
    "raw_sqlite_dir",
    "intermediate_dir",
    "outputs_dir",
    "caches_dir",
    "logs_dir",
}
REQUIRED_SOURCE_KEYS = {
    "name",
    "slug",
    "language",
    "base_url",
    "discovery",
    "entry_points",
}
REQUIRED_DISCOVERY_KEYS = {"primary"}
EXPECTED_SOURCE_SLUGS = {
    "kathmandu-post",
    "himalayan-times",
    "myrepublica",
    "rising-nepal",
    "ekantipur",
    "online-khabar",
    "setopati",
    "ratopati",
}


class ConfigError(ValueError):
    """Raised when configuration loading or validation fails."""


@dataclass(frozen=True)
class AppConfig:
    """Validated application configuration."""

    raw: dict[str, Any]
    config_path: Path
    is_placeholder: bool = False

    @property
    def study_period(self) -> tuple[int, int]:
        """Return the inclusive study period years."""

        period = self.raw["study_period"]
        return int(period["start"][:4]), int(period["end"][:4])

    @property
    def paths(self) -> dict[str, str]:
        """Return configured path mapping."""

        return dict(self.raw["paths"])

    @property
    def sources(self) -> list[dict[str, Any]]:
        """Return configured source definitions."""

        return list(self.raw["sources"])

    @property
    def doctor_settings(self) -> dict[str, Any]:
        """Return doctor-specific settings."""

        return dict(self.raw.get("doctor", {}))

    def resolve_path(self, key: str) -> Path:
        """Resolve a configured path relative to the config file."""

        candidate = Path(self.paths[key])
        if candidate.is_absolute():
            return candidate
        return (self.config_path.parent / candidate).resolve()

    def data_directories(self) -> list[Path]:
        """Return configured directories that should exist before runtime."""

        return [
            self.resolve_path("raw_sqlite_dir"),
            self.resolve_path("intermediate_dir"),
            self.resolve_path("outputs_dir"),
            self.resolve_path("caches_dir"),
            self.resolve_path("logs_dir"),
        ]

    @property
    def sqlite_path(self) -> Path:
        """Return the configured SQLite database file path."""

        return self.resolve_path("raw_sqlite_dir") / "landslide_inventory.sqlite"

    @classmethod
    def placeholder(cls, config_path: str | Path) -> "AppConfig":
        """Build a placeholder configuration when the main file is absent."""

        path = Path(config_path).resolve()
        raw = {
            "paper_metadata": {
                "study_area": "Nepal, 77 districts",
                "study_period": "2015-2026",
                "version": "0.1.0",
            },
            "study_period": {
                "start": EXPECTED_STUDY_PERIOD[0].isoformat(),
                "end": EXPECTED_STUDY_PERIOD[1].isoformat(),
            },
            "paths": {
                "raw_sqlite_dir": "data/raw_sqlite",
                "intermediate_dir": "data/intermediate",
                "outputs_dir": "data/outputs",
                "caches_dir": "data/caches",
                "logs_dir": "data/logs",
            },
            "runtime": {},
            "language_detection": {},
            "dedup": {},
            "geocode": {},
            "validation": {},
            "bipad": {},
            "analysis": {},
            "keywords": {},
            "doctor": {"spacy_model": "en_core_web_sm"},
            "sources": [],
        }
        return cls(raw=raw, config_path=path, is_placeholder=True)


def load_config(config_path: str | Path, allow_placeholder: bool = False) -> AppConfig:
    """Load and validate YAML configuration from disk."""

    path = Path(config_path).resolve()
    if not path.exists():
        if allow_placeholder:
            return AppConfig.placeholder(path)
        raise ConfigError(
            f"Config file not found: {path}. Copy config.example.yaml to config.yaml and update paths."
        )

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    apply_runtime_env_overrides(data)
    validate_config(data)
    return AppConfig(raw=data, config_path=path)


def validate_config(data: dict[str, Any]) -> None:
    """Validate required structure and fixed study constraints."""

    missing_top_level = sorted(REQUIRED_TOP_LEVEL_KEYS - set(data))
    if missing_top_level:
        raise ConfigError(f"Missing required config sections: {', '.join(missing_top_level)}.")

    start_date = _parse_iso_date(data["study_period"].get("start"), "study_period.start")
    end_date = _parse_iso_date(data["study_period"].get("end"), "study_period.end")
    if start_date > EXPECTED_STUDY_PERIOD[0] or end_date < EXPECTED_STUDY_PERIOD[1]:
        raise ConfigError("Study period must include the full 2015-01-01 to 2026-12-31 window.")

    sources = data["sources"]
    if len(sources) != EXPECTED_SOURCE_COUNT:
        raise ConfigError(f"Expected exactly 8 sources, found {len(sources)}.")
    _validate_sources(sources)

    missing_paths = sorted(REQUIRED_PATH_KEYS - set(data["paths"]))
    if missing_paths:
        raise ConfigError(f"Missing required config paths: {', '.join(missing_paths)}.")


def apply_runtime_env_overrides(data: dict[str, Any]) -> None:
    """Apply supported runtime overrides from environment variables."""

    runtime = data.setdefault("runtime", {})
    for env_name, (config_key, caster) in RUNTIME_ENV_OVERRIDES.items():
        raw_value = os.getenv(env_name)
        if raw_value is None or raw_value == "":
            continue
        try:
            runtime[config_key] = caster(raw_value)
        except ValueError as exc:
            raise ConfigError(f"{env_name} must be parseable as {caster.__name__}.") from exc


def _validate_sources(sources: list[dict[str, Any]]) -> None:
    """Validate source definitions."""

    slugs = set()
    for index, source in enumerate(sources, start=1):
        missing_keys = sorted(REQUIRED_SOURCE_KEYS - set(source))
        if missing_keys:
            raise ConfigError(
                f"Source #{index} ({source.get('name', 'unknown')}) missing keys: {', '.join(missing_keys)}."
            )
        discovery = source["discovery"]
        missing_discovery = sorted(REQUIRED_DISCOVERY_KEYS - set(discovery))
        if missing_discovery:
            raise ConfigError(
                f"Source '{source['slug']}' missing discovery keys: {', '.join(missing_discovery)}."
            )
        if not isinstance(source["entry_points"], list) or not source["entry_points"]:
            raise ConfigError(f"Source '{source['slug']}' must define at least one entry point.")
        for entry_point in source["entry_points"]:
            for key in ("kind", "url", "pagination"):
                if key not in entry_point:
                    raise ConfigError(
                        f"Source '{source['slug']}' entry point missing required key: {key}."
                    )
        slugs.add(str(source["slug"]))

    if slugs != EXPECTED_SOURCE_SLUGS:
        missing = sorted(EXPECTED_SOURCE_SLUGS - slugs)
        extra = sorted(slugs - EXPECTED_SOURCE_SLUGS)
        details = []
        if missing:
            details.append(f"missing expected slugs: {', '.join(missing)}")
        if extra:
            details.append(f"unexpected slugs: {', '.join(extra)}")
        raise ConfigError(f"Source set mismatch: {'; '.join(details)}.")


def _parse_iso_date(value: Any, field_name: str) -> date:
    """Parse an ISO date field."""

    if not isinstance(value, str):
        raise ConfigError(f"{field_name} must be an ISO date string.")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ConfigError(f"{field_name} must be a valid ISO date.") from exc
