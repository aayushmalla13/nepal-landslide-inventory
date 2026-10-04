#!/usr/bin/env python3
"""Resolve the reviewed collision batch and materialize persistent merge overrides."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'data' / 'outputs'
SOURCE = OUTPUT / 'dedup_collision_review_BATCH_01_COMPLETED.csv'
ADJUDICATED = OUTPUT / 'dedup_collision_review_BATCH_01_ADJUDICATED.csv'
OVERRIDES = ROOT / 'corrections' / 'dedup_merge_overrides.csv'
REVIEWED_AT = '2026-09-26'

DECISIONS = {
    'collision_pair_f65c953088a16c09': (
        'merge', 'event_d84b285798d43528',
        'The unrelated Kushma-11 article is corrected to Parbat; the remaining '
        'Ringlang/Bungadobhan fatality reports describe the same failure.',
    ),
    'collision_pair_4822e7b866928e46': (
        'keep_distinct', '',
        'The Republica pages have no recoverable incident body or place, so the '
        'Hagam/Yanglakot identity cannot be established at high precision.',
    ),
    'collision_pair_681a97ace6949e1b': (
        'keep_distinct', '',
        'All three source articles combine two road failures and are excluded '
        'from canonical output until location-specific decomposition is supported.',
    ),
    'collision_pair_324551a2d8c99cae': (
        'keep_distinct', '',
        'All source articles describe future risk sites rather than an observed '
        'dated landslide and are excluded from canonical output.',
    ),
    'collision_pair_1b64a52b78de2dee': (
        'merge', 'event_c543a264b3154a7f',
        'The later 28-household update explicitly contains the same seven Lower '
        'Tenchong households reported earlier, establishing continuing coverage.',
    ),
    'collision_pair_88f567dae780dfda': (
        'keep_distinct', '',
        'The reports combine Kerabari and 18 Kilo failures and are excluded until '
        'location-specific decomposition is supported.',
    ),
    'collision_pair_94ff68a6e2e6dcd1': (
        'keep_distinct', '',
        'The reports combine Kerabari and 18 Kilo failures and are excluded until '
        'location-specific decomposition is supported.',
    ),
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def find(parents: dict[str, str], item: str) -> str:
    parents.setdefault(item, item)
    if parents[item] != item:
        parents[item] = find(parents, parents[item])
    return parents[item]


def union(parents: dict[str, str], left: str, right: str) -> None:
    left_root, right_root = find(parents, left), find(parents, right)
    if left_root != right_root:
        parent, child = sorted((left_root, right_root))
        parents[child] = parent


def adjudicate(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    result = [dict(row) for row in rows]
    for row in result:
        pair_id = row['pair_id']
        if pair_id in DECISIONS:
            decision, survivor, notes = DECISIONS[pair_id]
            row['decision'] = decision
            row['merge_survivor_event_id'] = survivor
            row['review_notes'] = notes
        if row['group_id'] == 'collision_group_7b1b35543587ef1e' and row['decision'] == 'merge':
            row['merge_survivor_event_id'] = 'event_9087fe127ac8789a'
    return result


def materialize_overrides(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    merge_rows = [row for row in rows if row['decision'] == 'merge']
    parents: dict[str, str] = {}
    event_urls: dict[str, str] = {}
    for row in merge_rows:
        left, right = row['left_event_id'], row['right_event_id']
        union(parents, left, right)
        event_urls[left] = row['left_representative_url']
        event_urls[right] = row['right_representative_url']

    components: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in merge_rows:
        components[find(parents, row['left_event_id'])].append(row)

    output: list[dict[str, str]] = []
    for component_rows in components.values():
        survivors = {row['merge_survivor_event_id'] for row in component_rows}
        if len(survivors) != 1:
            raise ValueError(f'Conflicting survivors in component: {sorted(survivors)}')
        survivor = next(iter(survivors))
        pair_ids = sorted(row['pair_id'] for row in component_rows)
        anchors = sorted({
            url
            for row in component_rows
            for url in (row['left_representative_url'], row['right_representative_url'])
        })
        districts = {row['district'] for row in component_rows}
        dates = {row['event_date'] for row in component_rows}
        if len(districts) != 1 or len(dates) != 1:
            raise ValueError('A reviewed merge component crosses district or date identity')
        district = next(iter(districts))
        if component_rows[0]['group_id'] == 'collision_group_7b1b35543587ef1e':
            district = 'Nawalpur'
        digest = hashlib.sha256('|'.join(pair_ids).encode()).hexdigest()[:16]
        output.append({
            'merge_id': f'reviewed_merge_{digest}',
            'reviewed_at': REVIEWED_AT,
            'reviewed_by': component_rows[0]['reviewed_by'],
            'district': district,
            'event_date': next(iter(dates)),
            'survivor_url': event_urls[survivor],
            'member_anchor_urls_json': json.dumps(anchors, ensure_ascii=False),
            'reason': ' | '.join(row['review_notes'] for row in component_rows),
            'source_pair_ids_json': json.dumps(pair_ids),
        })
    return sorted(output, key=lambda row: row['merge_id'])


def main() -> None:
    source_rows = read_csv(SOURCE)
    adjudicated = adjudicate(source_rows)
    write_csv(ADJUDICATED, list(adjudicated[0]), adjudicated)
    overrides = materialize_overrides(adjudicated)
    write_csv(OVERRIDES, list(overrides[0]), overrides)
    print(f'Wrote {len(adjudicated)} adjudicated rows to {ADJUDICATED}')
    print(f'Wrote {len(overrides)} reviewed merge components to {OVERRIDES}')


if __name__ == '__main__':
    main()
