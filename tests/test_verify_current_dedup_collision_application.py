"""Tests for final reviewed-collision application verification."""

from __future__ import annotations

import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def load():
    path = ROOT / 'scripts' / 'verify_current_dedup_collision_application.py'
    spec = importlib.util.spec_from_file_location('verify_collision_application', path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def database() -> sqlite3.Connection:
    connection = sqlite3.connect(':memory:')
    connection.execute('CREATE TABLE article_events (url TEXT, dedup_cluster_id TEXT)')
    connection.execute(
        'CREATE TABLE reviewed_article_corrections '
        '(url TEXT, exclude_from_canonical INTEGER)'
    )
    connection.executemany(
        'INSERT INTO article_events VALUES (?, ?)',
        [('https://a.test', 'cluster-1'), ('https://b.test', 'cluster-1')],
    )
    return connection


def override() -> dict[str, str]:
    return {
        'merge_id': 'merge-1',
        'member_anchor_urls_json': json.dumps(['https://a.test', 'https://b.test']),
    }


def test_verifier_accepts_one_final_cluster() -> None:
    module = load()
    result = module.verify(database(), [override()])
    assert result['status'] == 'applied_reviewed_collision_batch'
    assert result['applied_merge_components'] == 1


def test_verifier_rejects_split_final_clusters() -> None:
    module = load()
    connection = database()
    connection.execute(
        "UPDATE article_events SET dedup_cluster_id='cluster-2' WHERE url='https://b.test'"
    )
    with pytest.raises(ValueError, match='anchors span'):
        module.verify(connection, [override()])
