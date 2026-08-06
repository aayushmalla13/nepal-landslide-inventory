"""Non-destructive decision log for the filter stages.

Why this module exists
----------------------
``event_specificity`` and ``scope_filter`` demote rows by running

    UPDATE article_events
    SET district = NULL, event_date_ad = NULL, deaths = NULL, ...

against the same row they are judging. Two consequences, both bad
(docs/TECHNICAL_REVIEW.md section 2.2):

**Provenance is destroyed.** Once a row is demoted you can no longer answer
"what did the extractor actually find here?" -- which is the first question any
error analysis asks, and the exact question needed to audit the ``by landslide``
false negatives. The only recovery path is a full re-run of ``extract``
(spaCy over 4,453 documents).

**The stages are not idempotent.** A second run of ``event_specificity`` reads
``district = NULL``, so ``has_location_anchor`` flips, the additive score
changes, and the recorded reason can change. The README claims all stages are
idempotent. They are not.

What this module does
---------------------
Records, for every (url, stage) pair, the decision that was made *and the field
values as they stood before the stage touched them*. The preserved snapshot is
written **once** and never overwritten, so it always reflects the state closest
to the extractor no matter how many times a stage re-runs.

``restore_preserved_fields`` then lets a stage read the extractor's original
view instead of its own previous mutation, which is what makes re-runs
idempotent.

What this module does NOT do
----------------------------
It does not make ``article_events`` immutable. That is the correct end state
(review section 7, Redesign item 3: every filter writes an immutable decision row
and never mutates ``article_events``), but it requires reworking ``dedup`` and
``location_consistency``, which read class/district/in_nepal directly off
``article_events``. This module is the enabling step: it makes the mutation
*recoverable* and the stages *repeatable*, without changing what the pipeline
currently produces.

Known limitation on existing data
---------------------------------
For rows that were already demoted before this module existed, the fields are
already NULL, so the first snapshot preserves NULLs. Provenance for those rows
is genuinely gone and can only be recovered by re-running ``extract``. New
demotions from here on are fully recoverable.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Iterable, Mapping, Sequence

from ..utils import utc_now_iso

LOGGER = logging.getLogger(__name__)

# Exactly the columns that the filter stages NULL out on demotion. Keep this in
# sync with the UPDATE statements in event_specificity.py and scope_filter.py --
# a column that is nulled but not listed here is a silent provenance hole.
PRESERVED_FIELDS: tuple[str, ...] = (
    'class',
    'event_class',
    'event_date_ad',
    'district',
    'province',
    'municipality',
    'ward',
    'place_admin_level',
    'place_name_raw',
    'place_candidates_json',
    'deaths',
    'missing',
    'injured',
    'trigger',
    'conf_class',
    'conf_date',
    'conf_district',
    'conf_place',
    'conf_fatalities',
    'conf_trigger',
)

CREATE_ARTICLE_DECISIONS = """
CREATE TABLE IF NOT EXISTS article_decisions (
    url TEXT NOT NULL,
    stage TEXT NOT NULL,
    decision INTEGER NOT NULL,
    reason TEXT NOT NULL,
    score REAL,
    updated_class INTEGER,
    -- JSON snapshot of PRESERVED_FIELDS as they were BEFORE this stage ran.
    -- Written once on first decision and never overwritten, so it always
    -- reflects the extractor's original view.
    preserved_fields_json TEXT,
    first_decided_at TEXT NOT NULL,
    decided_at TEXT NOT NULL,
    PRIMARY KEY (url, stage)
)
"""

CREATE_ARTICLE_DECISIONS_INDEX = """
CREATE INDEX IF NOT EXISTS idx_article_decisions_stage_reason
    ON article_decisions (stage, reason)
"""


def ensure_decisions_table(connection) -> None:
    """Create the decision log if it does not exist. Safe to call repeatedly."""

    connection.execute(CREATE_ARTICLE_DECISIONS)
    connection.execute(CREATE_ARTICLE_DECISIONS_INDEX)


def snapshot_fields(connection, url: str) -> dict[str, Any]:
    """Read the current values of PRESERVED_FIELDS for one article."""

    columns = ', '.join(f'"{field}"' for field in PRESERVED_FIELDS)
    row = connection.execute(
        f'SELECT {columns} FROM article_events WHERE url = ?', (url,)
    ).fetchone()
    if row is None:
        return {}
    return {field: row[index] for index, field in enumerate(PRESERVED_FIELDS)}


def record_decision(
    connection,
    url: str,
    stage: str,
    decision: int,
    reason: str,
    score: float | None = None,
    updated_class: int | None = None,
    preserved: Mapping[str, Any] | None = None,
    decided_at: str | None = None,
) -> None:
    """Log a stage decision, preserving pre-mutation field values.

    Call this **before** the stage's UPDATE, so ``preserved`` captures the
    extractor's view rather than the stage's own output.

    On conflict, the decision/reason/score are refreshed but
    ``preserved_fields_json`` and ``first_decided_at`` are deliberately left
    alone -- overwriting them on a re-run would preserve the already-mutated
    state, which defeats the purpose.
    """

    now = decided_at or utc_now_iso()
    payload = json.dumps(dict(preserved or {}), ensure_ascii=False, sort_keys=True)
    connection.execute(
        """
        INSERT INTO article_decisions (
            url, stage, decision, reason, score, updated_class,
            preserved_fields_json, first_decided_at, decided_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(url, stage) DO UPDATE SET
            decision = excluded.decision,
            reason = excluded.reason,
            score = excluded.score,
            updated_class = excluded.updated_class,
            decided_at = excluded.decided_at
        """,
        (url, stage, decision, reason, score, updated_class, payload, now, now),
    )


def load_preserved_fields(connection, stage: str) -> dict[str, dict[str, Any]]:
    """Return ``{url: preserved_fields}`` for a stage, for idempotent re-reads.

    A stage uses this to recover the extractor's original view of rows it
    previously demoted, instead of reading back its own NULLs.
    """

    preserved: dict[str, dict[str, Any]] = {}
    for url, payload in connection.execute(
        'SELECT url, preserved_fields_json FROM article_decisions WHERE stage = ? ORDER BY url',
        (stage,),
    ):
        if not payload:
            continue
        try:
            values = json.loads(payload)
        except json.JSONDecodeError:
            LOGGER.warning('Corrupt preserved_fields_json for %s at stage %s', url, stage)
            continue
        if isinstance(values, dict) and values:
            preserved[url] = values
    return preserved


def restore_preserved_fields(row_mapping: dict[str, Any], preserved: Mapping[str, Any] | None) -> dict[str, Any]:
    """Overlay preserved extractor values onto a freshly-read row.

    Only fills fields that are currently NULL: if a later stage legitimately
    *set* a value, that value wins. This is what makes a second run of a filter
    stage see the same inputs as the first.
    """

    if not preserved:
        return row_mapping
    restored = dict(row_mapping)
    for field, value in preserved.items():
        if field in restored and restored[field] is None and value is not None:
            restored[field] = value
    return restored


def decision_summary(connection, stage: str | None = None) -> list[dict[str, Any]]:
    """Counts by (stage, reason). Cheap sanity check after a run."""

    if stage:
        rows = connection.execute(
            'SELECT stage, reason, COUNT(*) FROM article_decisions WHERE stage = ? '
            'GROUP BY stage, reason ORDER BY COUNT(*) DESC',
            (stage,),
        )
    else:
        rows = connection.execute(
            'SELECT stage, reason, COUNT(*) FROM article_decisions '
            'GROUP BY stage, reason ORDER BY stage, COUNT(*) DESC'
        )
    return [{'stage': r[0], 'reason': r[1], 'count': r[2]} for r in rows]


def preserved_field_recovery_rate(connection, stage: str) -> dict[str, Any]:
    """How much provenance the log actually holds, per field.

    Rows demoted before this module existed have NULL preserved values -- the
    information is gone. This reports that honestly rather than implying the
    log is complete.
    """

    preserved = load_preserved_fields(connection, stage)
    total = len(preserved)
    if total == 0:
        return {'stage': stage, 'rows': 0, 'recoverable': {}}
    recoverable = {
        field: sum(1 for values in preserved.values() if values.get(field) is not None)
        for field in PRESERVED_FIELDS
    }
    return {'stage': stage, 'rows': total, 'recoverable': recoverable}
