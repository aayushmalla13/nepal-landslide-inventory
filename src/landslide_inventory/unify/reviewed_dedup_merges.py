"""Apply versioned human-reviewed dedup merges using stable article anchors."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

from ..config import AppConfig

if TYPE_CHECKING:
    from .dedup_stage import EventRecord


@dataclass(frozen=True)
class ReviewedMerge:
    merge_id: str
    reviewed_at: str
    reviewed_by: str
    district: str
    event_date: str
    survivor_url: str
    member_anchor_urls: tuple[str, ...]
    reason: str
    source_pair_ids: tuple[str, ...]


def merge_overrides_path(config: AppConfig) -> Path | None:
    value = config.raw.get('dedup', {}).get('reviewed_merge_overrides_path')
    if not value:
        return None
    path = Path(str(value))
    return path if path.is_absolute() else config.config_path.parent / path


def load_reviewed_merges(path: Path) -> list[ReviewedMerge]:
    with path.open(encoding='utf-8-sig', newline='') as handle:
        rows = list(csv.DictReader(handle))
    merges: list[ReviewedMerge] = []
    seen: set[str] = set()
    for row_number, row in enumerate(rows, start=2):
        merge_id = (row.get('merge_id') or '').strip()
        if not merge_id or merge_id in seen:
            raise ValueError(f'Reviewed merge row {row_number}: unique merge_id is required')
        seen.add(merge_id)
        reviewed_at = (row.get('reviewed_at') or '').strip()
        try:
            date.fromisoformat(reviewed_at)
        except ValueError as exc:
            raise ValueError(
                f'Reviewed merge row {row_number}: reviewed_at must be YYYY-MM-DD'
            ) from exc
        try:
            anchors = tuple(json.loads(row.get('member_anchor_urls_json') or ''))
            pair_ids = tuple(json.loads(row.get('source_pair_ids_json') or '[]'))
        except (json.JSONDecodeError, TypeError) as exc:
            raise ValueError(
                f'Reviewed merge row {row_number}: malformed JSON list'
            ) from exc
        survivor_url = (row.get('survivor_url') or '').strip()
        if len(set(anchors)) < 2 or survivor_url not in anchors:
            raise ValueError(
                f'Reviewed merge row {row_number}: at least two unique anchors are required '
                'and survivor_url must be one of them'
            )
        required = {
            'reviewed_by': (row.get('reviewed_by') or '').strip(),
            'district': (row.get('district') or '').strip(),
            'event_date': (row.get('event_date') or '').strip(),
            'reason': (row.get('reason') or '').strip(),
        }
        if not all(required.values()):
            raise ValueError(f'Reviewed merge row {row_number}: required field is blank')
        date.fromisoformat(required['event_date'])
        merges.append(
            ReviewedMerge(
                merge_id=merge_id,
                reviewed_at=reviewed_at,
                reviewed_by=required['reviewed_by'],
                district=required['district'],
                event_date=required['event_date'],
                survivor_url=survivor_url,
                member_anchor_urls=anchors,
                reason=required['reason'],
                source_pair_ids=pair_ids,
            )
        )
    return merges


def apply_reviewed_merges(
    clusters: list[list[EventRecord]],
    merges: list[ReviewedMerge],
) -> tuple[list[list[EventRecord]], dict[int, str], int]:
    """Merge reviewed components and preserve each selected survivor identity."""

    if not merges:
        return clusters, {}, 0

    from .dedup_stage import assign_cluster_ids, event_sort_key

    initial_ids, _ = assign_cluster_ids(clusters)
    anchors: dict[tuple[str, str, str], list[int]] = {}
    for index, cluster in enumerate(clusters):
        for event in cluster:
            anchors.setdefault(
                (event.url, event.district, event.event_date_ad), []
            ).append(index)

    parents = list(range(len(clusters)))

    def find(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent, child = sorted((left_root, right_root))
            parents[child] = parent

    survivors: list[tuple[int, str, str]] = []
    applied_count = 0
    for override in merges:
        cluster_indexes: list[int] = []
        index_by_url: dict[str, int] = {}
        for url in override.member_anchor_urls:
            matches = anchors.get((url, override.district, override.event_date), [])
            if len(matches) > 1:
                raise ValueError(
                    f'{override.merge_id}: anchor {url!r} resolved to {len(matches)} '
                    'eligible clusters; expected at most one'
                )
            if matches:
                cluster_indexes.append(matches[0])
                index_by_url[url] = matches[0]
        cluster_indexes = list(dict.fromkeys(cluster_indexes))
        if not cluster_indexes:
            # Every reviewed member was intentionally filtered upstream. The
            # duplicate relationship is now obsolete for this pipeline run.
            continue
        survivor_index = index_by_url.get(override.survivor_url, cluster_indexes[0])
        first = cluster_indexes[0]
        for index in cluster_indexes[1:]:
            union(first, index)
        if len(cluster_indexes) > 1:
            applied_count += 1
        survivors.append((first, initial_ids[survivor_index], override.merge_id))

    preferred_by_root: dict[int, str] = {}
    for source_root, preferred_id, merge_id in survivors:
        root = find(source_root)
        previous = preferred_by_root.setdefault(root, preferred_id)
        if previous != preferred_id:
            raise ValueError(
                f'{merge_id}: connected reviewed merges nominate conflicting survivors '
                f'{previous!r} and {preferred_id!r}'
            )

    grouped: dict[int, list[EventRecord]] = {}
    for index, cluster in enumerate(clusters):
        grouped.setdefault(find(index), []).extend(cluster)
    rebuilt = sorted(
        [sorted(cluster, key=event_sort_key) for cluster in grouped.values()],
        key=lambda cluster: event_sort_key(cluster[0]),
    )
    root_by_record = {
        event.record_key: root
        for root, cluster in grouped.items()
        for event in cluster
    }
    preferred: dict[int, str] = {}
    for index, cluster in enumerate(rebuilt):
        root = root_by_record[cluster[0].record_key]
        if root in preferred_by_root:
            preferred[index] = preferred_by_root[root]
    return rebuilt, preferred, applied_count
