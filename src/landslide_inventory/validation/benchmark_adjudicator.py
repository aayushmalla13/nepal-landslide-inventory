"""Decide empirically whether LLM adjudication beats the rules.

An LLM stage should be adopted because it wins a measurement, not because it is
an LLM. This scores model verdicts against the same hand-labelled rows the rules
were scored on, so the comparison is like-for-like, and reports both so the
paper can state the trade-off honestly.

It runs only over rows ``needs_adjudication`` selects -- the judgement calls --
because that is the only place the model is claimed to help. Scoring it on rows
where the rules are already reliable would flatter both.

Usage
-----
    export ANTHROPIC_API_KEY=...
    pip install anthropic
    python -m landslide_inventory.run --stage benchmark_adjudicator

Without a key it reports what the cache alone can answer and exits cleanly.
"""

from __future__ import annotations

import csv
import json
import logging
import sqlite3
from pathlib import Path
from typing import Any

from ..config import AppConfig
from ..unify.llm_adjudicator import (
    DEFAULT_MODEL,
    ResponseCache,
    adjudicate,
    build_caller,
    needs_adjudication,
)
from ..utils import ensure_directory
from .common import iso_now
from .locked_test_set import OUTPUT_STEM
from .score_locked import _predicted_headline, _truth_headline

LOGGER = logging.getLogger(__name__)


def _metrics(tp: float, fp: float, fn: float) -> dict[str, float | None]:
    precision = tp / (tp + fp) if (tp + fp) else None
    recall = tp / (tp + fn) if (tp + fn) else None
    f1 = (2 * precision * recall / (precision + recall)
          if precision and recall and (precision + recall) else None)
    return {'precision': precision, 'recall': recall, 'f1': f1}


def run_benchmark_adjudicator_stage(config: AppConfig) -> dict[str, Any]:
    """Score rules vs LLM on the labelled judgement-call rows."""

    outputs_dir = config.resolve_path('outputs_dir')
    ensure_directory(outputs_dir)
    labels_path = outputs_dir / f'{OUTPUT_STEM}_LABEL_HERE.csv'
    if not labels_path.exists():
        labels_path = outputs_dir / f'{OUTPUT_STEM}_labels_filled.csv'
    predictions_path = outputs_dir / f'{OUTPUT_STEM}_predictions.csv'

    with labels_path.open(encoding='utf-8-sig', newline='') as handle:
        labels = list(csv.DictReader(handle))
    with predictions_path.open(encoding='utf-8', newline='') as handle:
        predictions = {row['row_id']: row for row in csv.DictReader(handle)}

    cache = ResponseCache(config.resolve_path('caches_dir') / 'llm_adjudications.json')
    # Local model first: free, no quota, and reproducible from pinned weights.
    caller, model_id = build_caller(prefer='ollama')
    connection = sqlite3.connect(f'file:{config.sqlite_path}?mode=ro', uri=True)
    connection.row_factory = sqlite3.Row

    rules = {'tp': 0.0, 'fp': 0.0, 'fn': 0.0}
    llm = {'tp': 0.0, 'fp': 0.0, 'fn': 0.0}
    considered = skipped_no_verdict = 0

    for row in labels:
        pred = predictions.get(row['row_id'])
        if pred is None:
            continue
        truth = _truth_headline(row)
        if truth is None:
            continue
        try:
            score_ = float(pred.get('specificity_score') or 0.0)
        except ValueError:
            score_ = 0.0
        if not needs_adjudication(pred.get('specificity_reason'), score_):
            continue
        considered += 1

        weight = float(pred.get('inclusion_weight') or 1.0)
        rule_says = _predicted_headline(pred)
        for bucket, says in (('rules', rule_says),):
            target = rules
            key = 'tp' if (truth and says) else 'fn' if truth else 'fp' if says else None
            if key:
                target[key] += weight

        article = connection.execute(
            'SELECT COALESCE(title, \'\') AS t, COALESCE(text, \'\') AS x '
            'FROM raw_articles WHERE url = ?', (pred['url'],)
        ).fetchone()
        verdict = adjudicate(
            article['t'] if article else None,
            article['x'] if article else None,
            cache=cache, call_model=caller, model=model_id,
        )
        if verdict is None:
            skipped_no_verdict += 1
            continue
        llm_says = verdict.is_headline_event
        key = 'tp' if (truth and llm_says) else 'fn' if truth else 'fp' if llm_says else None
        if key:
            llm[key] += weight

    cache.save()
    report = {
        'generated_at': iso_now(),
        'model': model_id,
        'rows_considered': considered,
        'rows_without_verdict': skipped_no_verdict,
        'cache_entries': len(cache),
        'rules': _metrics(rules['tp'], rules['fp'], rules['fn']),
        'llm': _metrics(llm['tp'], llm['fp'], llm['fn']) if considered > skipped_no_verdict else None,
    }
    (outputs_dir / 'adjudicator_benchmark.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    LOGGER.info('Judgement-call rows scored: %d (no verdict for %d)', considered, skipped_no_verdict)
    if report['llm'] is None:
        LOGGER.warning(
            'No model verdicts available. Easiest free option:\n'
            '    curl -fsSL https://ollama.com/install.sh | sh\n'
            '    ollama pull qwen2.5:7b\n'
            '    ollama serve\n'
            'then re-run this stage. No account, no key, no quota.')
        return report
    for name in ('rules', 'llm'):
        m = report[name]
        LOGGER.info('  %-6s precision %s recall %s F1 %s', name,
                    *[f'{m[k]:.3f}' if m[k] is not None else '  n/a' for k in ('precision', 'recall', 'f1')])
    LOGGER.info('Adopt the LLM path only if it wins here, and report both numbers either way.')
    return report
