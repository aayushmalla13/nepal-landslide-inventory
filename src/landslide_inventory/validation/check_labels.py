"""Check a hand-edited label file before it is scored.

Editing labels in a spreadsheet is the fastest way to annotate, but it silently
introduces three failure modes that a scorer would otherwise absorb:

**Out-of-vocabulary values.** A typo like ``unkown`` becomes a truth class.
That happened before -- 17 rows of it (review section 5.4).

**Mangled Devanagari.** Excel re-saves CSV in the local code page unless told
otherwise, turning ``सिन्धुपाल्चोक`` into mojibake. Most rows still needing
labels are Nepali, so this would corrupt exactly the rows that matter.

**Structural damage.** Rows deleted, ``row_id`` altered, or the header renamed.
The locked sample is identified by its row set; losing rows silently shrinks
the test set and biases the estimate.

This reports every problem with a row reference and a suggested fix, and exits
without writing anything. Run it, fix what it names, run it again.

Usage
-----
    python -m landslide_inventory.run --stage check_labels
"""

from __future__ import annotations

import csv
import logging
import re
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from ..config import AppConfig
from .locked_test_set import OUTPUT_STEM, TRUTH_VOCABULARIES

LOGGER = logging.getLogger(__name__)

CHOICE_FIELDS = tuple(TRUTH_VOCABULARIES)
TRIGGER_VOCABULARY = ('rainfall', 'earthquake', 'anthropogenic', 'unknown')

# Sequences that appear when UTF-8 Devanagari is read back as Latin-1/cp1252.
MOJIBAKE_PATTERN = re.compile(r'à¤|à¥|â€|Ã¤|Ã¥|�')

DATE_PATTERN = re.compile(r'^\d{4}-\d{2}-\d{2}$')

# Free-text triggers map onto the controlled vocabulary unambiguously in almost
# every case; the keyword is what matters, not the phrasing.
TRIGGER_KEYWORDS = (
    ('earthquake', ('earthquake', 'seismic', 'tremor', 'भूकम्प')),
    ('anthropogenic', ('road', 'construction', 'excavat', 'quarry', 'widening',
                       'blasting', 'dozer', 'सडक', 'निर्माण')),
    ('rainfall', ('rain', 'monsoon', 'downpour', 'storm', 'cloudburst',
                  'precipitation', 'वर्षा', 'मनसुन')),
)


def normalize_trigger(value: str | None) -> str | None:
    """Map free-text trigger prose onto the controlled vocabulary.

    Order matters: an earthquake-triggered failure during road construction is
    recorded as seismic, and construction beats rain because a road-cut failure
    in the monsoon is still anthropogenic in origin.
    """

    text = (value or '').strip().casefold()
    if not text:
        return None
    if text in TRIGGER_VOCABULARY:
        return text
    for canonical, keywords in TRIGGER_KEYWORDS:
        if any(k in text for k in keywords):
            return canonical
    return 'unknown'



def _norm(value: str | None) -> str:
    return (value or '').strip()


def check(rows: Sequence[Mapping[str, str]], expected_ids: set[str]) -> dict[str, Any]:
    """Return every problem found, grouped by kind."""

    problems: dict[str, list[str]] = {
        'bad_value': [], 'mojibake': [], 'bad_date': [], 'bad_deaths': [],
        'missing_rows': [], 'unknown_rows': [], 'duplicate_rows': [],
        'trigger_freetext': [],
    }
    seen: set[str] = set()

    for row in rows:
        row_id = _norm(row.get('row_id'))
        if not row_id:
            problems['unknown_rows'].append('a row has no row_id')
            continue
        if row_id in seen:
            problems['duplicate_rows'].append(row_id)
        seen.add(row_id)
        if row_id not in expected_ids:
            problems['unknown_rows'].append(row_id)

        for field, allowed in TRUTH_VOCABULARIES.items():
            value = _norm(row.get(field))
            if value and value not in allowed:
                problems['bad_value'].append(
                    f'{row_id}: {field} = "{value}" — allowed: {" / ".join(allowed)}'
                )
        # trigger_true was offered as a free-text box, so most annotators wrote
        # prose ("Incessant monsoon rainfall"). That is a normalisation problem,
        # not a labelling error, and it does not affect the headline metric --
        # so it is a warning that carries a suggested mapping, never a blocker.
        trigger = _norm(row.get('trigger_true'))
        if trigger and trigger not in TRIGGER_VOCABULARY:
            problems['trigger_freetext'].append(
                f'{row_id}: "{trigger[:52]}" -> {normalize_trigger(trigger) or "unknown"}'
            )

        date = _norm(row.get('date_true'))
        if date and not DATE_PATTERN.match(date):
            # The commonest cause is Excel reformatting a date cell.
            problems['bad_date'].append(
                f'{row_id}: date_true = "{date}" — needs YYYY-MM-DD '
                '(Excel may have reformatted it; set the column to Text)'
            )

        deaths = _norm(row.get('deaths_true'))
        if deaths and not re.fullmatch(r'\d+', deaths):
            problems['bad_deaths'].append(f'{row_id}: deaths_true = "{deaths}" — needs a whole number or blank')

        for field in ('district_true', 'municipality_true', 'notes', 'title'):
            value = _norm(row.get(field))
            if value and MOJIBAKE_PATTERN.search(value):
                problems['mojibake'].append(
                    f'{row_id}: {field} looks corrupted — "{value[:40]}". '
                    'Re-export as CSV UTF-8 rather than plain CSV.'
                )

    missing = expected_ids - seen
    problems['missing_rows'] = sorted(missing)[:20]

    answered = sum(
        1 for row in rows
        if _norm(row.get('is_landslide_event_true'))
        and not all(_norm(row.get(f)) == 'unclear' for f in CHOICE_FIELDS)
    )
    return {
        'rows_seen': len(rows),
        'rows_expected': len(expected_ids),
        'rows_answered': answered,
        'problems': {k: v for k, v in problems.items() if v},
        'total_problems': sum(len(v) for v in problems.values()),
    }


def run_check_labels_stage(config: AppConfig) -> dict[str, Any]:
    """Validate the hand-edited label file and report anything wrong."""

    outputs_dir = config.resolve_path('outputs_dir')
    edited = outputs_dir / f'{OUTPUT_STEM}_LABEL_HERE.csv'
    fallback = outputs_dir / f'{OUTPUT_STEM}_labels_filled.csv'
    target = edited if edited.exists() else fallback
    if not target.exists():
        raise FileNotFoundError(f'No label file found at {edited} or {fallback}.')

    reference = outputs_dir / f'{OUTPUT_STEM}_labels.csv'
    with reference.open(encoding='utf-8', newline='') as handle:
        expected = {row['row_id'] for row in csv.DictReader(handle)}

    # utf-8-sig strips a BOM if present; errors='replace' turns undecodable
    # bytes into U+FFFD so the mojibake check can see them instead of crashing.
    with target.open(encoding='utf-8-sig', newline='', errors='replace') as handle:
        rows = list(csv.DictReader(handle))

    report = check(rows, expected)
    report['file'] = str(target)

    LOGGER.info('Checked %s', target.name)
    LOGGER.info('  rows: %d of %d expected | answered: %d',
                report['rows_seen'], report['rows_expected'], report['rows_answered'])
    blocking = {k: v for k, v in report['problems'].items() if k != 'trigger_freetext'}
    freetext = report['problems'].get('trigger_freetext', [])
    if freetext:
        LOGGER.info('  %d trigger_true values written as prose (not blocking; '
                    'they will be normalised): e.g.', len(freetext))
        for item in freetext[:3]:
            LOGGER.info('      %s', item)
    if not blocking:
        LOGGER.info('  nothing blocking — ready to score')
        return report
    LOGGER.warning('  %d problems found:', sum(len(v) for v in blocking.values()))
    for kind, items in blocking.items():
        LOGGER.warning('  [%s] %d', kind, len(items))
        for item in items[:10]:
            LOGGER.warning('      %s', item)
        if len(items) > 10:
            LOGGER.warning('      ... and %d more', len(items) - 10)
    return report
