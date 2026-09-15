"""Build the manuscript-ready validation report and checksummed release bundle."""

from __future__ import annotations

import csv
import hashlib
import json
import logging
import shutil
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any

from ..config import AppConfig
from ..db import connect_sqlite
from ..utils import ensure_directory, stable_hash
from .common import iso_now, write_csv
from .locked_test_set import locked_set_settings, verify_locked_manifest

LOGGER = logging.getLogger(__name__)

METRIC_COLUMNS = [
    'measure', 'estimate', 'ci95_lower', 'ci95_upper', 'truth_available_n',
    'reportable', 'unit', 'notes',
]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validation_metric_rows(score: dict[str, Any]) -> list[dict[str, Any]]:
    """Return reportable locked-test metrics in a manuscript-table schema."""

    rows: list[dict[str, Any]] = []
    intervals = score['weighted_ci95_stratified_bootstrap']
    for measure in ('precision', 'recall', 'f1'):
        interval = intervals[measure]
        rows.append(
            {
                'measure': f'article_{measure}',
                'estimate': score['weighted'][measure],
                'ci95_lower': interval[0] if interval else '',
                'ci95_upper': interval[1] if interval else '',
                'truth_available_n': score['labelled_rows'],
                'reportable': 'yes',
                'unit': 'article-level headline classification',
                'notes': 'Population-weighted; within-stratum bootstrap CI',
            }
        )
    extraction = score['extraction_among_true_headline_articles']
    district = extraction['district']
    rows.extend(
        [
            {
                'measure': 'district_exact_accuracy',
                'estimate': district['weighted_exact_accuracy'],
                'ci95_lower': '',
                'ci95_upper': '',
                'truth_available_n': district['truth_available_n'],
                'reportable': 'yes' if district['reportable'] else 'no',
                'unit': 'true headline articles with district truth',
                'notes': 'Population-weighted exact match',
            },
            {
                'measure': 'district_coverage',
                'estimate': district['weighted_coverage'],
                'ci95_lower': '',
                'ci95_upper': '',
                'truth_available_n': district['truth_available_n'],
                'reportable': 'yes' if district['reportable'] else 'no',
                'unit': 'true headline articles with district truth',
                'notes': 'Population-weighted nonblank prediction coverage',
            },
        ]
    )
    event_date = extraction['event_date']
    date_reportable = bool(event_date['reportable'])
    date_notes = (
        'Population-weighted exact match'
        if date_reportable
        else f"Not reportable below minimum n={event_date['minimum_truth_rows']}"
    )
    rows.extend(
        [
            {
                'measure': 'event_date_exact_accuracy',
                'estimate': event_date['weighted_exact_accuracy'] if date_reportable else '',
                'ci95_lower': '',
                'ci95_upper': '',
                'truth_available_n': event_date['truth_available_n'],
                'reportable': 'yes' if date_reportable else 'no',
                'unit': 'true headline articles with event-date truth',
                'notes': date_notes,
            },
            {
                'measure': 'event_date_coverage',
                'estimate': event_date['weighted_coverage'] if date_reportable else '',
                'ci95_lower': '',
                'ci95_upper': '',
                'truth_available_n': event_date['truth_available_n'],
                'reportable': 'yes' if date_reportable else 'no',
                'unit': 'true headline articles with event-date truth',
                'notes': (
                    'Population-weighted nonblank prediction coverage'
                    if date_reportable
                    else date_notes
                ),
            },
        ]
    )
    return rows


def summarize_canonical(path: Path, cutoff: date) -> dict[str, Any]:
    """Validate and summarize the released canonical CSV."""

    with path.open(encoding='utf-8', newline='') as handle:
        rows = list(csv.DictReader(handle))
    event_ids = [row['event_id'] for row in rows]
    dates = [row['event_date_ad'] for row in rows if row.get('event_date_ad')]
    future = [row for row in rows if row.get('event_date_ad', '') > cutoff.isoformat()]
    if not rows or len(set(event_ids)) != len(rows):
        raise ValueError('Canonical release must contain unique, non-empty event IDs.')
    if future:
        raise ValueError(
            f'{len(future)} canonical rows occur after release cutoff {cutoff}; '
            f"first: {future[0]['event_id']}={future[0]['event_date_ad']}"
        )
    return {
        'rows': len(rows),
        'unique_event_ids': len(set(event_ids)),
        'date_min': min(dates),
        'date_max': max(dates),
        'districts': len({row['district'] for row in rows if row.get('district')}),
        'representative_sources': len(
            {
                row['representative_source']
                for row in rows
                if row.get('representative_source')
            }
        ),
        'road_obstruction': sum(
            row.get('event_type') == 'road_obstruction' for row in rows
        ),
        'non_single': sum(
            row.get('event_granularity') != 'single' for row in rows
        ),
        'sha256': _sha256(path),
    }


def _format_metric(value: float | None) -> str:
    return 'n/a' if value is None else f'{value:.3f}'


def build_validation_report(
    score: dict[str, Any],
    locked_manifest: dict[str, Any],
    canonical: dict[str, Any],
    corrections: dict[str, Any],
) -> str:
    """Render a concise publication-ready Markdown report."""

    weighted = score['weighted']
    intervals = score['weighted_ci95_stratified_bootstrap']
    district = score['extraction_among_true_headline_articles']['district']
    event_date = score['extraction_among_true_headline_articles']['event_date']
    if event_date['reportable']:
        event_date_summary = (
            f"Event-date exact accuracy was {event_date['weighted_exact_accuracy']:.3f}, "
            f"with coverage {event_date['weighted_coverage']:.3f}, among "
            f"{event_date['truth_available_n']} true headline articles with "
            'event-date truth.'
        )
    else:
        event_date_summary = (
            'Event-date accuracy is not reportable: only '
            f"{event_date['truth_available_n']} rows contained event-date truth, "
            f"below the prespecified minimum of {event_date['minimum_truth_rows']}."
        )
    locked_version = str(locked_manifest['design_version'])
    undecidable_count = int(score['undecidable_rows'])
    undecidable_verb = 'was' if undecidable_count == 1 else 'were'
    lines = [
        '# Final Validation and Release Summary',
        '',
        f"Generated: {iso_now()}",
        '',
        '## Held-out article classification',
        '',
        (
            f"Locked {locked_manifest['design_version']} sampled "
            f"{locked_manifest['sample_size']} articles from "
            f"{locked_manifest['eligible_frame_size']} eligible articles after "
            'prior-evaluation and assisted-discovery exclusions. '
            f"{score['labelled_rows']} rows were decidable and "
            f"{undecidable_count} {undecidable_verb} excluded as undecidable."
        ),
        '',
        '| Measure | Estimate | Stratified-bootstrap 95% CI |',
        '|---|---:|---:|',
    ]
    for measure in ('precision', 'recall', 'f1'):
        interval = intervals[measure]
        lines.append(
            f"| {measure.capitalize()} | {_format_metric(weighted[measure])} | "
            f"{interval[0]:.3f}–{interval[1]:.3f} |"
        )
    lines.extend(
        [
            '',
            'These are population-weighted article-level headline metrics. '
            'Unweighted sample metrics are diagnostic and are not reportable as '
            'inventory-wide performance.',
            '',
            '## Field extraction',
            '',
            (
                f"District exact accuracy was "
                f"{district['weighted_exact_accuracy']:.3f}, with coverage "
                f"{district['weighted_coverage']:.3f}, among "
                f"{district['truth_available_n']} true headline articles with "
                'district truth.'
            ),
            '',
            event_date_summary,
            '',
            '## Released canonical inventory',
            '',
            f"- Canonical events: {canonical['rows']}",
            f"- Date range: {canonical['date_min']} to {canonical['date_max']}",
            f"- Districts represented: {canonical['districts']}",
            f"- Representative news sources: {canonical['representative_sources']}",
            f"- Road-obstruction subtype: {canonical['road_obstruction']}",
            f"- Non-single records: {canonical['non_single']}",
            f"- Canonical CSV SHA-256: `{canonical['sha256']}`",
            '',
            '## Reviewed post-validation corrections',
            '',
            (
                f"A versioned correction layer containing {corrections['rows']} "
                f'records was applied after locked-{locked_version} scoring. It '
                'records reviewed date corrections or exclusions from canonical '
                'release construction with source evidence and before/after state.'
            ),
            '',
            (
                f'Locked {locked_version} therefore validates the pre-correction '
                'article classifier. '
                'The reviewed corrections are a transparent release-QA layer and were '
                'not used to recompute or improve the held-out score. '
                + (
                    'Event-date performance is reported because the prespecified '
                    'minimum truth count was met.'
                    if event_date['reportable']
                    else 'Event-date performance remains explicitly unreported.'
                )
            ),
            '',
            '## Limitations',
            '',
            '- The held-out design evaluates article-level detection, not deduplicated '
            'event-level precision or cluster completeness.',
            '- News availability and archive depth vary by source and year; temporal '
            'counts must not be interpreted as an unbiased landslide trend.',
            '- The final article-level precision estimate implies that residual false '
            'positives remain in the automated inventory.',
            '- Any future classifier change requires a new locked test version.',
            '',
        ]
    )
    return '\n'.join(lines)


def _write_canonical_database(source_csv: Path, target_path: Path) -> int:
    """Create a compact SQLite snapshot whose sole data source is the final CSV.

    The working database continues to evolve and may contain a different dedup
    snapshot. Copying it into a release falsely implies that its canonical table
    generated the released CSV. This delivery database is deliberately narrow
    and mechanically identical to the CSV.
    """

    ensure_directory(target_path.parent)
    if target_path.exists():
        target_path.unlink()
    with source_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    if not fieldnames or "event_id" not in fieldnames:
        raise ValueError("Canonical CSV has no event_id column")
    definitions = [
        f'"{name}" TEXT' + (" PRIMARY KEY" if name == "event_id" else "")
        for name in fieldnames
    ]
    placeholders = ", ".join("?" for _ in fieldnames)
    columns = ", ".join(f'"{name}"' for name in fieldnames)
    with sqlite3.connect(target_path) as connection:
        connection.execute(f"CREATE TABLE canonical_events ({', '.join(definitions)})")
        connection.executemany(
            f"INSERT INTO canonical_events ({columns}) VALUES ({placeholders})",
            [[row.get(name, "") for name in fieldnames] for row in rows],
        )
        connection.execute(
            "CREATE TABLE release_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        connection.executemany(
            "INSERT INTO release_metadata (key, value) VALUES (?, ?)",
            [("canonical_csv_sha256", _sha256(source_csv)), ("canonical_rows", str(len(rows)))],
        )
        connection.commit()
    return len(rows)


def run_final_report_stage(config: AppConfig) -> dict[str, Any]:
    """Verify frozen artifacts and create the final checksummed release bundle."""

    outputs = config.resolve_path('outputs_dir')
    settings = locked_set_settings(config)
    stem = settings.stem
    reference = outputs / f'{stem}_labels.csv'
    final_labels = outputs / f'{stem}_labels_final.csv'
    predictions = outputs / f'{stem}_predictions.csv'
    locked_manifest_path = outputs / f'{stem}_manifest.json'
    score_path = outputs / f'{stem}_score.json'
    canonical_path = outputs / 'canonical_events_final.csv'
    corrections_report = outputs / 'reviewed_corrections_applied.csv'
    correction_source_value = config.raw.get('validation', {}).get(
        'article_corrections_path'
    )
    if not correction_source_value:
        raise ValueError('validation.article_corrections_path is required for release.')
    correction_source = Path(str(correction_source_value))
    if not correction_source.is_absolute():
        correction_source = config.config_path.parent / correction_source

    required = (
        reference, final_labels, predictions, locked_manifest_path, score_path,
        canonical_path, corrections_report, correction_source,
        outputs / 'inventory_audit_summary.json',
        outputs / 'inventory_audit_report.md',
    )
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError('Missing release artifacts: ' + ', '.join(missing))

    locked_manifest = json.loads(locked_manifest_path.read_text(encoding='utf-8'))
    score = json.loads(score_path.read_text(encoding='utf-8'))
    if not verify_locked_manifest(locked_manifest_path, reference):
        raise ValueError('Locked reference no longer matches its URL lock hash.')
    if _sha256(final_labels) != score['labels_sha256']:
        raise ValueError('Frozen labels no longer match the scored label hash.')
    if _sha256(predictions) != score['predictions_sha256']:
        raise ValueError('Predictions no longer match the scored prediction hash.')

    release_date_text = str(
        config.raw.get('validation', {}).get('final_release_date', date.today().isoformat())
    )
    release_cutoff = date.fromisoformat(release_date_text)
    canonical = summarize_canonical(canonical_path, release_cutoff)
    with connect_sqlite(config.sqlite_path) as connection:
        correction_count = int(
            connection.execute(
                'SELECT COUNT(*) FROM reviewed_article_corrections'
            ).fetchone()[0]
        )
        correction_hashes = {
            row[0]
            for row in connection.execute(
                'SELECT DISTINCT corrections_sha256 FROM reviewed_article_corrections'
            )
        }
    correction_hash = _sha256(correction_source)
    if correction_hashes != {correction_hash}:
        raise ValueError('Applied correction provenance does not match the source CSV.')
    corrections = {'rows': correction_count, 'sha256': correction_hash}

    metrics_path = outputs / f'{stem}_manuscript_metrics.csv'
    report_path = outputs / f'{stem}_validation_report.md'
    write_csv(metrics_path, METRIC_COLUMNS, validation_metric_rows(score))
    report_path.write_text(
        build_validation_report(score, locked_manifest, canonical, corrections),
        encoding='utf-8',
    )

    paper_version = str(config.raw.get('paper_metadata', {}).get('version', 'unknown'))
    release_id = (
        f'nepal_landslide_inventory_v{paper_version}_{settings.version}_'
        f'{release_date_text.replace("-", "")}'
    )
    release_dir = config.config_path.parent / 'data' / 'releases' / release_id
    ensure_directory(release_dir)
    database_snapshot = release_dir / 'canonical_inventory.sqlite'
    snapshot_rows = _write_canonical_database(canonical_path, database_snapshot)
    if snapshot_rows != canonical['rows']:
        raise ValueError("Canonical SQLite snapshot row count does not match the CSV")

    artifacts = [
        canonical_path,
        locked_manifest_path,
        final_labels,
        predictions,
        score_path,
        correction_source,
        corrections_report,
        outputs / 'inventory_audit_summary.json',
        outputs / 'inventory_audit_report.md',
        metrics_path,
        report_path,
    ]
    bundle_files: list[dict[str, Any]] = []
    for source in artifacts:
        target = release_dir / source.name
        shutil.copyfile(source, target)
        bundle_files.append(
            {'file': target.name, 'sha256': _sha256(target), 'bytes': target.stat().st_size}
        )
    bundle_files.append(
        {
            'file': database_snapshot.name,
            'sha256': _sha256(database_snapshot),
            'bytes': database_snapshot.stat().st_size,
        }
    )
    bundle_files.sort(key=lambda item: item['file'])
    release_manifest = {
        'release_id': release_id,
        'generated_at': iso_now(),
        'status': 'final_with_reviewed_post_validation_corrections',
        'locked_evaluation_version': settings.version,
        'release_cutoff': release_date_text,
        'canonical_summary': canonical,
        'reportable_metrics': {
            key: score['weighted'][key] for key in ('precision', 'recall', 'f1')
        },
        'corrections': corrections,
        'supersedes': config.raw.get('validation', {}).get('supersedes_release'),
        'checks': {
            'locked_url_hash_valid': True,
            'frozen_labels_hash_valid': True,
            'frozen_predictions_hash_valid': True,
            'canonical_unique_event_ids': True,
            'canonical_rows_after_release_cutoff': 0,
            'canonical_sqlite_rows_match_csv': True,
        },
        'files': bundle_files,
        'bundle_lock_hash': stable_hash(
            'release_bundle', release_id,
            [(item['file'], item['sha256']) for item in bundle_files],
        ),
        'notes': (
            'The included canonical_inventory.sqlite is generated directly from '
            'canonical_events_final.csv; it is not a copy of the mutable working database. '
            f'Locked {settings.version} metrics describe the pre-correction article '
            f'classifier. The {correction_count}-row reviewed correction layer is '
            f'release QA and does not alter or rescore frozen {settings.version} '
            'evaluation artifacts.'
        ),
    }
    release_manifest_path = release_dir / 'release_manifest.json'
    release_manifest_path.write_text(
        json.dumps(release_manifest, ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8',
    )
    LOGGER.info(
        'Final release bundle written to %s (%d canonical events; lock %s)',
        release_dir, canonical['rows'], release_manifest['bundle_lock_hash'][:12],
    )
    return release_manifest
