#!/usr/bin/env python3
"""Draw the locked, blinded final validation sample for the v1.4 candidate."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_v13_drawer():
    path = Path(__file__).with_name("draw_v13_final_validation.py")
    spec = importlib.util.spec_from_file_location("v14_fresh_draw_base", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load final-validation draw base: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = _load_v13_drawer()
core = base.core
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/outputs"
RELEASE_ID = "nepal_landslide_inventory_v1.4.0_candidate_20261002"
RELEASE_DIR = ROOT / "data/releases" / RELEASE_ID
CANONICAL = RELEASE_DIR / "canonical_events_final.csv"
DATABASE = (
    ROOT
    / "data/releases/nepal_landslide_inventory_v1.2.0_candidate_20260929"
    / "landslide_inventory.sqlite"
)
RELEASE_MANIFEST = RELEASE_DIR / "release_manifest.json"
CANONICAL_SHA256 = "bbf0f77960da94d7199268a3521715762ff833c0a4283ef3badedbe6d9ee9541"
SEED = 20261002
LABELS = OUTPUT / "v14_final_validation_LABEL_HERE.csv"
READING = OUTPUT / "v14_final_validation_reading_pack.csv"
WEIGHTS = OUTPUT / "v14_final_validation_weights.csv"
MANIFEST = OUTPUT / "v14_final_validation_manifest.json"
SCORER_SCRIPT = ROOT / "scripts/score_v14_final_validation.py"

EXTRA_REVIEWED_FILES = (
    "v13_final_validation_COMPLETED.csv",
    "v14_article_mapping_DECISIONS_COMPLETED.csv",
    "v14_article_membership_MAP.csv",
    "v14_reconstruction_COLLISION_DECISIONS_COMPLETED.csv",
    "v14_reconstruction_FINAL_COLLISION_DECISIONS_COMPLETED.csv",
    "v14_remediation_BATCH_TRUE_VALUE_REVIEW_COMPLETED.csv",
    "v14_structured_attribute_REVIEW_COMPLETED.csv",
    "v14_identity_plan_NEW_EVENTS.csv",
    "v14_identity_plan_MERGES_EXISTING.csv",
    "v14_identity_plan_REMOVE_OLD_EVENTS.csv",
    "v14_release_identity_NEW_EVENTS.csv",
    "v14_release_identity_EXCLUDED_CANDIDATES.csv",
)
REVIEWED_FILES = (*base.REVIEWED_FILES, *EXTRA_REVIEWED_FILES)
HISTORICAL_AUDITS = (
    *base.HISTORICAL_AUDITS,
    (
        ROOT
        / "data/releases/nepal_landslide_inventory_v1.3.0_candidate_20260930"
        / "canonical_events_final.csv",
        OUTPUT / "v13_final_validation_LABEL_HERE.csv",
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
        row["row_id"] = f"V14F-{number:03d}"
    core.write_csv(path, rows, tuple(rows[0]))


def finalize_outputs() -> None:
    for path in (LABELS, READING, WEIGHTS):
        _rename_row_ids(path)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest["audit"] = "v14_final_locked_validation_v1"
    manifest["outputs"] = {
        path.name: core.sha256(path) for path in (LABELS, READING, WEIGHTS)
    }
    manifest["notes"] = (
        "Final independent audit of v1.4; all traceable prior reviewed event IDs "
        "and article URLs through v1.3, plus every v1.4 remediation layer, are "
        "excluded. Promotion thresholds are unchanged."
    )
    MANIFEST.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    configure_core()
    core.main()
    finalize_outputs()
    print(f"Finalized v1.4 audit IDs and manifest at {MANIFEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
