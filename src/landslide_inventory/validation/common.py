"""Shared helpers for validation-stage sampling and reporting."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
import json
from pathlib import Path
import random
from typing import Any, Iterable

from ..utils import ensure_directory, stable_hash


def stable_sample(items: list[Any], sample_size: int, seed: int, key: callable) -> list[Any]:
    """Return a deterministic sample using a stable hash order."""

    ordered = sorted(items, key=lambda item: (stable_hash(seed, key(item)), key(item)))
    return ordered[:sample_size]


def parse_json_list(raw_value: str | None) -> list[str]:
    """Parse a JSON list value, returning an empty list on bad input."""

    if not raw_value:
        return []
    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(value) for value in parsed]


def write_csv(path: Path, fieldnames: list[str], rows: Iterable[dict[str, Any]]) -> None:
    """Write a deterministic CSV file."""

    ensure_directory(path.parent)
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fieldnames})



def normalize_whitespace(value: str | None) -> str:
    """Collapse internal whitespace so CSV audit fields stay single-line."""

    if value is None:
        return ''
    return ' '.join(str(value).split())


def derive_year(*values: str | None) -> str:
    """Return the first usable year bucket from candidate date strings."""

    for value in values:
        if not value:
            continue
        text = str(value).strip()
        if len(text) >= 4 and text[:4].isdigit():
            return text[:4]
    return ''


def is_truth_filled(value: str | None) -> bool:
    """Return whether a reviewer truth cell is meaningfully filled."""

    return value is not None and str(value).strip() != ''


def iso_now() -> str:
    """Return a compact ISO timestamp for reports."""

    return datetime.now(UTC).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
