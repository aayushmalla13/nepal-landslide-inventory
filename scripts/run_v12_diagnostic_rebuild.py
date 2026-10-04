#!/usr/bin/env python3
"""Run the repaired v1.2 pipeline on an isolated database copy."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from landslide_inventory.config import AppConfig, load_config
from landslide_inventory.export import run_export_final_stage
from landslide_inventory.unify.dedup_stage import run_dedup_stage
from landslide_inventory.unify.event_specificity import run_event_specificity_stage
from landslide_inventory.unify.event_typing_stage import run_event_typing_stage
from landslide_inventory.unify.extract_stage import run_extract_stage
from landslide_inventory.unify.location_consistency import run_location_consistency_stage
from landslide_inventory.unify.reviewed_corrections import run_reviewed_corrections_stage
from landslide_inventory.unify.scope_filter import run_filter_scope_stage


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "data/outputs/v12_pipeline_diagnostic"

STAGES: tuple[tuple[str, Callable[[AppConfig], Any]], ...] = (
    ("extract", run_extract_stage),
    ("event_specificity", run_event_specificity_stage),
    ("location_consistency", run_location_consistency_stage),
    ("filter_scope", run_filter_scope_stage),
    ("corrections", run_reviewed_corrections_stage),
    ("dedup", run_dedup_stage),
    ("event_typing", run_event_typing_stage),
    ("export_final", run_export_final_stage),
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def diagnostic_config(base: AppConfig, output_dir: Path) -> AppConfig:
    raw = deepcopy(base.raw)
    raw["paths"].update(
        {
            "raw_sqlite_dir": str(output_dir),
            "intermediate_dir": str(output_dir / "intermediate"),
            "outputs_dir": str(output_dir / "outputs"),
            "caches_dir": str(output_dir / "caches"),
            "logs_dir": str(output_dir / "logs"),
        }
    )
    return AppConfig(raw=raw, config_path=base.config_path)


def database_summary(path: Path) -> dict[str, Any]:
    with sqlite3.connect(path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        summary: dict[str, Any] = {
            "raw_articles": connection.execute(
                "SELECT COUNT(*) FROM raw_articles"
            ).fetchone()[0]
        }
        if "canonical_events" in tables:
            summary["canonical_events"] = connection.execute(
                "SELECT COUNT(*) FROM canonical_events"
            ).fetchone()[0]
            columns = {
                row[1]
                for row in connection.execute("PRAGMA table_info(canonical_events)")
            }
            for field in ("event_type", "hazard_type", "event_granularity", "article_role"):
                if field in columns:
                    summary[f"by_{field}"] = dict(
                        connection.execute(
                            f"SELECT {field}, COUNT(*) FROM canonical_events GROUP BY {field}"
                        ).fetchall()
                    )
        return summary


def run_rebuild(
    root: Path,
    config_path: Path,
    source_database: Path,
    output_dir: Path,
    *,
    force: bool = False,
    resume_from: str | None = None,
    manifest_status: str = "v12_pipeline_diagnostic_only",
    manifest_notes: str = (
        "Isolated rebuild for impact measurement. This is not a candidate "
        "release and does not supersede or modify v1.1."
    ),
) -> Path:
    stage_names = [name for name, _ in STAGES]
    if resume_from is not None and resume_from not in stage_names:
        raise ValueError(f"Unknown resume stage: {resume_from}")
    if resume_from is None and output_dir.exists() and any(output_dir.iterdir()):
        if not force:
            raise FileExistsError(f"Diagnostic directory is not empty: {output_dir}")
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    copied_database = output_dir / "landslide_inventory.sqlite"
    if resume_from is None:
        shutil.copy2(source_database, copied_database)
    elif not copied_database.exists():
        raise FileNotFoundError(f"Cannot resume without copied database: {copied_database}")

    config = diagnostic_config(load_config(config_path), output_dir)
    before = database_summary(source_database)
    stage_results: dict[str, Any] = {}
    start = stage_names.index(resume_from) if resume_from is not None else 0
    for name, handler in STAGES[start:]:
        print(f"running {name}", flush=True)
        result = handler(config)
        stage_results[name] = result

    export_path = output_dir / "outputs/canonical_events_final.csv"
    manifest = {
        "status": manifest_status,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_database": str(source_database.relative_to(root)),
        "source_database_sha256": sha256(source_database),
        "diagnostic_database_sha256": sha256(copied_database),
        "canonical_export": str(export_path.relative_to(root)),
        "canonical_export_sha256": sha256(export_path),
        "before": before,
        "after": database_summary(copied_database),
        "stage_results": stage_results,
        "stages": [name for name, _ in STAGES],
        "resumed_from": resume_from,
        "notes": manifest_notes,
    }
    manifest_path = output_dir / "diagnostic_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--config", type=Path, default=ROOT / "config.yaml")
    parser.add_argument(
        "--source-db",
        type=Path,
        default=ROOT / "data/raw_sqlite/landslide_inventory.sqlite",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--resume-from", choices=[name for name, _ in STAGES])
    args = parser.parse_args()
    manifest = run_rebuild(
        args.root.resolve(),
        args.config.resolve(),
        args.source_db.resolve(),
        args.output_dir.resolve(),
        force=args.force,
        resume_from=args.resume_from,
    )
    print(f"wrote {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
