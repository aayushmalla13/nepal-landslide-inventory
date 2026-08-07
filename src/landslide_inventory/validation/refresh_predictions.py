"""Regenerate the locked test set's prediction side against the current pipeline.

Why this exists
---------------
``locked_test_set`` writes two files: ``*_labels.csv`` (blind, what the
annotator sees) and ``*_predictions.csv`` (what the pipeline said). The
predictions were written **once, when the sample was drawn**. Every pipeline fix
since then leaves them stale, and scoring against a stale prediction file
measures the pipeline as it was on the draw date, not as it is.

This was caught the first time the set was scored. Row ``v1-0025``
("11 people missing in Sankhuwasabha as eight houses are swept away by
landslide") read ``dropped_scope / metaphor`` in the prediction file — that is
the ``by landslide`` substring bug — while the current pipeline correctly has it
as ``class=1 event_specific``. Eight of nine apparent disagreements were against
code that no longer exists.

What is and is not locked
-------------------------
The lock covers **which rows are in the sample** — the URL list, hashed in the
manifest. That is what must never change, because re-drawing after seeing
results is how a test set gets burned.

Predictions are not part of the lock. They are the *system under test*, and they
are supposed to change every time the pipeline changes. Refreshing them is not
only permitted, it is required for the score to mean anything.

This module verifies the label file still matches the manifest hash before
touching anything, so a refresh can never quietly paper over an edited sample.
"""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import Any

from ..config import AppConfig
from ..db import connect_sqlite
from ..utils import ensure_directory
from .common import write_csv
from .locked_test_set import (
    OUTPUT_STEM,
    PREDICTION_COLUMNS,
    classify_decision,
    verify_locked_manifest,
)

LOGGER = logging.getLogger(__name__)


def current_predictions(connection, urls: list[str]) -> dict[str, dict[str, Any]]:
    """Read the pipeline's present verdict for each locked URL."""

    out: dict[str, dict[str, Any]] = {}
    query = """
        SELECT e.url, e.class AS class_pred, e.in_nepal AS in_nepal_pred,
               e.district AS district_pred, e.municipality AS municipality_pred,
               e.event_date_ad AS event_date_pred, e.deaths AS deaths_pred,
               e.missing AS missing_pred, e.injured AS injured_pred,
               e.trigger AS trigger_pred, e.specificity_ok, e.specificity_reason,
               e.specificity_score, e.scope_reason, e.location_consistent,
               e.location_reason
        FROM article_events e WHERE e.url = ?
    """
    for url in urls:
        row = connection.execute(query, (url,)).fetchone()
        out[url] = dict(row) if row is not None else {}
    return out


def run_refresh_predictions_stage(config: AppConfig) -> dict[str, Any]:
    """Rewrite ``*_predictions.csv`` from the current database.

    Refuses to run if the label file no longer matches the manifest hash --
    that would mean the locked sample itself had been edited, which invalidates
    it as a held-out set and is not something to silently work around.
    """

    outputs_dir = config.resolve_path('outputs_dir')
    ensure_directory(outputs_dir)
    labels_path = outputs_dir / f'{OUTPUT_STEM}_labels.csv'
    predictions_path = outputs_dir / f'{OUTPUT_STEM}_predictions.csv'
    manifest_path = outputs_dir / f'{OUTPUT_STEM}_manifest.json'

    if not verify_locked_manifest(manifest_path, labels_path):
        raise ValueError(
            f'{labels_path.name} no longer matches the manifest hash. The locked '
            'sample has been edited, which invalidates it as a held-out set. '
            'Refusing to refresh predictions against a compromised sample.'
        )

    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    strata = manifest['strata']

    with labels_path.open(encoding='utf-8', newline='') as handle:
        rows = list(csv.DictReader(handle))

    with connect_sqlite(config.sqlite_path) as connection:
        current = current_predictions(connection, [r['url'] for r in rows])

    records: list[dict[str, Any]] = []
    changed = 0
    with predictions_path.open(encoding='utf-8', newline='') as handle:
        previous = {r['row_id']: r for r in csv.DictReader(handle)}

    for row in rows:
        item = current.get(row['url'], {})
        decision = classify_decision(
            has_event_row=bool(item),
            event_class=item.get('class_pred'),
            in_nepal=item.get('in_nepal_pred'),
            specificity_ok=item.get('specificity_ok'),
        )
        # Stratum and weight come from the manifest, not recomputed: they are
        # properties of the sampling design, fixed at draw time. Recomputing
        # them from the new pipeline state would silently change the weights
        # and break the population estimate.
        stratum = previous.get(row['row_id'], {}).get('stratum', '')
        record: dict[str, Any] = {
            'row_id': row['row_id'],
            'url': row['url'],
            'stratum': stratum,
            'pipeline_decision': decision,
            'inclusion_weight': (strata.get(stratum) or {}).get('inclusion_weight'),
        }
        for column in PREDICTION_COLUMNS:
            if column not in record:
                record[column] = item.get(column)
        records.append(record)
        if previous.get(row['row_id'], {}).get('pipeline_decision') != decision:
            changed += 1

    write_csv(predictions_path, PREDICTION_COLUMNS, records)
    LOGGER.info(
        'Refreshed predictions for %d locked rows; %d decisions changed since the '
        'previous file', len(records), changed,
    )
    return {'rows': len(records), 'decisions_changed': changed, 'path': str(predictions_path)}
