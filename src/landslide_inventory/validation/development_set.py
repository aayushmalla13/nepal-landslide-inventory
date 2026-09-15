"""Independent development-set sampling for pipeline tuning.

Unlike the locked test set, this artifact is explicitly for diagnosis and rule
development. It excludes every locked-test URL, every previously labelled
manual-evaluation row, and every BIPAD-assisted article before drawing a
decision-by-language sample.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections import defaultdict
from typing import Any

from ..config import AppConfig
from ..db import connect_sqlite
from ..utils import ensure_directory, stable_hash
from .common import iso_now, write_csv
from .evaluation_exclusions import collect_prior_evaluation_urls
from .locked_test_set import (
    LABEL_COLUMNS,
    PREDICTION_COLUMNS,
    FrameRow,
    load_frame,
    systematic_draw,
)

LOGGER = logging.getLogger(__name__)

DEFAULT_VERSION = 'v1'
DEFAULT_SEED = 20260810
DEFAULT_ALLOCATION = {
    'kept_class1': 60,
    'kept_class2': 50,
    'dropped_specificity': 120,
    'dropped_scope': 60,
    'dropped_other': 10,
}
def _sha256(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def allocate_balanced_languages(sizes: dict[str, int], quota: int) -> dict[str, int]:
    """Allocate a decision quota as evenly as availability permits."""

    allocation = {language: 0 for language in sizes}
    remaining = min(quota, sum(sizes.values()))
    languages = sorted(sizes)
    while remaining > 0:
        eligible = [
            language
            for language in languages
            if allocation[language] < sizes[language]
        ]
        if not eligible:
            break
        language = min(eligible, key=lambda item: (allocation[item], item))
        allocation[language] += 1
        remaining -= 1
    return allocation


def build_development_sample(
    frame: list[FrameRow],
    excluded_urls: set[str],
    allocation: dict[str, int],
    seed: int,
) -> tuple[list[FrameRow], dict[str, dict[str, Any]]]:
    """Return a deterministic, language-balanced sample outside prior evaluation."""

    eligible = [row for row in frame if row.url not in excluded_urls]
    grouped: dict[str, dict[str, list[FrameRow]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for row in eligible:
        grouped[row.pipeline_decision][row.route_lang or 'unknown'].append(row)

    sampled: list[FrameRow] = []
    bookkeeping: dict[str, dict[str, Any]] = {}
    for decision, quota in allocation.items():
        language_groups = grouped.get(decision, {})
        sizes = {
            language: len(rows) for language, rows in language_groups.items()
        }
        per_language = allocate_balanced_languages(sizes, quota)
        for language in sorted(language_groups):
            count = per_language.get(language, 0)
            stratum = f'{decision}|{language}'
            drawn = systematic_draw(
                language_groups[language],
                count,
                seed + int(stable_hash(decision, language)[:8], 16),
            )
            sampled.extend(drawn)
            bookkeeping[stratum] = {
                'pipeline_decision': decision,
                'route_lang': language,
                'eligible_population_n': sizes[language],
                'requested_n': count,
                'sampled_n': len(drawn),
            }
    sampled.sort(key=lambda row: row.url)
    return sampled, bookkeeping


def _label_records(rows: list[FrameRow], version: str) -> list[dict[str, Any]]:
    return [
        {
            'row_id': f'dev-{version}-{index:04d}',
            'url': row.url,
            'source': row.source,
            'year': row.year,
            'route_lang': row.route_lang,
            'title': row.title,
            'snippet': row.snippet,
        }
        for index, row in enumerate(rows, start=1)
    ]


def _prediction_records(rows: list[FrameRow], version: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        record = {
            'row_id': f'dev-{version}-{index:04d}',
            'url': row.url,
            'stratum': row.stratum,
            'pipeline_decision': row.pipeline_decision,
            'inclusion_weight': '',
        }
        record.update(row.predictions)
        records.append(record)
    return records


def run_development_set_stage(config: AppConfig) -> dict[str, Any]:
    """Generate a blind, non-evaluation labeling set for pipeline development."""

    settings = dict(config.raw.get('validation', {}).get('development_set', {}))
    version = str(settings.get('version', DEFAULT_VERSION))
    seed = int(settings.get('seed', DEFAULT_SEED))
    allocation = {
        str(key): int(value)
        for key, value in dict(
            settings.get('allocation', DEFAULT_ALLOCATION)
        ).items()
    }
    output_dir = config.resolve_path('outputs_dir')
    ensure_directory(output_dir)
    stem = f'development_set_{version}'
    labels_path = output_dir / f'{stem}_labels.csv'
    working_path = output_dir / f'{stem}_LABEL_HERE.csv'
    predictions_path = output_dir / f'{stem}_predictions.csv'
    manifest_path = output_dir / f'{stem}_manifest.json'
    if manifest_path.exists():
        LOGGER.warning(
            'Development set already exists at %s; refusing to redraw. '
            'Bump validation.development_set.version for a new set.',
            manifest_path,
        )
        return json.loads(manifest_path.read_text(encoding='utf-8'))

    excluded_urls, exclusion_audit = collect_prior_evaluation_urls(config)
    with connect_sqlite(config.sqlite_path) as connection:
        frame = load_frame(connection)
    sampled, strata = build_development_sample(
        frame,
        excluded_urls,
        allocation,
        seed,
    )
    label_rows = _label_records(sampled, version)
    prediction_rows = _prediction_records(sampled, version)
    write_csv(labels_path, LABEL_COLUMNS, label_rows)
    write_csv(working_path, LABEL_COLUMNS, label_rows)
    write_csv(predictions_path, PREDICTION_COLUMNS, prediction_rows)

    frame_urls = {row.url for row in frame}
    sampled_urls = {row.url for row in sampled}
    manifest = {
        'design': 'development_only_not_for_evaluation',
        'version': version,
        'created_at': iso_now(),
        'seed': seed,
        'allocation': allocation,
        'frame_size_after_assisted_exclusion': len(frame),
        'prior_evaluation_urls_found': len(excluded_urls),
        'prior_evaluation_urls_in_frame': len(excluded_urls & frame_urls),
        'eligible_frame_size': len(frame_urls - excluded_urls),
        'sample_size': len(sampled),
        'strata': strata,
        'exclusion_sources': exclusion_audit,
        'overlap_with_prior_evaluation': len(sampled_urls & excluded_urls),
        'url_lock_hash': stable_hash('development_set', version, sorted(sampled_urls)),
        'labels_file': labels_path.name,
        'working_labels_file': working_path.name,
        'predictions_file': predictions_path.name,
        'labels_sha256': _sha256(labels_path),
        'predictions_sha256': _sha256(predictions_path),
        'notes': (
            'For pipeline diagnosis and tuning only. Never report metrics from '
            'this sample as held-out performance. Truth and predictions remain '
            'in separate files.'
        ),
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8',
    )
    LOGGER.info(
        'Development set written: %d rows from %d eligible articles; '
        'excluded prior-evaluation overlap=%d',
        len(sampled),
        manifest['eligible_frame_size'],
        manifest['overlap_with_prior_evaluation'],
    )
    return manifest
