"""Pipeline stages for probing, collecting, and exporting external records."""

from __future__ import annotations

import json
import logging
import os
import uuid
from pathlib import Path
from typing import Any

from ..config import AppConfig
from .base import ProbeResult
from .http import ExternalHttpClient
from .registry import adapter_class
from .storage import (
    export_external_records,
    finish_source_run,
    source_counts,
    start_source_run,
    upsert_external_records,
)

LOGGER = logging.getLogger(__name__)


def _settings(config: AppConfig) -> dict[str, Any]:
    settings = dict(config.raw.get("external_sources", {}))
    settings.setdefault("sources", [])
    return settings


def _selected_sources(config: AppConfig, *, include_disabled: bool = False) -> list[dict[str, Any]]:
    settings = _settings(config)
    selected = os.getenv("LS_EXTERNAL_SOURCE", "").strip()
    allowed = {value.strip() for value in selected.split(",") if value.strip()}
    sources: list[dict[str, Any]] = []
    for source in settings.get("sources", []):
        if allowed and source.get("slug") not in allowed:
            continue
        # An explicit LS_EXTERNAL_SOURCE selection is an intentional one-off run,
        # even when the source is disabled for routine batch collection.
        if not include_disabled and not allowed and not source.get("enabled", False):
            continue
        item = dict(source)
        item["config_dir"] = str(config.config_path.parent)
        sources.append(item)
    if allowed:
        found = {str(source.get("slug")) for source in sources}
        missing = allowed - found
        if missing:
            raise ValueError(f"Unknown LS_EXTERNAL_SOURCE values: {', '.join(sorted(missing))}")
    return sources


def _client(config: AppConfig, settings: dict[str, Any]) -> ExternalHttpClient:
    runtime = config.raw.get("runtime", {})
    return ExternalHttpClient(
        user_agent=str(
            settings.get("user_agent", runtime.get("user_agent", "landslide-inventory/0.1"))
        ),
        timeout_seconds=float(settings.get("timeout_seconds", runtime.get("timeout_seconds", 30))),
        retries=int(settings.get("retries", runtime.get("retries", 3))),
        rate_limit_seconds=float(
            settings.get("rate_limit_seconds", runtime.get("rate_limit_seconds", 0))
        ),
    )


def collect_external_sources(
    config: AppConfig, client: ExternalHttpClient | None = None
) -> dict[str, int]:
    """Collect every enabled source; one failure does not erase other results."""

    settings = _settings(config)
    http_client = client or _client(config, settings)
    counts: dict[str, int] = {}
    failures: list[str] = []
    for source_config in _selected_sources(config):
        slug = str(source_config["slug"])
        adapter_name = str(source_config["adapter"])
        run_id = f"external-{slug}-{uuid.uuid4().hex}"
        start_source_run(config.sqlite_path, run_id, slug, adapter_name)
        try:
            adapter = adapter_class(adapter_name)(slug, source_config, http_client)
            records = adapter.collect()
            stored = upsert_external_records(config.sqlite_path, records)
            finish_source_run(
                config.sqlite_path,
                run_id,
                status="complete",
                fetched_count=len(records),
                stored_count=stored,
            )
            counts[slug] = stored
            LOGGER.info("External source %s: fetched=%s stored=%s", slug, len(records), stored)
        except Exception as exc:
            finish_source_run(config.sqlite_path, run_id, status="failed", error=str(exc))
            failures.append(f"{slug}: {exc}")
            LOGGER.exception("External source %s failed", slug)
    if failures:
        raise RuntimeError("External collection failures: " + "; ".join(failures))
    return counts


def probe_external_sources(
    config: AppConfig, client: ExternalHttpClient | None = None
) -> list[ProbeResult]:
    """Probe all configured sources, including disabled ones, without writing records."""

    settings = _settings(config)
    http_client = client or _client(config, settings)
    results: list[ProbeResult] = []
    for source_config in _selected_sources(config, include_disabled=True):
        slug = str(source_config["slug"])
        adapter_name = str(source_config["adapter"])
        result = adapter_class(adapter_name)(slug, source_config, http_client).probe()
        results.append(result)
        LOGGER.info(
            "External probe %-24s adapter=%-20s ok=%s status=%s %s",
            result.source,
            adapter_name,
            result.ok,
            result.status,
            result.message,
        )
    return results


def run_external_collect_stage(config: AppConfig) -> None:
    counts = collect_external_sources(config)
    LOGGER.info("External collection complete: %s", json.dumps(counts, sort_keys=True))


def run_external_probe_stage(config: AppConfig) -> None:
    results = probe_external_sources(config)
    failed = [result.source for result in results if not result.ok]
    LOGGER.info("External probes: %s configured, %s unavailable", len(results), len(failed))


def run_external_export_stage(config: AppConfig) -> None:
    settings = _settings(config)
    configured = Path(str(settings.get("output_csv", "data/outputs/external_records.csv")))
    output = (
        configured
        if configured.is_absolute()
        else (config.config_path.parent / configured).resolve()
    )
    study_period = config.raw["study_period"]
    count = export_external_records(
        config.sqlite_path,
        output,
        start_date=str(study_period["start"]),
        end_date=str(study_period["end"]),
    )
    LOGGER.info(
        "Exported %s external records to %s; source counts=%s",
        count,
        output,
        source_counts(config.sqlite_path),
    )
