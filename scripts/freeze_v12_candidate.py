#!/usr/bin/env python3
"""Freeze the reconciled v1.2 diagnostic rebuild as a candidate release."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RELEASE_ID = "nepal_landslide_inventory_v1.2.0_candidate_20260929"
DIAGNOSTIC_DIR = ROOT / "data/outputs/v12_pipeline_diagnostic"
EXPECTED_CANONICAL_SHA256 = "0c077fab7290b3fbc3f9a74dacb3adfa827e19466433221b4424b4cd75162643"
EXPECTED_DATABASE_SHA256 = "f5af3c3c0d256f74d9350a6190ff2152216f8d08f0cc311e83c9d221d7e1a9aa"
EXPECTED_ROWS = 2160


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def csv_event_ids(path: Path) -> list[str]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return [row["event_id"] for row in csv.DictReader(handle)]


def database_event_ids(path: Path) -> list[str]:
    with sqlite3.connect(path) as connection:
        return [
            row[0]
            for row in connection.execute(
                "SELECT event_id FROM canonical_events ORDER BY event_id"
            )
        ]


def file_entry(path: Path) -> dict[str, Any]:
    return {"file": path.name, "bytes": path.stat().st_size, "sha256": sha256(path)}


def freeze(root: Path, output_dir: Path, *, force: bool = False) -> Path:
    diagnostic_dir = root / "data/outputs/v12_pipeline_diagnostic"
    canonical_source = diagnostic_dir / "outputs/canonical_events_final.csv"
    database_source = diagnostic_dir / "landslide_inventory.sqlite"
    diagnostic_manifest_source = diagnostic_dir / "diagnostic_manifest.json"
    if sha256(canonical_source) != EXPECTED_CANONICAL_SHA256:
        raise RuntimeError("Canonical export differs from the reconciled v1.2 candidate")
    if sha256(database_source) != EXPECTED_DATABASE_SHA256:
        raise RuntimeError("Diagnostic database differs from the reconciled v1.2 candidate")
    diagnostic_manifest = json.loads(diagnostic_manifest_source.read_text(encoding="utf-8"))
    if diagnostic_manifest["canonical_export_sha256"] != EXPECTED_CANONICAL_SHA256:
        raise RuntimeError("Diagnostic manifest does not lock the expected canonical export")
    if diagnostic_manifest["after"]["canonical_events"] != EXPECTED_ROWS:
        raise RuntimeError("Diagnostic manifest has an unexpected canonical row count")

    if output_dir.exists():
        if not force:
            raise FileExistsError(f"Candidate directory already exists: {output_dir}")
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    sources = {
        "canonical_events_final.csv": canonical_source,
        "landslide_inventory.sqlite": database_source,
        "diagnostic_manifest.json": diagnostic_manifest_source,
        "article_corrections.csv": root / "corrections/article_corrections.csv",
        "dedup_merge_overrides.csv": root / "corrections/dedup_merge_overrides.csv",
        "V12_PIPELINE_REPAIR_PASS_3.md": root / "docs/V12_PIPELINE_REPAIR_PASS_3.md",
        "V12_CORRECTION_RECONCILIATION.md": root / "docs/V12_CORRECTION_RECONCILIATION.md",
    }
    for name, source in sources.items():
        shutil.copy2(source, output_dir / name)

    canonical = output_dir / "canonical_events_final.csv"
    database = output_dir / "landslide_inventory.sqlite"
    csv_ids = sorted(csv_event_ids(canonical))
    db_ids = database_event_ids(database)
    with sqlite3.connect(database) as connection:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    checks = {
        "canonical_sha_locked": sha256(canonical) == EXPECTED_CANONICAL_SHA256,
        "database_sha_locked": sha256(database) == EXPECTED_DATABASE_SHA256,
        "expected_2160_rows": len(csv_ids) == EXPECTED_ROWS,
        "unique_event_ids": len(csv_ids) == len(set(csv_ids)),
        "csv_sqlite_event_ids_equal": csv_ids == db_ids,
        "sqlite_integrity_ok": integrity == "ok",
        "fresh_locked_validation_complete": False,
    }
    if not all(value for key, value in checks.items() if key != "fresh_locked_validation_complete"):
        raise RuntimeError(f"Candidate freeze checks failed: {checks}")

    files = [file_entry(output_dir / name) for name in sources]
    bundle_lock_hash = hashlib.sha256(
        json.dumps(files, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    manifest = {
        "release_id": RELEASE_ID,
        "status": "pending_fresh_validation",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "supersedes": "nepal_landslide_inventory_v1.1.0_candidate_20260928",
        "canonical_summary": {
            "rows": len(csv_ids),
            "unique_event_ids": len(set(csv_ids)),
            "sha256": sha256(canonical),
        },
        "checks": checks,
        "files": files,
        "bundle_lock_hash": bundle_lock_hash,
        "inputs": {
            str(source.relative_to(root)): sha256(source)
            for source in sources.values()
        }
        | {str(Path(__file__).resolve().relative_to(root)): sha256(Path(__file__).resolve())},
        "notes": (
            "Frozen from the reconciled isolated v1.2 rebuild. Prior validation metrics "
            "do not validate this candidate; promotion requires the new locked sample."
        ),
    }
    manifest_path = output_dir / "release_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    output_dir = (
        args.output_dir.resolve()
        if args.output_dir
        else root / "data/releases" / RELEASE_ID
    )
    manifest = freeze(root, output_dir, force=args.force)
    print(f"Wrote frozen v1.2 candidate manifest to {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
