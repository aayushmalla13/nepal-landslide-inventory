#!/usr/bin/env python3
"""Draw the locked, blinded final validation sample for the v1.2 candidate."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_v11_drawer():
    path = Path(__file__).with_name("draw_v11_final_validation.py")
    spec = importlib.util.spec_from_file_location("v12_fresh_draw_base", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load final-validation draw base: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = _load_v11_drawer()
core = base.core
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/outputs"
RELEASE_ID = "nepal_landslide_inventory_v1.2.0_candidate_20260929"
RELEASE_DIR = ROOT / "data/releases" / RELEASE_ID
CANONICAL = RELEASE_DIR / "canonical_events_final.csv"
DATABASE = RELEASE_DIR / "landslide_inventory.sqlite"
RELEASE_MANIFEST = RELEASE_DIR / "release_manifest.json"
CANONICAL_SHA256 = "0c077fab7290b3fbc3f9a74dacb3adfa827e19466433221b4424b4cd75162643"
SEED = 20260929
LABELS = OUTPUT / "v12_final_validation_LABEL_HERE.csv"
READING = OUTPUT / "v12_final_validation_reading_pack.csv"
WEIGHTS = OUTPUT / "v12_final_validation_weights.csv"
MANIFEST = OUTPUT / "v12_final_validation_manifest.json"
SCORER_SCRIPT = ROOT / "scripts/score_v12_final_validation.py"

EXTRA_REVIEWED_FILES = (
    "v11_final_validation_COMPLETED.csv",
    "../../corrections/article_corrections.csv",
    "../../corrections/dedup_merge_overrides.csv",
)
REVIEWED_FILES = (*base.REVIEWED_FILES, *EXTRA_REVIEWED_FILES)
HISTORICAL_AUDITS = (
    *base.HISTORICAL_AUDITS,
    (
        ROOT
        / "data/releases/nepal_landslide_inventory_v1.1.0_candidate_20260928"
        / "canonical_events_final.csv",
        OUTPUT / "v11_final_validation_LABEL_HERE.csv",
    ),
)


def configure_core() -> None:
    core.RELEASE_ID = RELEASE_ID
    core.RELEASE_DIR = RELEASE_DIR
    core.CANONICAL = CANONICAL
    core.DATABASE = DATABASE
    core.RELEASE_MANIFEST = RELEASE_MANIFEST
    core.DRAW_SCRIPT = Path(__file__).resolve()
    core.SCORER_SCRIPT = SCORER_SCRIPT
    core.LABELS = LABELS
    core.READING = READING
    core.WEIGHTS = WEIGHTS
    core.MANIFEST = MANIFEST
    core.CANONICAL_SHA256 = CANONICAL_SHA256
    core.SEED = SEED
    core.REVIEWED_FILES = REVIEWED_FILES
    core.HISTORICAL_AUDITS = HISTORICAL_AUDITS


def _rename_row_ids(path: Path) -> None:
    rows = core.read_csv(path)
    for number, row in enumerate(rows, start=1):
        row["row_id"] = f"V12F-{number:03d}"
    core.write_csv(path, rows, tuple(rows[0]))


def finalize_outputs() -> None:
    for path in (LABELS, READING, WEIGHTS):
        _rename_row_ids(path)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest["audit"] = "v12_final_locked_validation_v1"
    manifest["outputs"] = {
        path.name: core.sha256(path) for path in (LABELS, READING, WEIGHTS)
    }
    manifest["notes"] = (
        "Final independent audit of v1.2; all traceable prior reviewed event IDs "
        "and article URLs through v1.1, plus the v1.2 correction and merge layers, "
        "are excluded. Promotion thresholds are unchanged."
    )
    MANIFEST.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    configure_core()
    core.main()
    finalize_outputs()
    print(f"Finalized v1.2 audit IDs and manifest at {MANIFEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
