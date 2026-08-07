"""Score the pipeline against the locked, hand-labelled test set.

This is the first honest measurement the project has had. Everything previously
reported was in-sample: the 200-row set was re-scored after the rules had been
tuned on it (review §5.2), so 0.656 macro F1 was a training-set number.

Three properties this scorer enforces that the old one did not.

**Weighting.** The locked set deliberately oversamples the rows the pipeline
*dropped*, because that is the only way to see false negatives (review §5.1).
So raw sample rates describe the sample, not the inventory. Every metric here is
weighted by ``inclusion_weight`` (= stratum population / stratum sampled) to
recover population-scale estimates. Unweighted numbers are reported alongside,
labelled as such, purely as a sanity check.

**Vocabulary validation.** ``manual_score.py`` accepted any string as truth,
which is how a literal ``unkown`` typo became a truth class with 17 rows
(review §5.4). This hard-fails on any value outside
``locked_test_set.TRUTH_VOCABULARIES``.

**Partial labelling.** The annotation tool serves rows interleaved across
strata, so the first N labelled rows are a balanced miniature of the full
design. This scorer therefore works on however many rows are done, reports
per-stratum coverage, and states a confidence interval that reflects the actual
sample size rather than pretending to the full 395.

Usage
-----
    python -m landslide_inventory.run --stage score_locked
"""

from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import logging

from ..config import AppConfig
from ..utils import ensure_directory
from .common import iso_now, write_csv
from .locked_test_set import OUTPUT_STEM, TRUTH_VOCABULARIES

LOGGER = logging.getLogger(__name__)

# A row counts as labelled once the primary judgement is filled. Rows the
# annotator has not reached yet are excluded rather than treated as negatives.
PRIMARY_FIELD = 'is_landslide_event_true'


def load_filled_labels(path: Path) -> list[dict[str, str]]:
    with path.open(encoding='utf-8-sig', newline='') as handle:
        return [row for row in csv.DictReader(handle)]


def validate_vocabularies(rows: Sequence[Mapping[str, str]]) -> list[str]:
    """Return every out-of-vocabulary truth value found. Empty means clean."""

    problems: list[str] = []
    for row in rows:
        for field, allowed in TRUTH_VOCABULARIES.items():
            value = (row.get(field) or '').strip()
            if value and value not in allowed:
                problems.append(
                    f"{row.get('row_id', '?')}: {field}={value!r} not in {sorted(allowed)}"
                )
    return problems


def _truth_headline(row: Mapping[str, str]) -> bool | None:
    """The definition the pipeline implements, per docs/ANNOTATION_RUBRIC.md.

    A headline event is a real landslide-family hazard in Nepal, reported as a
    single event. Returns None when the annotator could not decide, so unclear
    rows are excluded from the metric rather than silently counted as negatives.
    """

    event = (row.get('is_landslide_event_true') or '').strip()
    nepal = (row.get('in_nepal_true') or '').strip()
    hazard = (row.get('hazard_type_true') or '').strip()
    grain = (row.get('event_granularity_true') or '').strip()
    if not event:
        return None
    if event == 'unclear' or nepal == 'unclear':
        return None
    if event == 'no' or nepal == 'no':
        return False
    if hazard in {'avalanche', 'flood', 'other_hazard', 'not_a_hazard'}:
        return False
    if grain == 'roundup':
        return False
    if hazard == 'unclear' or grain == 'unclear':
        return None
    return True


def _predicted_headline(pred: Mapping[str, str]) -> bool:
    """What the pipeline decided for this row: did it become a kept class-1 event?"""

    return (pred.get('pipeline_decision') or '') == 'kept_class1'


def _wilson(successes: float, total: float, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval -- behaves sensibly at small n and near 0/1.

    A normal-approximation interval would give nonsense bounds on 30 labelled
    rows, which is exactly the regime this scorer is designed to run in.
    """

    if total <= 0:
        return (0.0, 1.0)
    p = successes / total
    denom = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denom
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denom
    return (max(0.0, centre - margin), min(1.0, centre + margin))


def score(
    labels: Sequence[Mapping[str, str]],
    predictions: Mapping[str, Mapping[str, str]],
) -> dict[str, Any]:
    """Weighted confusion matrix and derived metrics on the labelled subset."""

    cells = {'tp': 0.0, 'fp': 0.0, 'fn': 0.0, 'tn': 0.0}
    raw = {'tp': 0, 'fp': 0, 'fn': 0, 'tn': 0}
    per_stratum: dict[str, dict[str, int]] = defaultdict(lambda: {'labelled': 0, 'total': 0})
    undecidable = 0
    examples: dict[str, list[str]] = {'fp': [], 'fn': []}

    for row in labels:
        row_id = row.get('row_id', '')
        pred = predictions.get(row_id)
        if pred is None:
            continue
        stratum = pred.get('stratum', '?')
        per_stratum[stratum]['total'] += 1
        if not (row.get(PRIMARY_FIELD) or '').strip():
            continue  # not yet reached by the annotator
        per_stratum[stratum]['labelled'] += 1

        truth = _truth_headline(row)
        if truth is None:
            undecidable += 1
            continue
        predicted = _predicted_headline(pred)
        try:
            weight = float(pred.get('inclusion_weight') or 1.0)
        except ValueError:
            weight = 1.0

        key = 'tp' if (truth and predicted) else 'fn' if truth else 'fp' if predicted else 'tn'
        cells[key] += weight
        raw[key] += 1
        if key in examples and len(examples[key]) < 8:
            examples[key].append(row.get('url', row_id))

    def _metrics(c: Mapping[str, float]) -> dict[str, float | None]:
        tp, fp, fn = c['tp'], c['fp'], c['fn']
        precision = tp / (tp + fp) if (tp + fp) else None
        recall = tp / (tp + fn) if (tp + fn) else None
        f1 = (2 * precision * recall / (precision + recall)
              if precision and recall and (precision + recall) else None)
        return {'precision': precision, 'recall': recall, 'f1': f1}

    weighted = _metrics(cells)
    unweighted = _metrics({k: float(v) for k, v in raw.items()})

    labelled = sum(raw.values())
    ci_precision = _wilson(raw['tp'], raw['tp'] + raw['fp']) if (raw['tp'] + raw['fp']) else None
    ci_recall = _wilson(raw['tp'], raw['tp'] + raw['fn']) if (raw['tp'] + raw['fn']) else None

    return {
        'labelled_rows': labelled,
        'undecidable_rows': undecidable,
        'weighted_confusion': {k: round(v, 1) for k, v in cells.items()},
        'unweighted_confusion': dict(raw),
        'weighted': weighted,
        'unweighted_sample_only': unweighted,
        'precision_ci95_unweighted': ci_precision,
        'recall_ci95_unweighted': ci_recall,
        'per_stratum_coverage': {k: dict(v) for k, v in sorted(per_stratum.items())},
        'false_positive_examples': examples['fp'],
        'false_negative_examples': examples['fn'],
    }


def _format(report: Mapping[str, Any]) -> str:
    lines = []
    n = report['labelled_rows']
    lines.append(f"Labelled rows scored: {n}  (undecidable, excluded: {report['undecidable_rows']})")
    if n < 30:
        lines.append('  NOTE: fewer than 30 rows. Treat these as a smoke test of the')
        lines.append('  rubric, not as a measurement.')
    lines.append('')
    lines.append('  Weighted to population (this is the number to report):')
    for key in ('precision', 'recall', 'f1'):
        value = report['weighted'][key]
        lines.append(f"    {key:10s} {value:.3f}" if value is not None else f"    {key:10s} n/a")
    lines.append('')
    lines.append('  Unweighted, sample only (sanity check, do NOT report):')
    for key in ('precision', 'recall', 'f1'):
        value = report['unweighted_sample_only'][key]
        lines.append(f"    {key:10s} {value:.3f}" if value is not None else f"    {key:10s} n/a")
    for label, key in (('precision', 'precision_ci95_unweighted'), ('recall', 'recall_ci95_unweighted')):
        ci = report.get(key)
        if ci:
            lines.append(f"    {label} 95% CI  [{ci[0]:.2f}, {ci[1]:.2f}]")
    lines.append('')
    lines.append('  Stratum coverage (labelled / sampled):')
    for stratum, counts in report['per_stratum_coverage'].items():
        lines.append(f"    {stratum:28s} {counts['labelled']:3d} / {counts['total']:3d}")
    return '\n'.join(lines)


def run_score_locked_stage(config: AppConfig) -> dict[str, Any]:
    """Score whatever has been labelled so far."""

    outputs_dir = config.resolve_path('outputs_dir')
    ensure_directory(outputs_dir)
    # Prefer the hand-edited spreadsheet when present; fall back to the tool
    # export. Both carry the same columns keyed on row_id.
    edited = outputs_dir / f'{OUTPUT_STEM}_LABEL_HERE.csv'
    filled = edited if edited.exists() else outputs_dir / f'{OUTPUT_STEM}_labels_filled.csv'
    predictions_path = outputs_dir / f'{OUTPUT_STEM}_predictions.csv'

    if not filled.exists():
        raise FileNotFoundError(
            f'No labelled file at {filled}.\n'
            'Export from tools/annotate.html and save it there.'
        )

    labels = load_filled_labels(filled)
    problems = validate_vocabularies(labels)
    if problems:
        # Hard failure by design: silently accepting an out-of-vocabulary value
        # is how 'unkown' became a truth class with 17 rows.
        raise ValueError(
            'Out-of-vocabulary truth values found:\n  ' + '\n  '.join(problems[:20])
        )

    with predictions_path.open(encoding='utf-8', newline='') as handle:
        predictions = {row['row_id']: row for row in csv.DictReader(handle)}

    report = score(labels, predictions)
    report['generated_at'] = iso_now()

    report_path = outputs_dir / 'locked_test_set_v1_score.json'
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    for line in _format(report).splitlines():
        LOGGER.info(line)
    LOGGER.info('Report written to %s', report_path)
    return report
