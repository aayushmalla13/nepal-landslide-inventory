#!/usr/bin/env python3
"""Draw the locked, blinded final validation sample for the v1.5 candidate."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_v14_drawer():
    path = Path(__file__).with_name("draw_v14_final_validation.py")
    spec = importlib.util.spec_from_file_location("v15_fresh_draw_base", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load final-validation draw base: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = _load_v14_drawer()
core = base.core
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/outputs"
RELEASE_ID = "nepal_landslide_inventory_v1.5.0_candidate_20261003"
RELEASE_DIR = ROOT / "data/releases" / RELEASE_ID
CANONICAL = RELEASE_DIR / "canonical_events_final.csv"
DATABASE = ROOT / "data/releases/nepal_landslide_inventory_v1.2.0_candidate_20260929/landslide_inventory.sqlite"
RELEASE_MANIFEST = RELEASE_DIR / "release_manifest.json"
CANONICAL_SHA256 = "313745c27218be7989764cc9614b71cc69a9549ff05c483247a6c89bd276ae19"
SEED = 20261003
LABELS = OUTPUT / "v15_final_validation_LABEL_HERE.csv"
READING = OUTPUT / "v15_final_validation_reading_pack.csv"
WEIGHTS = OUTPUT / "v15_final_validation_weights.csv"
MANIFEST = OUTPUT / "v15_final_validation_manifest.json"
SCORER_SCRIPT = ROOT / "scripts/score_v15_final_validation.py"

EXTRA_REVIEWED_FILES = (
    "v14_final_validation_COMPLETED.csv",
    "v15_article_mapping_DECISIONS_COMPLETED.csv",
    "v15_article_membership_MAP.csv",
    "v15_reconstruction_COLLISION_DECISIONS_COMPLETED.csv",
    "v15_reconstruction_FINAL_COLLISION_DECISIONS_COMPLETED.csv",
    "v15_remediation_BATCH_TRUE_VALUE_REVIEW_COMPLETED.csv",
    "v15_structured_attribute_REVIEW_COMPLETED.csv",
    "v15_identity_plan_NEW_EVENTS.csv",
    "v15_identity_plan_MERGES_EXISTING.csv",
    "v15_identity_plan_REMOVE_OLD_EVENTS.csv",
    "v15_release_identity_NEW_EVENTS.csv",
    "v15_release_identity_EXCLUDED_CANDIDATES.csv",
)
REVIEWED_FILES = (*base.REVIEWED_FILES, *EXTRA_REVIEWED_FILES)
HISTORICAL_AUDITS = (
    *base.HISTORICAL_AUDITS,
    (
        ROOT / "data/releases/nepal_landslide_inventory_v1.4.0_candidate_20261002/canonical_events_final.csv",
        OUTPUT / "v14_final_validation_LABEL_HERE.csv",
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
        row["row_id"] = f"V15F-{number:03d}"
    core.write_csv(path, rows, tuple(rows[0]))


def finalize_outputs() -> None:
    for path in (LABELS, READING, WEIGHTS):
        _rename_row_ids(path)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest["audit"] = "v15_final_locked_validation_v1"
    manifest["outputs"] = {path.name: core.sha256(path) for path in (LABELS, READING, WEIGHTS)}
    manifest["notes"] = (
        "Final independent audit of v1.5; all traceable prior reviewed event IDs "
        "and article URLs through v1.4, plus every v1.5 remediation layer, are "
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
    print(f"Finalized v1.5 audit IDs and manifest at {MANIFEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
