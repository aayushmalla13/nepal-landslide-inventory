#!/usr/bin/env python3
"""Draw the locked, blinded final validation sample for the v0.9 candidate."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_core_drawer():
    path = Path(__file__).with_name("draw_v08_fresh_validation.py")
    spec = importlib.util.spec_from_file_location("v08_fresh_draw_core", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load fresh-validation draw core: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


core = _load_core_drawer()
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "outputs"
RELEASE_ID = "nepal_landslide_inventory_v0.9.0_candidate_20260924"
RELEASE_DIR = ROOT / "data" / "releases" / RELEASE_ID
CANONICAL = RELEASE_DIR / "canonical_events_final.csv"
RELEASE_MANIFEST = RELEASE_DIR / "release_manifest.json"
CANONICAL_SHA256 = "9331668017b1ea34709acfbda34ec9a52c4ab5a02bcdc127cab0a58769379f22"
SEED = 20260924
LABELS = OUTPUT / "v09_final_validation_LABEL_HERE.csv"
READING = OUTPUT / "v09_final_validation_reading_pack.csv"
WEIGHTS = OUTPUT / "v09_final_validation_weights.csv"
MANIFEST = OUTPUT / "v09_final_validation_manifest.json"
SCORER_SCRIPT = ROOT / "scripts" / "score_v09_final_validation.py"

EXTRA_REVIEWED_FILES = (
    "v08_fresh_validation_COMPLETED.csv",
    "v09_article_mapping_DECISIONS_COMPLETED.csv",
    "v09_article_membership_MAP.csv",
    "v09_reconstruction_COLLISION_DECISIONS_COMPLETED.csv",
    "v09_reconstruction_FINAL_COLLISION_DECISIONS_COMPLETED.csv",
    "v09_remediation_BATCH_TRUE_VALUE_REVIEW_COMPLETED.csv",
    "v09_structured_attribute_REVIEW_SUBMITTED.csv",
    "v09_structured_attribute_REVIEW_COMPLETED.csv",
)
REVIEWED_FILES = (*core.REVIEWED_FILES, *EXTRA_REVIEWED_FILES)
HISTORICAL_AUDITS = (
    *core.HISTORICAL_AUDITS,
    (
        ROOT / "data/releases/nepal_landslide_inventory_v0.8.0_candidate_20260923"
        / "canonical_events_final.csv",
        OUTPUT / "v08_fresh_validation_LABEL_HERE.csv",
    ),
)


def configure_core() -> None:
    core.RELEASE_ID = RELEASE_ID
    core.RELEASE_DIR = RELEASE_DIR
    core.CANONICAL = CANONICAL
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
        row["row_id"] = f"V9F-{number:03d}"
    core.write_csv(path, rows, tuple(rows[0]))


def finalize_outputs() -> None:
    for path in (LABELS, READING, WEIGHTS):
        _rename_row_ids(path)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest["audit"] = "v09_final_locked_validation_v1"
    manifest["outputs"] = {
        path.name: core.sha256(path) for path in (LABELS, READING, WEIGHTS)
    }
    manifest["notes"] = (
        "Final independent audit of v0.9; all traceable prior reviewed events and "
        "article evidence are excluded. Promotion thresholds are unchanged from the "
        "prespecified v0.8 rule."
    )
    MANIFEST.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    configure_core()
    core.main()
    finalize_outputs()
    print(f"Finalized v0.9 audit IDs and manifest at {MANIFEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
