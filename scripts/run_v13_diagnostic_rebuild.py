#!/usr/bin/env python3
"""Run the v1.3 remediation pipeline from the frozen v1.2 database."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = (
    ROOT
    / "data/releases/nepal_landslide_inventory_v1.2.0_candidate_20260929"
    / "landslide_inventory.sqlite"
)
DEFAULT_OUTPUT = ROOT / "data/outputs/v13_pipeline_diagnostic"


def _load_core():
    path = Path(__file__).with_name("run_v12_diagnostic_rebuild.py")
    spec = importlib.util.spec_from_file_location("v13_diagnostic_core", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load diagnostic rebuild core: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


core = _load_core()
STAGES = core.STAGES
diagnostic_config = core.diagnostic_config


def run_rebuild(
    root: Path,
    config_path: Path,
    source_database: Path,
    output_dir: Path,
    *,
    force: bool = False,
    resume_from: str | None = None,
) -> Path:
    return core.run_rebuild(
        root,
        config_path,
        source_database,
        output_dir,
        force=force,
        resume_from=resume_from,
        manifest_status="v13_pipeline_diagnostic_only",
        manifest_notes=(
            "Isolated v1.3 remediation rebuild from the frozen v1.2 candidate. "
            "This diagnostic does not modify or supersede the v1.2 release, and "
            "the spent v1.2 validation sample is used only for repair replay."
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--config", type=Path, default=ROOT / "config.yaml")
    parser.add_argument("--source-db", type=Path, default=DEFAULT_SOURCE)
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
