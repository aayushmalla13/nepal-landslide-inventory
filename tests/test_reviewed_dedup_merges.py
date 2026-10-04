"""Tests for persistent, article-anchored reviewed dedup merges."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from landslide_inventory.unify.dedup_stage import EventRecord, assign_cluster_ids
from landslide_inventory.unify.reviewed_dedup_merges import (
    apply_reviewed_merges,
    load_reviewed_merges,
)


def event(url: str, municipality: str | None = 'Nilkantha Municipality') -> EventRecord:
    return EventRecord(
        url=url, source='test', title='Landslide', body_text='Landslide in Dhading.',
        event_date_ad='2024-07-16', district='Dhading', province='Bagmati',
        municipality=municipality, ward=None, place_name_raw='Nilkantha',
        deaths=None, missing=None, injured=None, trigger='rainfall', route_lang='en',
        event_class=1, in_nepal=1, conf_class=1, conf_date=1, conf_district=1,
        conf_place=1, conf_fatalities=1, conf_trigger=1,
    )


def write_override(path: Path, *, missing_anchor: bool = False) -> None:
    fields = [
        'merge_id', 'reviewed_at', 'reviewed_by', 'district', 'event_date',
        'survivor_url', 'member_anchor_urls_json', 'reason', 'source_pair_ids_json',
    ]
    row = {
        'merge_id': 'reviewed_merge_1', 'reviewed_at': '2026-09-26',
        'reviewed_by': 'human', 'district': 'Dhading', 'event_date': '2024-07-16',
        'survivor_url': (
            'https://a.test/1' if missing_anchor else 'https://b.test/2'
        ),
        'member_anchor_urls_json': json.dumps([
            'https://a.test/1',
            'https://missing.test/3' if missing_anchor else 'https://b.test/2',
        ]),
        'reason': 'Same named place and victims.',
        'source_pair_ids_json': '["pair-1"]',
    }
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerow(row)


def test_reviewed_merge_combines_clusters_and_preserves_survivor_id(tmp_path: Path) -> None:
    path = tmp_path / 'overrides.csv'
    write_override(path)
    clusters = [[event('https://a.test/1')], [event('https://b.test/2')]]
    original_ids, _ = assign_cluster_ids(clusters)

    merged, preferred, count = apply_reviewed_merges(
        clusters, load_reviewed_merges(path)
    )
    assigned, collisions = assign_cluster_ids(merged, preferred)

    assert count == 1
    assert len(merged) == 1
    assert {item.url for item in merged[0]} == {
        'https://a.test/1', 'https://b.test/2'
    }
    assert assigned[0] == original_ids[1]
    assert collisions == 0


def test_reviewed_merge_is_noop_when_filtered_non_survivor_is_missing(tmp_path: Path) -> None:
    path = tmp_path / 'overrides.csv'
    write_override(path, missing_anchor=True)
    clusters = [[event('https://a.test/1')], [event('https://b.test/2')]]

    merged, preferred, count = apply_reviewed_merges(
        clusters, load_reviewed_merges(path)
    )
    assert len(merged) == 2
    assert count == 0
    assigned, _ = assign_cluster_ids(merged, preferred)
    survivor_cluster = next(
        index
        for index, cluster in enumerate(merged)
        if cluster[0].url == 'https://a.test/1'
    )
    assert assigned[survivor_cluster]


def test_reviewed_merge_uses_first_remaining_anchor_when_survivor_is_filtered(
    tmp_path: Path,
) -> None:
    path = tmp_path / 'overrides.csv'
    write_override(path)
    clusters = [[event('https://a.test/1')]]

    merged, preferred, count = apply_reviewed_merges(
        clusters, load_reviewed_merges(path)
    )
    assert len(merged) == 1
    assert count == 0
    assert preferred


def test_reviewed_merge_fails_closed_when_anchor_is_ambiguous(tmp_path: Path) -> None:
    path = tmp_path / 'overrides.csv'
    write_override(path)
    clusters = [
        [event('https://a.test/1')],
        [event('https://b.test/2')],
        [event('https://b.test/2')],
    ]

    with pytest.raises(ValueError, match='expected at most one'):
        apply_reviewed_merges(clusters, load_reviewed_merges(path))


def test_reviewed_survivor_is_stable_when_merged_place_evidence_changes_base(
    tmp_path: Path,
) -> None:
    path = tmp_path / 'overrides.csv'
    write_override(path)
    clusters = [
        [event('https://a.test/1', municipality=None)],
        [event('https://b.test/2')],
    ]
    original_ids, _ = assign_cluster_ids(clusters)

    merged, preferred, _ = apply_reviewed_merges(clusters, load_reviewed_merges(path))
    assigned, _ = assign_cluster_ids(merged, preferred)

    assert assigned[0] == original_ids[1]
