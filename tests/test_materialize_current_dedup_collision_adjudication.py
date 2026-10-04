"""Tests for collision adjudication and merge-override materialization."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load():
    path = ROOT / 'scripts' / 'materialize_current_dedup_collision_adjudication.py'
    spec = importlib.util.spec_from_file_location('materialize_collision_adjudication', path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_adjudication_resolves_unclear_and_parasi_survivor() -> None:
    module = load()
    rows = module.read_csv(module.SOURCE)
    result = module.adjudicate(rows)

    assert all(row['decision'] != 'unclear' for row in result)
    parasi = [
        row for row in result
        if row['group_id'] == 'collision_group_7b1b35543587ef1e'
    ]
    assert {row['merge_survivor_event_id'] for row in parasi} == {
        'event_9087fe127ac8789a'
    }


def test_materialized_components_use_representative_url_anchors() -> None:
    module = load()
    rows = module.adjudicate(module.read_csv(module.SOURCE))
    overrides = module.materialize_overrides(rows)

    assert len(overrides) < sum(row['decision'] == 'merge' for row in rows)
    assert all('member_anchor_urls_json' in row for row in overrides)
    parasi = [
        row for row in overrides
        if row['survivor_url'] == 'https://www.ujyaaloonline.com/detail/57742'
    ]
    assert len(parasi) == 1
    assert parasi[0]['survivor_url'] == 'https://www.ujyaaloonline.com/detail/57742'
