#!/usr/bin/env python3
"""Verify that reviewed collision decisions are materialized in the database."""

from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'data' / 'outputs'
DATABASE = ROOT / 'data' / 'raw_sqlite' / 'landslide_inventory.sqlite'
ADJUDICATED = OUTPUT / 'dedup_collision_review_BATCH_01_ADJUDICATED.csv'
VALIDATION = OUTPUT / 'dedup_collision_review_BATCH_01_validation.json'
OVERRIDES = ROOT / 'corrections' / 'dedup_merge_overrides.csv'
CORRECTIONS = ROOT / 'corrections' / 'article_corrections.csv'
REPORT = OUTPUT / 'dedup_collision_review_BATCH_01_application.json'


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))


def verify(connection: sqlite3.Connection, overrides: list[dict[str, str]]) -> dict[str, int | str]:
    applied = 0
    for row in overrides:
        cluster_ids: set[str] = set()
        for url in json.loads(row['member_anchor_urls_json']):
            matches = connection.execute(
                'SELECT dedup_cluster_id FROM article_events WHERE url = ?', (url,)
            ).fetchall()
            if len(matches) != 1 or not matches[0][0]:
                raise ValueError(
                    f"{row['merge_id']}: anchor {url!r} is missing or not canonical"
                )
            cluster_ids.add(str(matches[0][0]))
        if len(cluster_ids) != 1:
            raise ValueError(
                f"{row['merge_id']}: anchors span {len(cluster_ids)} final clusters"
            )
        applied += 1

    excluded_still_clustered = connection.execute(
        """
        SELECT COUNT(*)
        FROM reviewed_article_corrections AS correction
        JOIN article_events AS event ON event.url = correction.url
        WHERE correction.exclude_from_canonical = 1
          AND event.dedup_cluster_id IS NOT NULL
        """
    ).fetchone()[0]
    if excluded_still_clustered:
        raise ValueError(
            f'{excluded_still_clustered} reviewed exclusions remain canonical'
        )
    return {
        'status': 'applied_reviewed_collision_batch',
        'reviewed_merge_components': len(overrides),
        'applied_merge_components': applied,
        'excluded_articles_still_clustered': excluded_still_clustered,
    }


def main() -> None:
    validation = json.loads(VALIDATION.read_text(encoding='utf-8'))
    if validation['status'] != 'validated_collision_batch_not_yet_applied':
        raise ValueError('Collision decision validation is not ready for application')
    connection = sqlite3.connect(DATABASE)
    try:
        result = verify(connection, read_csv(OVERRIDES))
    finally:
        connection.close()
    result['inputs'] = {
        ADJUDICATED.name: sha256(ADJUDICATED),
        VALIDATION.name: sha256(VALIDATION),
        OVERRIDES.name: sha256(OVERRIDES),
        CORRECTIONS.name: sha256(CORRECTIONS),
        DATABASE.name: sha256(DATABASE),
    }
    REPORT.write_text(
        json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8'
    )
    print(f"Verified {result['applied_merge_components']} applied merge components")
    print(f'Wrote {REPORT}')


if __name__ == '__main__':
    main()
