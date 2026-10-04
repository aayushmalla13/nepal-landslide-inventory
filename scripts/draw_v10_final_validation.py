#!/usr/bin/env python3
"""Draw the locked, blinded final validation sample for the v1.0 candidate."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_core_drawer():
    path = Path(__file__).with_name('draw_v08_fresh_validation.py')
    spec = importlib.util.spec_from_file_location('v10_fresh_draw_core', path)
    if spec is None or spec.loader is None:
        raise ImportError(f'Cannot load fresh-validation draw core: {path}')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


core = _load_core_drawer()
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'data' / 'outputs'
RELEASE_ID = 'nepal_landslide_inventory_v1.0.0_candidate_20260927'
RELEASE_DIR = ROOT / 'data/releases' / RELEASE_ID
CANONICAL = RELEASE_DIR / 'canonical_events_final.csv'
DATABASE = RELEASE_DIR / 'landslide_inventory.sqlite'
RELEASE_MANIFEST = RELEASE_DIR / 'release_manifest.json'
CANONICAL_SHA256 = '68f2efd27a2c929c0df879974afcde14560ecbd6edf2ce389cc03a18f0857c8a'
SEED = 20260927
LABELS = OUTPUT / 'v10_final_validation_LABEL_HERE.csv'
READING = OUTPUT / 'v10_final_validation_reading_pack.csv'
WEIGHTS = OUTPUT / 'v10_final_validation_weights.csv'
MANIFEST = OUTPUT / 'v10_final_validation_manifest.json'
SCORER_SCRIPT = ROOT / 'scripts/score_v10_final_validation.py'

EXTRA_REVIEWED_FILES = (
    'v08_fresh_validation_COMPLETED.csv',
    'v09_article_mapping_DECISIONS_COMPLETED.csv',
    'v09_article_membership_MAP.csv',
    'v09_reconstruction_COLLISION_DECISIONS_COMPLETED.csv',
    'v09_reconstruction_FINAL_COLLISION_DECISIONS_COMPLETED.csv',
    'v09_remediation_BATCH_TRUE_VALUE_REVIEW_COMPLETED.csv',
    'v09_structured_attribute_REVIEW_SUBMITTED.csv',
    'v09_structured_attribute_REVIEW_COMPLETED.csv',
    'v09_final_validation_COMPLETED.csv',
    'dedup_collision_review_BATCH_01_COMPLETED.csv',
    'dedup_collision_review_BATCH_01_ADJUDICATED.csv',
)
REVIEWED_FILES = (*core.REVIEWED_FILES, *EXTRA_REVIEWED_FILES)
HISTORICAL_AUDITS = (
    *core.HISTORICAL_AUDITS,
    (
        ROOT / 'data/releases/nepal_landslide_inventory_v0.8.0_candidate_20260923'
        / 'canonical_events_final.csv',
        OUTPUT / 'v08_fresh_validation_LABEL_HERE.csv',
    ),
    (
        ROOT / 'data/releases/nepal_landslide_inventory_v0.9.0_candidate_20260924'
        / 'canonical_events_final.csv',
        OUTPUT / 'v09_final_validation_LABEL_HERE.csv',
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
        row['row_id'] = f'V10F-{number:03d}'
    core.write_csv(path, rows, tuple(rows[0]))


def finalize_outputs() -> None:
    for path in (LABELS, READING, WEIGHTS):
        _rename_row_ids(path)
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    manifest['audit'] = 'v10_final_locked_validation_v1'
    manifest['outputs'] = {
        path.name: core.sha256(path) for path in (LABELS, READING, WEIGHTS)
    }
    manifest['notes'] = (
        'Final independent audit of v1.0; all traceable prior reviewed event IDs '
        'and article URLs, including collision-review evidence, are excluded. '
        'Promotion thresholds are unchanged from the prespecified v0.8 rule.'
    )
    MANIFEST.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + '\n',
        encoding='utf-8',
    )


def main() -> int:
    configure_core()
    core.main()
    finalize_outputs()
    print(f'Finalized v1.0 audit IDs and manifest at {MANIFEST}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
