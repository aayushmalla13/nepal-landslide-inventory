"""Discover URLs that must not enter a new evaluation or development sample."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from ..config import AppConfig

TRUTH_MARKERS = {
    'is_landslide_event_true',
    'class_true',
    'district_true',
    'municipality_true',
    'date_true',
    'deaths_true',
    'trigger_true',
    'annotator',
}


def _url_field(fieldnames: list[str] | None) -> str | None:
    fields = set(fieldnames or [])
    for candidate in ('url', 'article_url'):
        if candidate in fields:
            return candidate
    return None


def _read_urls(path: Path, *, labelled_only: bool) -> tuple[set[str], int]:
    """Read URL exclusions from one CSV and return URLs plus rows inspected."""

    urls: set[str] = set()
    with path.open(encoding='utf-8-sig', newline='', errors='replace') as handle:
        reader = csv.DictReader(handle)
        url_field = _url_field(reader.fieldnames)
        if url_field is None:
            return urls, 0
        marker_fields = TRUTH_MARKERS & set(reader.fieldnames or [])
        rows_seen = 0
        for row in reader:
            rows_seen += 1
            if labelled_only and not any(
                (row.get(field) or '').strip() for field in marker_fields
            ):
                continue
            url = (row.get(url_field) or '').strip()
            if url:
                urls.add(url)
    return urls, rows_seen


def collect_prior_evaluation_urls(
    config: AppConfig,
) -> tuple[set[str], list[dict[str, Any]]]:
    """Collect prior locked, development, and labelled manual URLs with provenance."""

    project_root = config.config_path.parent
    output_dir = config.resolve_path('outputs_dir')
    specs: list[tuple[str, list[Path], bool]] = [
        (
            'locked_test',
            [
                *output_dir.glob('locked_test_set_v*_labels*.csv'),
                *output_dir.glob('locked_test_set_v*_LABEL_HERE.csv'),
                *(project_root / 'docs').glob('locked_test_set_v*_labels*.csv'),
            ],
            False,
        ),
        (
            'prior_development',
            [
                *output_dir.glob('development_set_v*_labels*.csv'),
                *output_dir.glob('development_set_v*_LABEL_HERE.csv'),
            ],
            False,
        ),
        (
            'labelled_manual_evaluation',
            list(output_dir.glob('manual_verification*.csv')),
            True,
        ),
    ]
    excluded: set[str] = set()
    audit: list[dict[str, Any]] = []
    seen_paths: set[Path] = set()
    for category, paths, labelled_only in specs:
        for path in sorted(paths):
            resolved = path.resolve()
            if resolved in seen_paths or not path.is_file():
                continue
            seen_paths.add(resolved)
            urls, rows_seen = _read_urls(path, labelled_only=labelled_only)
            before = len(excluded)
            excluded.update(urls)
            try:
                display_path = str(path.relative_to(project_root))
            except ValueError:
                display_path = str(path)
            audit.append(
                {
                    'category': category,
                    'path': display_path,
                    'rows_seen': rows_seen,
                    'urls_in_file': len(urls),
                    'new_unique_exclusions': len(excluded) - before,
                }
            )
    return excluded, audit
