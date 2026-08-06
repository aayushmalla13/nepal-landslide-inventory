"""CLI stage runner."""

from __future__ import annotations

import argparse
import logging
from typing import Callable

from .bipad import run_bipad_validation_stage
from .config import AppConfig, load_config
from .db import initialize_sqlite
from .langdetect import run_language_stage
from .validation import (
    run_audit_canonical_stage,
    run_inventory_audit_stage,
    run_locked_test_set_stage,
    run_manual_audit_stage,
    run_manual_pack_stage,
    run_manual_refresh_stage,
    run_manual_score_stage,
)
from .preprocess import normalize_dates_in_sqlite
from .unify.dedup_stage import run_dedup_stage
from .unify.extract_stage import run_extract_stage
from .unify.event_specificity import run_event_specificity_stage
from .unify.location_consistency import run_location_consistency_stage
from .unify.scope_filter import run_filter_scope_stage
from .scrape import run_collect_stage
from .utils import configure_logging, ensure_directory, stable_hash, utc_now_iso

LOGGER = logging.getLogger(__name__)

STAGE_ALIASES = {
    'scrape': 'collect',
    'bipad_validate': 'bipad',
    'validate_bipad': 'bipad',
}


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser."""

    parser = argparse.ArgumentParser(description='Run landslide inventory pipeline stages.')
    parser.add_argument('--stage', required=True, help='Pipeline stage to execute.')
    parser.add_argument('--config', required=True, help='Path to YAML config.')
    parser.add_argument('--verbose', action='store_true', help='Enable debug logging.')
    return parser


def stage_smoke(config: AppConfig) -> None:
    """Create working directories and initialize SQLite without scraping."""

    for directory in config.data_directories():
        ensure_directory(directory)

    database_path = config.sqlite_path
    initialize_sqlite(database_path)

    LOGGER.info('Smoke stage completed with database at %s', database_path)


def stage_normalize_dates(config: AppConfig) -> None:
    """Normalize published dates in raw_articles."""

    updated = normalize_dates_in_sqlite(config)
    LOGGER.info('Normalized %s raw article dates', updated)



def stage_lang(config: AppConfig) -> None:
    """Compute article language routing decisions."""

    routed = run_language_stage(config)
    LOGGER.info('Computed language routing for %s articles', routed)

def stage_all(config: AppConfig) -> None:
    """Placeholder for the full pipeline until later stages are implemented."""

    LOGGER.info('Running placeholder all-stage workflow via smoke stage.')
    stage_smoke(config)


def _not_implemented(config: AppConfig) -> None:
    """Placeholder stage handler for future work."""

    LOGGER.info('Stage scaffold exists but is not implemented yet. Config: %s', config.config_path)


STAGE_HANDLERS: dict[str, Callable[[AppConfig], None]] = {
    'smoke': stage_smoke,
    'collect': run_collect_stage,
    'preprocess': stage_normalize_dates,
    'normalize_dates': stage_normalize_dates,
    'lang': stage_lang,
    'extract': run_extract_stage,
    'event_specificity': run_event_specificity_stage,
    'location_consistency': run_location_consistency_stage,
    'filter_scope': run_filter_scope_stage,
    'unify': _not_implemented,
    'dedup': run_dedup_stage,
    'audit_canonical': run_audit_canonical_stage,
    'inventory_audit': run_inventory_audit_stage,
    'locked_test_set': run_locked_test_set_stage,
    'manual_pack': run_manual_pack_stage,
    'manual_score': run_manual_score_stage,
    'manual_refresh': run_manual_refresh_stage,
    'manual_audit': run_manual_audit_stage,
    'validate': _not_implemented,
    'bipad': run_bipad_validation_stage,
    'analysis': _not_implemented,
    'all': stage_all,
}


def resolve_stage_name(stage: str) -> str:
    """Resolve public stage aliases to internal stage names."""

    return STAGE_ALIASES.get(stage, stage)


def dispatch_stage(stage: str, config: AppConfig) -> None:
    """Dispatch a stage by name."""

    resolved_stage = resolve_stage_name(stage)
    try:
        handler = STAGE_HANDLERS[resolved_stage]
    except KeyError as exc:
        available = ', '.join(sorted(set(STAGE_HANDLERS) | set(STAGE_ALIASES)))
        raise ValueError(f"Unknown stage '{stage}'. Available stages: {available}.") from exc

    run_fingerprint = stable_hash(resolved_stage, str(config.config_path), utc_now_iso())
    LOGGER.debug('Dispatching stage %s with run fingerprint %s', resolved_stage, run_fingerprint)
    handler(config)


def main() -> None:
    """Run the requested pipeline stage."""

    parser = build_parser()
    args = parser.parse_args()
    configure_logging(verbose=args.verbose)
    config = load_config(args.config)
    dispatch_stage(args.stage, config)


if __name__ == '__main__':
    main()
