"""Unified article extraction stage."""

from __future__ import annotations

import csv
from dataclasses import dataclass
import json
import re
from pathlib import Path
from typing import Any, Callable

from ..config import AppConfig
from ..db import connect_sqlite, initialize_sqlite
from ..gazetteer import all_districts, district_to_province, normalize_district, normalize_municipality, municipality_to_district
from ..gazetteer_municipality import municipality_districts
from ..nlp_en import extract_en
from ..nlp_np import extract_np
from ..utils import ensure_directory, stable_hash, utc_now_iso
from datetime import date, datetime

ExtractorFunc = Callable[[str | None, str, str | None, dict[str, Callable[..., Any]], dict[str, Any]], dict[str, Any]]
CONFIDENCE_FIELDS = {
    'class': 'conf_class',
    'event_date_ad': 'conf_date',
    'district': 'conf_district',
    'province': 'conf_district',
    'municipality': 'conf_place',
    'ward': 'conf_place',
    'place_admin_level': 'conf_place',
    'place_name_raw': 'conf_place',
    'place_candidates_json': 'conf_place',
    'deaths': 'conf_fatalities',
    'missing': 'conf_fatalities',
    'injured': 'conf_fatalities',
    'trigger': 'conf_trigger',
}
BATCH_SIZE = 100
EXTRACT_TEXT_CHAR_LIMIT = 4000

NP_LEAD_DATE_PATTERN = re.compile(
    r'(?:[०-९0-9]{3,4}\s*)?(?:[०-९0-9]{1,2}\s*(?:बैशाख|वैशाख|जेठ|असार|साउन|भदौ|असोज|कात्तिक|कार्तिक|मंसिर|पुष|पुस|माघ|फागुन|चैत)|(?:बैशाख|वैशाख|जेठ|असार|साउन|भदौ|असोज|कात्तिक|कार्तिक|मंसिर|पुष|पुस|माघ|फागुन|चैत)\s*[०-९0-9]{1,2})(?:\s*गते)?(?:\s*,?\s*[ऀ-ॿA-Za-z]+)?'
)
MYREPUBLICA_TITLE_SUFFIX_PATTERN = re.compile(
    r'\s*-\s*myRepublica\s*-\s*The New York Times Partner.*$',
    re.IGNORECASE,
)
MYREPUBLICA_LEAD_PATTERN = re.compile(
    r'(?:By\s+[A-Z][A-Za-z.\s-]+?\s+)?'
    r'(?:[A-Z][A-Z.-]+(?:\s+[A-Z][A-Z.-]+)*|[A-Z][a-z.-]+(?:\s+[A-Z][a-z.-]+)*)'
    r',\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec|'
    r'January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}:',
)
MYREPUBLICA_DATELINE_PATTERN = re.compile(
    r'\b(?:[A-Z][A-Z.-]+(?:\s+[A-Z][A-Z.-]+)*|[A-Z][a-z.-]+(?:\s+[A-Z][a-z.-]+){0,3})'
    r'(?:\s+\([A-Z][A-Za-z.-]*(?:\s+[A-Z][A-Za-z.-]*)*\))?,\s+'
    r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec|'
    r'January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}:',
)
MYREPUBLICA_PREAMBLE_IMPACT_PATTERN = re.compile(
    r'\b(?:\d+|[A-Za-z-]+)\s+(?:killed|dead|missing|injured)\b',
    re.IGNORECASE,
)

CLASS_ONE_REVIEW_PATTERNS = (
    re.compile(r'\bin\s+\d+\s+years\b', re.IGNORECASE),
    re.compile(r'\bat high risk of landslide\b', re.IGNORECASE),
    re.compile(r'\bgrowing incidents? of landslide\b', re.IGNORECASE),
    re.compile(r'\beffective measures needed\b', re.IGNORECASE),
    re.compile(r'\broad to recovery\b', re.IGNORECASE),
    re.compile(r'\bfear still haunts\b', re.IGNORECASE),
    re.compile(r'\brecent landslides? and floods?\b', re.IGNORECASE),
)

FALLBACK_EVENT_LANDSLIDE_PATTERN = re.compile(r'(?:\blandslides?\b|पहिरो|भूस्खलन)', re.IGNORECASE)
FALLBACK_EVENT_NUMBER_PATTERN = re.compile(r'(?:\b\d+\b|[०-९]+)', re.IGNORECASE)
FALLBACK_EVENT_IMPACT_PATTERN = re.compile(
    r'(?:\bkilled\b|\bdead\b|\bdies?\b|\bmissing\b|\binjured\b|\bdisplaced\b|\bswept away\b|\bburied\b|\bdeath\b|मृत्यु|मृत|बेपत्ता|घाइते|विस्थापित|बगायो|पुरियो)',
    re.IGNORECASE,
)
FALLBACK_EVENT_STRONG_IMPACT_PATTERN = re.compile(
    r'(?:\bkilled\b|\bdead\b|\bdies?\b|\bmissing\b|\binjured\b|\bswept away\b|\bburied\b|\bdeath\b|मृत्यु|मृत|बेपत्ता|घाइते|बगायो|पुरियो)',
    re.IGNORECASE,
)
FALLBACK_EVENT_FOLLOWUP_PATTERN = re.compile(
    r'(?:search ongoing|still missing|bodies recovered|body recovered|खोजी जारी|खोजी नगरिने|शव भेटियो|शव फेला|शव निकालियो|राहत दिइयो|राहत दिइने|क्षतिपूर्ति)',
    re.IGNORECASE,
)

OUTPUT_COLUMNS = [
    'url', 'source', 'title', 'published_date_raw', 'published_date_ad',
    'route_lang', 'mixed_flag', 'class', 'event_date_ad', 'district', 'province',
    'municipality', 'ward', 'place_admin_level', 'place_name_raw', 'place_candidates_json',
    'deaths', 'missing', 'injured', 'trigger', 'conf_class', 'conf_date',
    'conf_district', 'conf_place', 'conf_fatalities', 'conf_trigger', 'extracted_at',
]


@dataclass(frozen=True)
class ArticleRow:
    url: str
    source: str
    title: str | None
    year_hint: int | None
    published_date_raw: str | None
    published_date_ad: str | None
    text: str
    route_lang: str
    mixed_flag: bool


def run_extract_stage(config: AppConfig) -> int:
    """Build article-level extracted events and export them to CSV."""

    initialize_sqlite(config.sqlite_path)
    rows = list(_article_rows(config.sqlite_path))
    extracted_at = utc_now_iso()
    study_start = date.fromisoformat(config.raw['study_period']['start'])
    study_end = date.fromisoformat(config.raw['study_period']['end'])
    keywords_cfg = dict(config.raw['keywords'])
    gazetteer = {
        'normalize_district': lambda name: normalize_district(name, 'en'),
        'normalize_municipality': lambda name: normalize_municipality(name, 'en'),
        'municipality_to_district': municipality_to_district,
        'district_to_province': district_to_province,
    }
    np_gazetteer = {
        'normalize_district': lambda name: normalize_district(name, 'np'),
        'normalize_municipality': lambda name: normalize_municipality(name, 'np'),
        'municipality_to_district': municipality_to_district,
        'district_to_province': district_to_province,
    }

    records: list[dict[str, Any]] = []
    with connect_sqlite(config.sqlite_path) as connection:
        for index, row in enumerate(rows, start=1):
            record = build_article_event_record(
                row=row,
                extracted_at=extracted_at,
                keywords_cfg=keywords_cfg,
                en_gazetteer=gazetteer,
                np_gazetteer=np_gazetteer,
                study_start=study_start,
                study_end=study_end,
            )
            records.append(record)
            upsert_article_event(connection, record)
            if index % BATCH_SIZE == 0:
                connection.commit()
        connection.commit()
    export_article_events_csv(config.resolve_path('outputs_dir') / 'article_events.csv', records)
    return len(records)


def build_article_event_record(
    *,
    row: ArticleRow,
    extracted_at: str,
    keywords_cfg: dict[str, Any],
    en_gazetteer: dict[str, Callable[..., Any]],
    np_gazetteer: dict[str, Callable[..., Any]],
    study_start: date,
    study_end: date,
    en_extractor: ExtractorFunc = extract_en,
    np_extractor: ExtractorFunc = extract_np,
) -> dict[str, Any]:
    """Build a normalized article_events row from raw article + routing state."""

    normalized_title = _normalize_source_title(row.source, row.title)
    extraction_text = _prepare_extraction_text(row.source, row.title, row.text)
    effective_year_hint = _effective_published_year_hint(row.published_date_ad, row.year_hint)
    if row.mixed_flag:
        en_result = en_extractor(
            normalized_title,
            extraction_text,
            row.published_date_ad,
            en_gazetteer,
            keywords_cfg,
            published_year_hint=effective_year_hint,
        )
        np_result = np_extractor(
            normalized_title,
            extraction_text,
            row.published_date_ad,
            np_gazetteer,
            keywords_cfg,
            published_year_hint=effective_year_hint,
        )
        result = merge_extractor_outputs(en_result, np_result)
    elif row.route_lang == 'np':
        result = np_extractor(
            normalized_title,
            extraction_text,
            row.published_date_ad,
            np_gazetteer,
            keywords_cfg,
            published_year_hint=effective_year_hint,
        )
    else:
        result = en_extractor(
            normalized_title,
            extraction_text,
            row.published_date_ad,
            en_gazetteer,
            keywords_cfg,
            published_year_hint=effective_year_hint,
        )

    canonical_districts = set(all_districts())
    district, municipality, ward = _reconcile_place(
        result.get('district'),
        result.get('municipality'),
        result.get('ward'),
        canonical_districts,
    )
    result['district'] = district
    result['municipality'] = municipality
    result['ward'] = ward
    if municipality is None and result.get('place_admin_level') in ('municipality', 'ward'):
        result['place_admin_level'] = 'district' if district else 'unknown'
    if municipality and district:
        result['province'] = district_to_province(district)
        result['conf_district'] = max(float(result.get('conf_district') or 0.0), 0.82)
    else:
        result['province'] = district_to_province(district) if district else None
    event_date_ad = _enforce_study_period(result.get('event_date_ad'), study_start, study_end)
    if event_date_ad != result.get('event_date_ad'):
        result['event_date_ad'] = None
        result['conf_date'] = 0.0
    if district is None and result.get('class') == 1:
        result['class'] = 2
        result['conf_class'] = min(float(result.get('conf_class') or 0.8), 0.8)
    if result.get('event_date_ad') is None and result.get('class') == 1:
        result['class'] = 2
        result['conf_class'] = min(float(result.get('conf_class') or 0.8), 0.8)
    if result.get('class') == 1 and _requires_class_one_review(row.title, extraction_text):
        result['class'] = 2
        result['conf_class'] = min(float(result.get('conf_class') or 0.8), 0.75)
    if _qualifies_for_specific_class_one(row, result, extraction_text):
        result['class'] = 1
        result['conf_class'] = max(float(result.get('conf_class') or 0.0), 0.78)

    return {
        'url': row.url,
        'source': row.source,
        'title': row.title,
        'published_date_raw': row.published_date_raw,
        'published_date_ad': row.published_date_ad,
        'route_lang': row.route_lang,
        'mixed_flag': int(row.mixed_flag),
        'class': result.get('class'),
        'event_date_ad': result.get('event_date_ad'),
        'district': result.get('district'),
        'province': result.get('province'),
        'municipality': result.get('municipality'),
        'ward': result.get('ward'),
        'place_admin_level': result.get('place_admin_level'),
        'place_name_raw': result.get('place_name_raw'),
        'place_candidates_json': result.get('place_candidates_json'),
        'deaths': result.get('deaths'),
        'missing': result.get('missing'),
        'injured': result.get('injured'),
        'trigger': result.get('trigger'),
        'conf_class': result.get('conf_class'),
        'conf_date': result.get('conf_date'),
        'conf_district': result.get('conf_district'),
        'conf_place': result.get('conf_place'),
        'conf_fatalities': result.get('conf_fatalities'),
        'conf_trigger': result.get('conf_trigger'),
        'extracted_at': extracted_at,
    }


def _prepare_extraction_text(source: str, title: str | None, text: str) -> str:
    cleaned_title = _normalize_source_title(source, title)
    cleaned_text = _trim_extraction_preamble(source, text or '')
    lead_text = cleaned_text[:EXTRACT_TEXT_CHAR_LIMIT]
    if cleaned_title and cleaned_title not in lead_text:
        return f"{cleaned_title}\n{lead_text}".strip()
    return lead_text



def _normalize_source_title(source: str, title: str | None) -> str | None:
    if not title:
        return title
    if source == 'myrepublica':
        return MYREPUBLICA_TITLE_SUFFIX_PATTERN.sub('', title).strip()
    return title.strip()



def _trim_extraction_preamble(source: str, text: str) -> str:
    if not text:
        return ''
    if source == 'myrepublica':
        lead_match = MYREPUBLICA_LEAD_PATTERN.search(text)
        min_offset = 40
        if lead_match is None:
            lead_match = MYREPUBLICA_DATELINE_PATTERN.search(text)
            min_offset = 1
        if lead_match is not None and lead_match.start() >= min_offset:
            prefix = text[:lead_match.start()].strip()
            if prefix and MYREPUBLICA_PREAMBLE_IMPACT_PATTERN.search(prefix) is not None:
                impact_lines = [line.strip() for line in prefix.splitlines() if MYREPUBLICA_PREAMBLE_IMPACT_PATTERN.search(line)]
                preserved = ' '.join(impact_lines[-2:]).strip()
                if preserved:
                    return f"{preserved}\n{text[lead_match.start():].lstrip()}"
            return text[lead_match.start():].lstrip()
    summary_markers = [pos for pos in (text.find('News Summary'), text.find('Generated by OK AI.')) if pos >= 0]
    if not summary_markers:
        return text
    start = min(summary_markers)
    date_match = NP_LEAD_DATE_PATTERN.search(text, start)
    if date_match is not None and date_match.start() - start <= 200:
        return text[date_match.start():].lstrip()
    return text[start:].lstrip()


def _effective_published_year_hint(published_date_ad: str | date | datetime | None, discovered_year_hint: int | str | None) -> int | None:
    if isinstance(published_date_ad, datetime):
        return published_date_ad.date().year
    if isinstance(published_date_ad, date):
        return published_date_ad.year
    if published_date_ad:
        try:
            return date.fromisoformat(str(published_date_ad)).year
        except ValueError:
            pass
    if discovered_year_hint is None:
        return None
    try:
        return int(discovered_year_hint)
    except (TypeError, ValueError):
        return None


# Ablation switch for the conflict rule measured in
# scripts/score_district_development.py. ``False`` is the chosen behaviour: an
# already-established district is kept and the contradicting municipality is
# dropped. Setting it to ``True`` restores the pre-2026-08-14 rule, in which a
# municipality's district always won, so the two can be compared on the labelled
# development set without editing code.
MUNICIPALITY_OVERRIDES_DISTRICT = False


def _reconcile_place(
    district: str | None,
    municipality: str | None,
    ward: str | None,
    canonical_districts: set[str],
) -> tuple[str | None, str | None, str | None]:
    """Make district, municipality and ward mutually consistent.

    A stored record must never assert a municipality that the gazetteer places
    outside its own district: district is the analysis unit for the rainfall
    study, and an internally inconsistent record cannot be validated.

    Two rules resolve a disagreement, and which one applies depends on whether
    the district is already established:

    * **No usable district.** The municipality supplies one. This is a pure
      gain and is what the enlarged gazetteer is for.
    * **A canonical district is already extracted.** Keep it and drop the
      municipality and ward. The language extractors have already adjudicated
      this exact conflict against the evidence in the text -- see
      ``nlp_en.extract._district_is_near_municipality``, which moves the
      district when the two names are written together, as in "Uttargaya rural
      municipality - 4, Rasuwa" under a Nuwakot dateline. Reaching this point
      means that adjudication declined, so the municipality is unsupported as
      the event location; typically it is a victim's home address ("the
      deceased ... of Chandrpur Municipality-1, Rautahat" in a story about a
      landslide in Rasuwa). Moving the event to it would relocate a case.

    This function previously let the municipality win unconditionally. That was
    harmless while the gazetteer held 142 local units, because a municipality
    rarely resolved at all; at 753 units it silently moved five of the first
    400 class-1 articles into the wrong district, every one of them a
    regression. The measurement is in ``scripts/measure_district_drift.py``.

    Ambiguous names -- fifteen canonical names exist in more than one district
    -- map to ``None`` through ``municipality_to_district``. They are consistent
    when the extracted district is one of their candidates, so they are checked
    against ``municipality_districts`` instead of being treated as a conflict.
    """

    established = district if district in canonical_districts else None
    if not municipality:
        return established, municipality, ward

    if MUNICIPALITY_OVERRIDES_DISTRICT:
        mapped = municipality_to_district(municipality)
        if mapped in canonical_districts:
            return mapped, municipality, ward
        return established, municipality, ward

    candidates = tuple(
        name for name in municipality_districts(municipality) if name in canonical_districts
    )
    if not candidates:
        mapped = municipality_to_district(municipality)
        candidates = (mapped,) if mapped in canonical_districts else ()

    if established is not None:
        if established in candidates:
            return established, municipality, ward
        return established, None, None

    # An unresolved district is filled from the municipality only when the name
    # is unambiguous. A name shared across districts cannot pick one for itself.
    if len(candidates) == 1:
        return candidates[0], municipality, ward
    return None, municipality, ward


def _enforce_study_period(event_date_ad: str | None, study_start: date, study_end: date) -> str | None:
    if not event_date_ad:
        return None
    try:
        value = date.fromisoformat(event_date_ad)
    except ValueError:
        return None
    if study_start <= value <= study_end:
        return event_date_ad
    return None


def merge_extractor_outputs(primary: dict[str, Any], secondary: dict[str, Any]) -> dict[str, Any]:
    """Merge two extractor outputs field-by-field using the higher confidence source."""

    merged = dict(primary)
    for field, confidence_field in CONFIDENCE_FIELDS.items():
        left_conf = float(primary.get(confidence_field) or 0.0)
        right_conf = float(secondary.get(confidence_field) or 0.0)
        if right_conf > left_conf:
            merged[field] = secondary.get(field)
            merged[confidence_field] = secondary.get(confidence_field)
    for confidence_field in ('conf_class', 'conf_date', 'conf_district', 'conf_place', 'conf_fatalities', 'conf_trigger'):
        merged[confidence_field] = max(float(primary.get(confidence_field) or 0.0), float(secondary.get(confidence_field) or 0.0))
    return merged


def upsert_article_event(connection, record: dict[str, Any]) -> None:
    """Upsert one article_events row keyed by article URL."""

    extracted_event_id = stable_hash(record['url'])
    payload = json.dumps({key: record.get(key) for key in OUTPUT_COLUMNS}, ensure_ascii=False, sort_keys=True)
    connection.execute(
        """
        INSERT INTO article_events (
            extracted_event_id, article_url, event_class, municipality, ward, place_name_raw,
            place_candidates_json, conf_place, event_payload, url, source, title, published_date_raw,
            published_date_ad, route_lang, mixed_flag, class, event_date_ad, district, province,
            place_admin_level, deaths, missing, injured, trigger, conf_class, conf_date, conf_district,
            conf_fatalities, conf_trigger, extracted_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(url) DO UPDATE SET
            extracted_event_id = excluded.extracted_event_id,
            article_url = excluded.article_url,
            event_class = excluded.event_class,
            municipality = excluded.municipality,
            ward = excluded.ward,
            place_name_raw = excluded.place_name_raw,
            place_candidates_json = excluded.place_candidates_json,
            conf_place = excluded.conf_place,
            event_payload = excluded.event_payload,
            source = excluded.source,
            title = excluded.title,
            published_date_raw = excluded.published_date_raw,
            published_date_ad = excluded.published_date_ad,
            route_lang = excluded.route_lang,
            mixed_flag = excluded.mixed_flag,
            class = excluded.class,
            event_date_ad = excluded.event_date_ad,
            district = excluded.district,
            province = excluded.province,
            place_admin_level = excluded.place_admin_level,
            deaths = excluded.deaths,
            missing = excluded.missing,
            injured = excluded.injured,
            trigger = excluded.trigger,
            conf_class = excluded.conf_class,
            conf_date = excluded.conf_date,
            conf_district = excluded.conf_district,
            conf_fatalities = excluded.conf_fatalities,
            conf_trigger = excluded.conf_trigger,
            extracted_at = excluded.extracted_at
        """,
        (
            extracted_event_id, record['url'], record['class'], record['municipality'], record['ward'],
            record['place_name_raw'], record['place_candidates_json'], record['conf_place'], payload,
            record['url'], record['source'], record['title'], record['published_date_raw'], record['published_date_ad'],
            record['route_lang'], record['mixed_flag'], record['class'], record['event_date_ad'], record['district'],
            record['province'], record['place_admin_level'], record['deaths'], record['missing'], record['injured'],
            record['trigger'], record['conf_class'], record['conf_date'], record['conf_district'],
            record['conf_fatalities'], record['conf_trigger'], record['extracted_at'],
        ),
    )


def export_article_events_csv(path: Path, records: list[dict[str, Any]]) -> None:
    """Export article event rows to a deterministic CSV."""

    ensure_directory(path.parent)
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        for record in sorted(records, key=lambda item: item['url']):
            writer.writerow({column: record.get(column) for column in OUTPUT_COLUMNS})


def _article_rows(database_path: Path) -> list[ArticleRow]:
    with connect_sqlite(database_path) as connection:
        rows = connection.execute(
            """
            SELECT r.url, r.source, r.title, r.published_date_raw, r.published_date_ad,
                   d.year_hint, COALESCE(r.text, '') AS text, l.route_lang, l.mixed_flag
            FROM raw_articles r
            INNER JOIN article_lang l ON l.url = r.url
            LEFT JOIN (
                SELECT url, MAX(year_hint) AS year_hint
                FROM discovered_urls
                GROUP BY url
            ) d ON d.url = r.url
            ORDER BY r.url ASC
            """
        ).fetchall()
    return [
        ArticleRow(
            url=str(row['url']),
            source=str(row['source']),
            title=row['title'],
            year_hint=int(row['year_hint']) if row['year_hint'] is not None else None,
            published_date_raw=row['published_date_raw'],
            published_date_ad=row['published_date_ad'],
            text=str(row['text'] or ''),
            route_lang=str(row['route_lang']),
            mixed_flag=bool(row['mixed_flag']),
        )
        for row in rows
    ]


def _requires_class_one_review(title: str | None, extraction_text: str) -> bool:
    """Return whether a row looks like retrospective, analysis, or partner-feed coverage."""

    combined = '\n'.join(part for part in ((title or '').strip(), extraction_text.strip()) if part)
    return any(pattern.search(combined) for pattern in CLASS_ONE_REVIEW_PATTERNS)


def _is_road_disruption_title(title: str | None) -> bool:
    title_cf = (title or '').casefold()
    return any(term in title_cf for term in ('road', 'highway', 'corridor')) and any(
        term in title_cf for term in ('block', 'blocks', 'blocked', 'obstruct', 'obstructed', 'disrupt', 'disrupts', 'disrupted', 'disturb', 'disturbs', 'disturbed')
    )




# A toll is cumulative only when the article also scopes it to a period or an
# area wider than the event -- "so far this monsoon", "nationwide", "in five
# years". Without one of these, "death toll" is just how a reporter states the
# casualty count of the event in front of them.
CUMULATIVE_SCOPE_PATTERN = re.compile(
    r'\bso far\b|\bto date\b|\bthis (?:monsoon|year|season)\b|\bsince the (?:monsoon|onset)\b'
    r'|\bnationwide\b|\bacross the country\b|\bin nepal\b|\bvarious districts\b'
    r'|\bin\s+(?:the\s+)?(?:past|last)?\s*\d+\s*(?:years?|months?|weeks?)\b'
    r'|अहिलेसम्म|हालसम्म|यो मनसुन|यसवर्ष|यस वर्ष|देशभर|देशैभरि|देशभरि|कुल',
    re.IGNORECASE,
)


def _is_cumulative_toll_update(title: str | None, extraction_text: str) -> bool:
    """Whether an article reports a RUNNING TOTAL rather than an event.

    The phrase "death toll" alone was treated as proof of a cumulative report.
    It is not: an ordinary single-event story routinely says "the death toll in
    the Gumthang landslide has reached 11". Measured on the locked test set,
    this veto blocked real single-event reports from class 1 --
    "11 killed, 20 others still missing in Gumthang landslide" and
    "55 die in Taplejung landslides" among them.

    A running total needs a *period or scope* as well as a toll. "Death toll
    reaches 11 in Gumthang" is an event; "death toll reaches 244 this monsoon"
    is a tally. That distinction is what the phrase alone could not make.
    """

    title_cf = (title or '').casefold()
    lowered = extraction_text.casefold()
    combined = f'{title_cf}\n{lowered}'
    # Nepali too: an English-only toll check is blind to exactly the articles
    # a bilingual pipeline exists to read.
    mentions_toll = 'death toll' in combined or any(
        term in combined for term in (
            'toll rises', 'toll climbs', 'toll reaches',
            'मृतकको संख्या', 'मृत्यु हुनेको संख्या', 'ज्यान गुमाउनेको संख्या',
        )
    )
    if not mentions_toll:
        return False
    # A toll becomes cumulative only when scoped to a period or a wider area.
    return CUMULATIVE_SCOPE_PATTERN.search(combined) is not None

def _qualifies_for_specific_class_one(row: ArticleRow, result: dict[str, Any], extraction_text: str) -> bool:
    """Return whether a Class 2 row is still specific enough for Class 1."""

    if result.get('class') not in {2, 3}:
        return False
    if result.get('district') is None:
        return False
    event_date_ad = result.get('event_date_ad')
    if not event_date_ad:
        return False
    title = (row.title or '').strip()
    combined = '\n'.join(part for part in (title, extraction_text.strip()) if part)
    if _requires_class_one_review(row.title, extraction_text):
        return False
    if _is_non_event_followup_for_class_one(combined):
        return False
    if _is_cumulative_toll_update(row.title, extraction_text):
        return False
    # NO HARD CASUALTY REQUIREMENT.
    #
    # This used to demand deaths/missing/injured > 0, which meant a
    # displacement-only event could never be class 1 -- "150 households
    # displaced as fresh landslide looms large in Parbat" was excluded despite
    # being a real, located, dated landslide. That contradicts
    # docs/ANNOTATION_RUBRIC.md, which is authoritative and does not require
    # casualties, and it contradicts LABELING_GUIDE.md too; only the older
    # manual_label_policy.md ever required them (review section 3.3).
    #
    # The gate is also redundant: _has_strong_fallback_impact below already
    # requires casualties OR strong impact evidence, so removing this line
    # widens the definition to "human OR settlement impact" rather than
    # removing the impact requirement altogether.
    if _is_road_disruption_title(row.title):
        return False
    if not title or not FALLBACK_EVENT_LANDSLIDE_PATTERN.search(combined):
        return False
    if not _has_strong_fallback_impact(result, combined):
        return False
    if not FALLBACK_EVENT_IMPACT_PATTERN.search(combined):
        return False
    return True


def _has_strong_fallback_impact(result: dict[str, Any], text: str) -> bool:
    """Return whether a fallback-date candidate has strong human-impact evidence."""

    for field in ('deaths', 'missing', 'injured'):
        value = result.get(field)
        if value is not None and int(value) > 0:
            return True
    return FALLBACK_EVENT_STRONG_IMPACT_PATTERN.search(text) is not None


def _is_non_event_followup_for_class_one(text: str) -> bool:
    """Return whether a row is clearly a relief/compensation-style follow-up."""

    lowered = text.casefold()
    return any(
        pattern in lowered
        for pattern in (
            'relief',
            'compensation',
            'families to receive relief',
            'राहत',
            'क्षतिपूर्ति',
            'सहयोग',
            'खोजी नगरिने',
            'खोजी गरिने छैन',
        )
    )
