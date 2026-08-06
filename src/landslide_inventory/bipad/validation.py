"""External validation against BIPAD landslide records."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime
import json
from pathlib import Path
import re
from typing import Any, Iterable

from ..config import AppConfig
from ..db import connect_sqlite, initialize_sqlite
from ..gazetteer import all_districts, normalize_district
from ..utils import ensure_directory, stable_hash, utc_now_iso

DATE_COLUMNS = (
    'incident_date', 'event_date', 'date', 'occurred_on', 'incident_on', 'reported_on',
    'start_date', 'created_on', 'created_at', 'published_date', 'date_bs', 'date_ad',
    'Incident Date', 'Date', 'Incident On', 'Created On', 'Created At', 'Reported On',
)
DISTRICT_COLUMNS = (
    'district', 'district_name', 'district_en', 'District', 'District Name', 'district_title',
)
ID_COLUMNS = ('id', 'incident_id', 'bipad_id', 'event_id', 'situation_report_id', 'Incident ID', 'ID')
TITLE_COLUMNS = ('title', 'name', 'incident_title', 'description', 'event_title', 'Title', 'Name', 'Description')
DEATH_COLUMNS = ('deaths', 'death', 'people_death_count', 'death_count', 'total_death', 'Deaths', 'Death')
MISSING_COLUMNS = ('missing', 'people_missing_count', 'missing_count', 'Missing')
INJURED_COLUMNS = ('injured', 'people_injured_count', 'injured_count', 'Injured')
DISASTER_COLUMNS = ('disaster', 'hazard', 'type', 'incident_type', 'disaster_type', 'event_type', 'Disaster', 'Hazard', 'Type')
LANDSLIDE_TERMS = ('landslide', 'landslides', 'पहिरो', 'भूस्खलन')


@dataclass(frozen=True)
class CanonicalEvent:
    event_id: str
    event_date: date
    district: str
    municipality: str | None
    deaths: int | None
    missing: int | None
    injured: int | None
    representative_url: str | None
    representative_title: str | None


@dataclass(frozen=True)
class BipadEvent:
    bipad_id: str
    event_date: date
    district: str
    title: str | None
    deaths: int | None
    missing: int | None
    injured: int | None
    raw: dict[str, str]


@dataclass(frozen=True)
class BipadMatch:
    canonical: CanonicalEvent
    bipad: BipadEvent
    day_diff: int
    death_diff: int | None
    window_days: int


def run_bipad_validation_stage(config: AppConfig) -> int:
    """Match canonical events against BIPAD and export validation metrics."""

    initialize_sqlite(config.sqlite_path)
    output_dir = config.resolve_path('outputs_dir')
    ensure_directory(output_dir)
    bipad_path = resolve_bipad_input_path(config)
    if not bipad_path.exists():
        raise FileNotFoundError(
            f"BIPAD input CSV not found: {bipad_path}. "
            "Place the file at data/reference/bipad_landslides.csv or update bipad.bipad_input_path."
        )

    canonical_events = load_canonical_events(config.sqlite_path)
    bipad_events = load_bipad_events(bipad_path)
    windows = sorted(int(value) for value in config.raw.get('bipad', {}).get('match_windows_days', [1, 3, 7]))
    if not windows:
        windows = [1, 3, 7]

    all_matches = {window: match_events(canonical_events, bipad_events, window) for window in windows}
    metrics = build_metrics(canonical_events, bipad_events, all_matches, windows)
    max_window = max(windows)
    district_rows = build_district_coverage(canonical_events, bipad_events, all_matches, windows)
    generated_at = utc_now_iso()

    write_matches_csv(output_dir / 'bipad_matches.csv', all_matches[max_window])
    write_unmatched_canonical_csv(output_dir / 'bipad_unmatched_canonical.csv', canonical_events, all_matches[max_window])
    write_unmatched_bipad_csv(output_dir / 'bipad_unmatched_reference.csv', bipad_events, all_matches[max_window])
    write_district_coverage_csv(output_dir / 'bipad_district_coverage.csv', district_rows, windows)
    write_metrics_json(output_dir / 'bipad_metrics.json', metrics, generated_at, bipad_path)
    write_report(output_dir / 'bipad_validation_report.md', metrics, generated_at, bipad_path, windows)
    return len(all_matches[max_window])


def resolve_bipad_input_path(config: AppConfig) -> Path:
    raw_path = str(config.raw.get('bipad', {}).get('bipad_input_path', '')).strip()
    default_path = (config.config_path.parent / 'data/reference/bipad_landslides.csv').resolve()
    if not raw_path or raw_path.startswith('/absolute/path/to'):
        return default_path
    candidate = Path(raw_path)
    if candidate.is_absolute():
        return candidate
    return (config.config_path.parent / candidate).resolve()


def load_canonical_events(database_path: Path) -> list[CanonicalEvent]:
    with connect_sqlite(database_path) as connection:
        rows = connection.execute(
            """
            SELECT c.event_id, c.event_date_ad, c.district, c.municipality,
                   e.deaths, e.missing, e.injured,
                   json_extract(c.event_payload, '$.representative_url') AS representative_url,
                   e.title AS representative_title
            FROM canonical_events c
            LEFT JOIN article_events e ON e.url = json_extract(c.event_payload, '$.representative_url')
            WHERE c.event_date_ad IS NOT NULL AND c.district IS NOT NULL
            ORDER BY c.event_date_ad ASC, c.district ASC, c.event_id ASC
            """
        ).fetchall()
    return [
        CanonicalEvent(
            event_id=str(row['event_id']),
            event_date=date.fromisoformat(str(row['event_date_ad'])),
            district=str(row['district']),
            municipality=row['municipality'],
            deaths=_to_int(row['deaths']),
            missing=_to_int(row['missing']),
            injured=_to_int(row['injured']),
            representative_url=row['representative_url'],
            representative_title=row['representative_title'],
        )
        for row in rows
    ]


def load_bipad_events(path: Path) -> list[BipadEvent]:
    with path.open('r', encoding='utf-8-sig', newline='') as handle:
        sample = handle.read(4096)
        handle.seek(0)
        dialect = csv.Sniffer().sniff(sample) if sample.strip() else csv.excel
        reader = csv.DictReader(handle, dialect=dialect)
        rows = [dict(row) for row in reader]

    events: list[BipadEvent] = []
    for index, row in enumerate(rows, start=1):
        if not _is_landslide_row(row):
            continue
        parsed_date = _first_date(row, DATE_COLUMNS)
        district = _first_district(row, DISTRICT_COLUMNS)
        if parsed_date is None or district is None:
            continue
        raw_id = _first_value(row, ID_COLUMNS)
        title = _first_value(row, TITLE_COLUMNS)
        events.append(
            BipadEvent(
                bipad_id=raw_id or f"bipad_{stable_hash(str(index), parsed_date.isoformat(), district)[:12]}",
                event_date=parsed_date,
                district=district,
                title=title,
                deaths=_first_int(row, DEATH_COLUMNS),
                missing=_first_int(row, MISSING_COLUMNS),
                injured=_first_int(row, INJURED_COLUMNS),
                raw={str(key): str(value or '') for key, value in row.items()},
            )
        )
    return events


def match_events(canonical_events: list[CanonicalEvent], bipad_events: list[BipadEvent], window_days: int) -> list[BipadMatch]:
    candidates: list[tuple[int, int, str, str, CanonicalEvent, BipadEvent]] = []
    for canonical in canonical_events:
        for bipad in bipad_events:
            if canonical.district != bipad.district:
                continue
            day_diff = abs((canonical.event_date - bipad.event_date).days)
            if day_diff > window_days:
                continue
            death_diff = _death_diff(canonical, bipad)
            candidates.append((day_diff, death_diff if death_diff is not None else 9999, canonical.event_id, bipad.bipad_id, canonical, bipad))

    matched_canonical: set[str] = set()
    matched_bipad: set[str] = set()
    matches: list[BipadMatch] = []
    for day_diff, death_sort, _canonical_id, _bipad_id, canonical, bipad in sorted(candidates):
        if canonical.event_id in matched_canonical or bipad.bipad_id in matched_bipad:
            continue
        matched_canonical.add(canonical.event_id)
        matched_bipad.add(bipad.bipad_id)
        matches.append(BipadMatch(canonical, bipad, day_diff, None if death_sort == 9999 else death_sort, window_days))
    return matches


def build_metrics(
    canonical_events: list[CanonicalEvent],
    bipad_events: list[BipadEvent],
    all_matches: dict[int, list[BipadMatch]],
    windows: list[int],
) -> dict[str, Any]:
    canonical_count = len(canonical_events)
    bipad_count = len(bipad_events)
    per_window: dict[str, dict[str, float | int]] = {}
    for window in windows:
        tp = len(all_matches[window])
        precision = tp / canonical_count if canonical_count else 0.0
        recall = tp / bipad_count if bipad_count else 0.0
        per_window[str(window)] = {
            'window_days': window,
            'matches': tp,
            'canonical_events': canonical_count,
            'bipad_events': bipad_count,
            'precision': precision,
            'recall': recall,
            'f1': _f1(precision, recall),
        }
    return {
        'canonical_events': canonical_count,
        'bipad_events': bipad_count,
        'windows': per_window,
    }


def build_district_coverage(
    canonical_events: list[CanonicalEvent],
    bipad_events: list[BipadEvent],
    all_matches: dict[int, list[BipadMatch]],
    windows: list[int],
) -> list[dict[str, Any]]:
    districts = sorted(set(all_districts()) | {event.district for event in canonical_events} | {event.district for event in bipad_events})
    rows: list[dict[str, Any]] = []
    for district in districts:
        canonical_count = sum(1 for event in canonical_events if event.district == district)
        bipad_count = sum(1 for event in bipad_events if event.district == district)
        row: dict[str, Any] = {
            'district': district,
            'canonical_events': canonical_count,
            'bipad_events': bipad_count,
        }
        for window in windows:
            matches = [match for match in all_matches[window] if match.canonical.district == district]
            matched_count = len(matches)
            row[f'matches_{window}d'] = matched_count
            row[f'precision_{window}d'] = matched_count / canonical_count if canonical_count else 0.0
            row[f'recall_{window}d'] = matched_count / bipad_count if bipad_count else 0.0
        rows.append(row)
    return rows


def write_matches_csv(path: Path, matches: list[BipadMatch]) -> None:
    fieldnames = [
        'canonical_event_id', 'canonical_date', 'canonical_district', 'canonical_municipality',
        'canonical_deaths', 'canonical_missing', 'canonical_injured', 'canonical_title', 'canonical_url',
        'bipad_id', 'bipad_date', 'bipad_district', 'bipad_deaths', 'bipad_missing', 'bipad_injured',
        'bipad_title', 'day_diff', 'death_diff', 'window_days',
    ]
    rows = [
        {
            'canonical_event_id': match.canonical.event_id,
            'canonical_date': match.canonical.event_date.isoformat(),
            'canonical_district': match.canonical.district,
            'canonical_municipality': match.canonical.municipality or '',
            'canonical_deaths': _blank_none(match.canonical.deaths),
            'canonical_missing': _blank_none(match.canonical.missing),
            'canonical_injured': _blank_none(match.canonical.injured),
            'canonical_title': match.canonical.representative_title or '',
            'canonical_url': match.canonical.representative_url or '',
            'bipad_id': match.bipad.bipad_id,
            'bipad_date': match.bipad.event_date.isoformat(),
            'bipad_district': match.bipad.district,
            'bipad_deaths': _blank_none(match.bipad.deaths),
            'bipad_missing': _blank_none(match.bipad.missing),
            'bipad_injured': _blank_none(match.bipad.injured),
            'bipad_title': match.bipad.title or '',
            'day_diff': match.day_diff,
            'death_diff': _blank_none(match.death_diff),
            'window_days': match.window_days,
        }
        for match in matches
    ]
    _write_csv(path, fieldnames, rows)


def write_unmatched_canonical_csv(path: Path, canonical_events: list[CanonicalEvent], matches: list[BipadMatch]) -> None:
    matched = {match.canonical.event_id for match in matches}
    rows = [
        {
            'event_id': event.event_id,
            'event_date': event.event_date.isoformat(),
            'district': event.district,
            'municipality': event.municipality or '',
            'deaths': _blank_none(event.deaths),
            'missing': _blank_none(event.missing),
            'injured': _blank_none(event.injured),
            'title': event.representative_title or '',
            'url': event.representative_url or '',
        }
        for event in canonical_events
        if event.event_id not in matched
    ]
    _write_csv(path, ['event_id', 'event_date', 'district', 'municipality', 'deaths', 'missing', 'injured', 'title', 'url'], rows)


def write_unmatched_bipad_csv(path: Path, bipad_events: list[BipadEvent], matches: list[BipadMatch]) -> None:
    matched = {match.bipad.bipad_id for match in matches}
    rows = [
        {
            'bipad_id': event.bipad_id,
            'event_date': event.event_date.isoformat(),
            'district': event.district,
            'deaths': _blank_none(event.deaths),
            'missing': _blank_none(event.missing),
            'injured': _blank_none(event.injured),
            'title': event.title or '',
            'raw_json': json.dumps(event.raw, ensure_ascii=False, sort_keys=True),
        }
        for event in bipad_events
        if event.bipad_id not in matched
    ]
    _write_csv(path, ['bipad_id', 'event_date', 'district', 'deaths', 'missing', 'injured', 'title', 'raw_json'], rows)


def write_district_coverage_csv(path: Path, rows: list[dict[str, Any]], windows: list[int]) -> None:
    fieldnames = ['district', 'canonical_events', 'bipad_events']
    for window in windows:
        fieldnames.extend([f'matches_{window}d', f'precision_{window}d', f'recall_{window}d'])
    _write_csv(path, fieldnames, rows)


def write_metrics_json(path: Path, metrics: dict[str, Any], generated_at: str, bipad_path: Path) -> None:
    payload = {'generated_at': generated_at, 'bipad_input_path': str(bipad_path), **metrics}
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding='utf-8')


def write_report(path: Path, metrics: dict[str, Any], generated_at: str, bipad_path: Path, windows: list[int]) -> None:
    lines = [
        '# BIPAD Validation Report',
        '',
        f'Generated at: {generated_at}',
        f'BIPAD input: `{bipad_path}`',
        '',
        '## Core Counts',
        f"- Canonical events: {metrics['canonical_events']}",
        f"- BIPAD events: {metrics['bipad_events']}",
        '',
        '## Matching Metrics',
    ]
    for window in windows:
        row = metrics['windows'][str(window)]
        lines.extend([
            f"- +/- {window} days: matches={row['matches']}, precision={row['precision']:.3f}, recall={row['recall']:.3f}, F1={row['f1']:.3f}",
        ])
    lines.extend([
        '',
        'Precision uses canonical events as predictions; recall uses BIPAD rows as the external reference.',
    ])
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def _write_csv(path: Path, fieldnames: list[str], rows: Iterable[dict[str, Any]]) -> None:
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _is_landslide_row(row: dict[str, str]) -> bool:
    disaster_value = _first_value(row, DISASTER_COLUMNS)
    if not disaster_value:
        return True
    normalized = disaster_value.casefold()
    return any(term.casefold() in normalized for term in LANDSLIDE_TERMS)


def _first_value(row: dict[str, Any], candidates: tuple[str, ...]) -> str | None:
    normalized = {_normalize_header(key): value for key, value in row.items()}
    for candidate in candidates:
        value = row.get(candidate)
        if value not in (None, ''):
            return str(value).strip()
        value = normalized.get(_normalize_header(candidate))
        if value not in (None, ''):
            return str(value).strip()
    return None


def _first_date(row: dict[str, Any], candidates: tuple[str, ...]) -> date | None:
    for candidate in candidates:
        value = _first_value(row, (candidate,))
        parsed = parse_date(value)
        if parsed is not None:
            return parsed
    for value in row.values():
        parsed = parse_date(str(value) if value is not None else None)
        if parsed is not None:
            return parsed
    return None


def _first_district(row: dict[str, Any], candidates: tuple[str, ...]) -> str | None:
    for candidate in candidates:
        value = _first_value(row, (candidate,))
        normalized = normalize_district_value(value)
        if normalized is not None:
            return normalized
    return None


def _first_int(row: dict[str, Any], candidates: tuple[str, ...]) -> int | None:
    value = _first_value(row, candidates)
    return _to_int(value)


def parse_date(value: str | None) -> date | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    if not cleaned:
        return None
    cleaned = cleaned.replace('T', ' ').split()[0]
    cleaned = cleaned.replace('.', '-').replace('/', '-')
    for fmt in ('%Y-%m-%d', '%d-%m-%Y', '%m-%d-%Y', '%Y-%m', '%Y'):
        try:
            parsed = datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
        return parsed.date()
    match = re.search(r'(20\d{2}|201[5-9])[-/]([01]?\d)[-/]([0-3]?\d)', str(value))
    if match:
        try:
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            return None
    return None


def normalize_district_value(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    if not cleaned:
        return None
    for lang in ('en', 'np'):
        normalized = normalize_district(cleaned, lang)
        if normalized is not None:
            return normalized
    return None


def _death_diff(canonical: CanonicalEvent, bipad: BipadEvent) -> int | None:
    if canonical.deaths is None or bipad.deaths is None:
        return None
    return abs(canonical.deaths - bipad.deaths)


def _f1(precision: float, recall: float) -> float:
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def _to_int(value: Any) -> int | None:
    if value in (None, ''):
        return None
    text = str(value).strip()
    if not text:
        return None
    match = re.search(r'-?\d+', text.replace(',', ''))
    if match is None:
        return None
    return int(match.group(0))


def _blank_none(value: Any) -> Any:
    return '' if value is None else value


def _normalize_header(value: str) -> str:
    return re.sub(r'[^a-z0-9]+', '_', value.strip().casefold()).strip('_')
