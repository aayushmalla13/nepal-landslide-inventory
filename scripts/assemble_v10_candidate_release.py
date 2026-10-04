#!/usr/bin/env python3
"""Freeze the reviewed 2,605-event working inventory as a v1.0 candidate."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_RELEASE_ID = 'nepal_landslide_inventory_v1.0.0_candidate_20260927'
SUPERSEDES = 'nepal_landslide_inventory_v0.9.0_candidate_20260924'
EXPECTED_ROWS = 2605
EXPECTED_CANONICAL_SHA256 = '68f2efd27a2c929c0df879974afcde14560ecbd6edf2ce389cc03a18f0857c8a'
EXPECTED_DATABASE_SHA256 = 'aed9e133ee511382f19ea7304168c3a3d7d2e59efb54cdcbc5047ec2117a198d'


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))


def inventory_lock(release_id: str, files: list[dict[str, object]]) -> str:
    payload = json.dumps(
        ['release_bundle', release_id, [[item['file'], item['sha256']] for item in files]],
        ensure_ascii=False,
        sort_keys=True,
        separators=(',', ':'),
    )
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def verify_csv_database(canonical: Path, database: Path) -> dict[str, object]:
    rows = read_csv(canonical)
    if len(rows) != EXPECTED_ROWS:
        raise ValueError(f'Expected {EXPECTED_ROWS} canonical rows, found {len(rows)}')
    event_ids = [row['event_id'] for row in rows]
    if len(event_ids) != len(set(event_ids)):
        raise ValueError('Canonical CSV contains duplicate event IDs')
    with sqlite3.connect(database) as connection:
        integrity = connection.execute('PRAGMA integrity_check').fetchone()[0]
        database_rows = {
            row[0]: (row[1] or '', row[2] or '', row[3] or '')
            for row in connection.execute(
                'SELECT event_id, event_date_ad, district, municipality FROM canonical_events'
            )
        }
    if integrity != 'ok':
        raise ValueError(f'SQLite integrity check failed: {integrity}')
    csv_rows = {
        row['event_id']: (
            row['event_date_ad'], row['district'], row.get('municipality', '') or ''
        )
        for row in rows
    }
    if csv_rows != database_rows:
        raise ValueError('Canonical CSV and SQLite canonical rows differ')
    dates = [row['event_date_ad'] for row in rows]
    return {
        'rows': len(rows),
        'unique_event_ids': len(set(event_ids)),
        'date_min': min(dates),
        'date_max': max(dates),
        'districts': len({row['district'] for row in rows}),
        'sha256': sha256(canonical),
    }


def build_release(
    root: Path,
    release_id: str,
    output_dir: Path,
    *,
    force: bool = False,
) -> Path:
    sources = {
        'canonical_events_final.csv': root / 'data/outputs/canonical_events_final.csv',
        'landslide_inventory.sqlite': (
            root / 'data/snapshots/landslide_inventory_post_collision_adjudication_20260927.sqlite'
        ),
        'article_corrections.csv': root / 'corrections/article_corrections.csv',
        'dedup_merge_overrides.csv': root / 'corrections/dedup_merge_overrides.csv',
        'dedup_collision_review_BATCH_01_ADJUDICATED.csv': (
            root / 'data/outputs/dedup_collision_review_BATCH_01_ADJUDICATED.csv'
        ),
        'dedup_collision_review_BATCH_01_application.json': (
            root / 'data/outputs/dedup_collision_review_BATCH_01_application.json'
        ),
    }
    missing = [str(path) for path in sources.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(f'Missing release inputs: {missing}')
    canonical = sources['canonical_events_final.csv']
    database = sources['landslide_inventory.sqlite']
    if sha256(canonical) != EXPECTED_CANONICAL_SHA256:
        raise ValueError('Canonical CSV differs from the reviewed 2,605-event state')
    if sha256(database) != EXPECTED_DATABASE_SHA256:
        raise ValueError('SQLite snapshot differs from the reviewed post-pass state')
    summary = verify_csv_database(canonical, database)

    if output_dir.exists():
        if not force:
            raise FileExistsError(f'Release directory already exists: {output_dir}')
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    bundled: list[Path] = []
    for name, source in sources.items():
        target = output_dir / name
        shutil.copy2(source, target)
        bundled.append(target)
    readme = output_dir / 'CANDIDATE_README.md'
    readme.write_text(
        '\n'.join([
            '# Nepal landslide inventory v1.0 candidate', '',
            f'Release: `{release_id}`', f'Rows: {EXPECTED_ROWS:,}',
            'Status: pending fresh independent validation.', '',
            'This candidate freezes the current parser/dedup pipeline after the first',
            'reviewed collision-adjudication pass. Earlier validation metrics do not',
            'validate this candidate.', '',
        ]),
        encoding='utf-8',
    )
    bundled.append(readme)
    files = [
        {'file': path.name, 'sha256': sha256(path), 'bytes': path.stat().st_size}
        for path in bundled
    ]
    application = json.loads(
        sources['dedup_collision_review_BATCH_01_application.json'].read_text(
            encoding='utf-8'
        )
    )
    manifest = {
        'release_id': release_id,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'status': 'pending_fresh_validation',
        'supersedes': SUPERSEDES,
        'canonical_summary': summary,
        'correction_summary': {
            'reviewed_article_corrections': len(read_csv(sources['article_corrections.csv'])),
            'reviewed_merge_components': len(read_csv(sources['dedup_merge_overrides.csv'])),
            'collision_application_status': application['status'],
        },
        'inputs': {
            str(path.relative_to(root)): sha256(path) for path in sources.values()
        } | {
            'scripts/assemble_v10_candidate_release.py': sha256(Path(__file__))
        },
        'checks': {
            'expected_2605_rows': summary['rows'] == EXPECTED_ROWS,
            'unique_event_ids': summary['unique_event_ids'] == EXPECTED_ROWS,
            'csv_sqlite_content_equal': True,
            'sqlite_integrity_ok': True,
            'reviewed_collision_application_complete': (
                application['status'] == 'applied_reviewed_collision_batch'
            ),
            'fresh_locked_validation_complete': False,
        },
        'files': files,
        'bundle_lock_hash': inventory_lock(release_id, files),
        'notes': (
            'Frozen from the corrected mutable pipeline after dedup collision '
            'adjudication pass 1. No earlier accuracy metric transfers to this candidate.'
        ),
    }
    if not all(
        value for key, value in manifest['checks'].items()
        if key != 'fresh_locked_validation_complete'
    ):
        raise ValueError(f'Release checks failed: {manifest["checks"]}')
    (output_dir / 'release_manifest.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + '\n',
        encoding='utf-8',
    )
    return output_dir


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default='.')
    parser.add_argument('--release-id', default=DEFAULT_RELEASE_ID)
    parser.add_argument('--output-dir')
    parser.add_argument('--force', action='store_true')
    args = parser.parse_args()
    root = Path(args.root).resolve()
    output = (
        Path(args.output_dir).resolve()
        if args.output_dir
        else root / 'data/releases' / args.release_id
    )
    release = build_release(root, args.release_id, output, force=args.force)
    print(f'Wrote v1.0 candidate release to {release}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
