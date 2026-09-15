"""Smoke test harness for quick post-stage verification."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from typing import Sequence

from landslide_inventory.config import AppConfig, load_config
from landslide_inventory.run import STAGE_HANDLERS

REPO_ROOT = Path(__file__).resolve().parents[1]
STAGE_ALIASES = {
    'scrape': 'collect',
    'collect': 'collect',
    'normalize_dates': 'preprocess',
    'preprocess': 'preprocess',
    'lang': 'lang',
    'unify': 'unify',
    'extract': 'extract',
    'event_specificity': 'event_specificity',
    'location_consistency': 'location_consistency',
    'filter_scope': 'filter_scope',
    'dedup': 'dedup',
    'inventory_audit': 'inventory_audit',
    'audit_canonical': 'audit_canonical',
    'manual_pack': 'manual_pack',
    'manual_score': 'manual_score',
}
DEV_OVERRIDES = {
    'LS_MAX_URLS_PER_SOURCE': '20',
    'LS_MAX_PAGES_PER_ENTRY': '1',
    'LS_RATE_LIMIT_SECONDS': '0',
}
NETWORK_ERROR_MARKERS = (
    'Temporary failure in name resolution',
    'Name or service not known',
    'nodename nor servname provided',
    'Failed to fetch',
)


class SmokeFailure(RuntimeError):
    """Raised when a smoke step fails."""


class SmokeSkip(RuntimeError):
    """Raised when a smoke stage is intentionally skipped."""


def resolve_stage_name(stage_name: str) -> str:
    """Resolve smoke aliases to the pipeline stage names."""

    return STAGE_ALIASES.get(stage_name, stage_name)


def is_stage_implemented(stage_name: str) -> bool:
    """Return whether the resolved stage has a real handler."""

    resolved = resolve_stage_name(stage_name)
    handler = STAGE_HANDLERS.get(resolved)
    return handler is not None and handler.__name__ != '_not_implemented'


def build_stage_env() -> dict[str, str]:
    """Return environment overrides for dev-limited stage smoke runs."""

    env = dict(os.environ)
    env.update(DEV_OVERRIDES)
    env['PYTHONPATH'] = 'src'
    return env


def run_command(command: Sequence[str], env: dict[str, str] | None = None) -> tuple[int, str, str]:
    """Run a subprocess and capture output."""

    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode, result.stdout, result.stderr


def run_basic_smoke(config_path: Path) -> list[tuple[str, bool, str]]:
    """Run the basic smoke suite."""

    steps = [
        (
            'doctor',
            [sys.executable, '-m', 'landslide_inventory.doctor', '--config', str(config_path), '--minimal'],
        ),
        ('pytest', [sys.executable, '-m', 'pytest', '-q']),
        ('shadow_guard', [sys.executable, 'scripts/check_shadowing.py']),
    ]
    results: list[tuple[str, bool, str]] = []
    env = dict(os.environ)
    env['PYTHONPATH'] = 'src'
    for name, command in steps:
        returncode, stdout, stderr = run_command(command, env=env)
        ok = returncode == 0
        detail = (stdout + stderr).strip() or f'{name} completed'
        results.append((name, ok, detail))
    return results


def run_stage_smoke(config: AppConfig, stage_name: str) -> str:
    """Run a single stage with dev-limit overrides and verify outputs."""

    resolved = resolve_stage_name(stage_name)
    if resolved not in STAGE_HANDLERS:
        raise SmokeSkip(f'SKIP unknown stage: {stage_name}')
    if not is_stage_implemented(stage_name):
        raise SmokeSkip(f'SKIP stage not implemented: {stage_name}')
    if stage_requires_external_inputs(resolved, config):
        raise SmokeSkip(f'SKIP external inputs missing for stage: {stage_name}')

    env = build_stage_env()
    returncode, stdout, stderr = run_command(
        [sys.executable, '-m', 'landslide_inventory.run', '--stage', resolved, '--config', str(config.config_path)],
        env=env,
    )
    detail = (stdout + stderr).strip() or f'{stage_name} completed'
    if returncode != 0:
        if resolved == 'collect' and any(marker in detail for marker in NETWORK_ERROR_MARKERS):
            raise SmokeSkip(f'SKIP network unavailable for stage: {stage_name}')
        raise SmokeFailure(detail)
    verify_stage_outputs(config, stage_name)
    return detail


def verify_stage_outputs(config: AppConfig, stage_name: str) -> None:
    """Verify expected outputs for a smoke stage."""

    resolved = resolve_stage_name(stage_name)
    database_path = config.sqlite_path
    output_dir = config.resolve_path('outputs_dir')

    if resolved == 'collect':
        coverage_path = output_dir / 'coverage_report.csv'
        raw_count = table_row_count(database_path, 'raw_articles')
        if raw_count >= 1:
            return
        if coverage_path.exists() and coverage_path.stat().st_size > 0:
            return
        raise SmokeFailure('collect smoke expected raw_articles rows or coverage_report.csv')

    if resolved == 'preprocess':
        raw_count = table_row_count(database_path, 'raw_articles')
        if raw_count <= 0:
            raise SmokeSkip('SKIP normalize_dates requires raw_articles rows from scrape stage')
        if non_null_count(database_path, 'raw_articles', 'published_date_raw') <= 0:
            raise SmokeSkip('SKIP normalize_dates requires raw_articles.published_date_raw values')
        if non_null_count(database_path, 'raw_articles', 'published_date_ad') <= 0:
            raise SmokeFailure('normalize_dates smoke expected non-null raw_articles.published_date_ad values')
        return

    if resolved == 'lang':
        if table_row_count(database_path, 'raw_articles') <= 0:
            raise SmokeSkip('SKIP lang requires prerequisite raw_articles rows')
        if table_row_count(database_path, 'article_lang') <= 0:
            raise SmokeFailure('lang smoke expected article_lang rows')
        return

    if resolved == 'extract':
        extracted_path = output_dir / 'article_events.csv'
        if table_row_count(database_path, 'raw_articles') <= 0 and not extracted_path.exists():
            raise SmokeSkip('SKIP extract requires prerequisite scraped articles')
        if table_row_count(database_path, 'article_events') <= 0 and not file_has_data_rows(extracted_path):
            raise SmokeFailure('extract smoke expected article_events rows or outputs/article_events.csv with rows')
        return

    if resolved == 'filter_scope':
        if table_row_count(database_path, 'article_events') <= 0:
            raise SmokeSkip('SKIP filter_scope requires extracted article_events rows')
        if table_row_count(database_path, 'article_scope') <= 0:
            raise SmokeFailure('filter_scope smoke expected article_scope rows')
        return

    if resolved == 'dedup':
        if table_row_count(database_path, 'article_events') <= 0:
            raise SmokeSkip('SKIP dedup requires prerequisite extracted events')
        if table_row_count(database_path, 'canonical_events') <= 0:
            raise SmokeFailure('dedup smoke expected canonical_events rows')
        if table_row_count(database_path, 'cluster_summary') <= 0:
            raise SmokeFailure('dedup smoke expected cluster_summary rows')
        return

    if resolved == 'inventory_audit':
        report_path = output_dir / 'inventory_audit_report.md'
        summary_path = output_dir / 'inventory_audit_summary.json'
        if table_row_count(database_path, 'article_events') <= 0:
            raise SmokeSkip('SKIP inventory_audit requires article_events rows')
        if not report_path.exists() or report_path.stat().st_size == 0:
            raise SmokeFailure('inventory_audit smoke expected outputs/inventory_audit_report.md')
        if not summary_path.exists() or summary_path.stat().st_size == 0:
            raise SmokeFailure('inventory_audit smoke expected outputs/inventory_audit_summary.json')
        return

    if resolved == 'audit_canonical':
        audit_path = output_dir / 'canonical_audit_sample.csv'
        canonical_count = table_row_count(database_path, 'canonical_events')
        if canonical_count <= 0:
            raise SmokeSkip('SKIP audit_canonical requires canonical_events rows')
        row_count = csv_data_row_count(audit_path)
        expected_rows = min(30, canonical_count)
        if row_count != expected_rows:
            raise SmokeFailure(
                'audit_canonical smoke expected '
                f'{expected_rows} data rows in outputs/canonical_audit_sample.csv'
            )
        return

    if resolved == 'manual_pack':
        pack_path = output_dir / 'manual_verification_sample.csv'
        if table_row_count(database_path, 'article_events') <= 0:
            raise SmokeSkip('SKIP manual_pack requires extracted article_events rows')
        row_count = csv_data_row_count(pack_path)
        if row_count != 150:
            raise SmokeFailure('manual_pack smoke expected 150 data rows in outputs/manual_verification_sample.csv')
        return

    if resolved == 'manual_score':
        metrics_path = output_dir / 'manual_metrics.json'
        report_path = output_dir / 'manual_report.md'
        if not metrics_path.exists() or metrics_path.stat().st_size == 0:
            raise SmokeSkip('SKIP manual_score requires a labeled manual_verification_sample.csv')
        if not report_path.exists() or report_path.stat().st_size == 0:
            raise SmokeFailure('manual_score smoke expected outputs/manual_report.md')
        return

    raise SmokeSkip(f'SKIP no smoke verifier registered for stage: {stage_name}')


def stage_requires_external_inputs(stage_name: str, config: AppConfig) -> bool:
    """Return whether required external inputs for a stage are missing."""

    requirements = {
        'analysis': [
            _resolve_external_path(config, config.raw['analysis']['chirps_daily_district_path'])
        ],
        'bipad': [_resolve_external_path(config, config.raw['bipad']['bipad_input_path'])],
    }
    required_paths = requirements.get(stage_name, [])
    return any(not path.exists() for path in required_paths)


def table_row_count(database_path: Path, table_name: str) -> int:
    """Return a table row count, or zero if the table does not exist."""

    if not database_path.exists():
        return 0
    with sqlite3.connect(database_path) as connection:
        exists = connection.execute(
            'SELECT 1 FROM sqlite_master WHERE type = \'table\' AND name = ?',
            (table_name,),
        ).fetchone()
        if exists is None:
            return 0
        row = connection.execute(f'SELECT COUNT(*) FROM {table_name}').fetchone()
    return int(row[0])


def non_null_count(database_path: Path, table_name: str, column_name: str) -> int:
    """Return a non-null column count, or zero if unavailable."""

    if not database_path.exists():
        return 0
    with sqlite3.connect(database_path) as connection:
        exists = connection.execute(
            'SELECT 1 FROM sqlite_master WHERE type = \'table\' AND name = ?',
            (table_name,),
        ).fetchone()
        if exists is None:
            return 0
        row = connection.execute(
            f'SELECT COUNT(*) FROM {table_name} WHERE {column_name} IS NOT NULL'
        ).fetchone()
    return int(row[0])


def csv_data_row_count(path: Path) -> int:
    """Return the number of data rows in a CSV-like file."""

    if not path.exists() or path.stat().st_size == 0:
        return 0
    lines = [line for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
    return max(0, len(lines) - 1)


def file_has_data_rows(path: Path) -> bool:
    """Return whether a CSV-like file exists and contains at least one data row."""

    if not path.exists() or path.stat().st_size == 0:
        return False
    lines = [line for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
    return len(lines) >= 2


def _resolve_external_path(config: AppConfig, value: str) -> Path:
    """Resolve external paths relative to the config file when needed."""

    path = Path(str(value))
    if path.is_absolute():
        return path
    return (config.config_path.parent / path).resolve()


def build_parser() -> argparse.ArgumentParser:
    """Create the smoke CLI parser."""

    parser = argparse.ArgumentParser(description='Run smoke checks for the pipeline.')
    parser.add_argument('--config', required=True, help='Path to config YAML.')
    parser.add_argument('--level', required=True, choices=['basic', 'stage'])
    parser.add_argument('--stage', help='Stage name for stage-level smoke checks.')
    return parser


def main() -> None:
    """Run the requested smoke level."""

    args = build_parser().parse_args()
    config_path = Path(args.config).resolve()

    if args.level == 'basic':
        results = run_basic_smoke(config_path)
        failures = [result for result in results if not result[1]]
        for name, ok, detail in results:
            status = 'PASS' if ok else 'FAIL'
            print(f'[{status}] {name}')
            print(detail)
        if failures:
            raise SystemExit(1)
        print('[PASS] basic smoke summary')
        return

    if not args.stage:
        raise SystemExit('--stage is required when --level stage')

    config = load_config(config_path)
    try:
        detail = run_stage_smoke(config, args.stage)
    except SmokeSkip as exc:
        print(str(exc))
        raise SystemExit(0)
    except SmokeFailure as exc:
        print(f'[FAIL] {args.stage}')
        print(str(exc))
        raise SystemExit(1)

    print(f'[PASS] {args.stage}')
    print(detail)


if __name__ == '__main__':
    main()
