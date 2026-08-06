"""English event extraction helpers."""

from __future__ import annotations

from datetime import date, datetime, timedelta
import json
import re
from typing import Any, Callable

from ..gazetteer import district_to_province, normalize_district
from ..gazetteer_municipality import municipality_to_district, normalize_municipality
from .places import EN_DISTRICT_ALIASES_PATTERN, extract_place_en

MONTH_NAMES = (
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December',
)
MONTH_ABBR_NAMES = (
    'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
    'Jul', 'Aug', 'Sep', 'Sept', 'Oct', 'Nov', 'Dec',
)
MONTH_PATTERN = '|'.join(MONTH_NAMES)
MONTH_ABBR_PATTERN = '|'.join(MONTH_ABBR_NAMES)
DATE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(rf'\b({MONTH_PATTERN})\s+(\d{{1,2}}),\s*(\d{{4}})\b', re.IGNORECASE), '%B %d %Y'),
    (re.compile(rf'\b(\d{{1,2}})\s+({MONTH_PATTERN})\s+(\d{{4}})\b', re.IGNORECASE), '%d %B %Y'),
    (re.compile(rf'\b({MONTH_ABBR_PATTERN})\s+(\d{{1,2}}),\s*(\d{{4}})\b', re.IGNORECASE), '%b %d %Y'),
    (re.compile(rf'\b(\d{{1,2}})\s+({MONTH_ABBR_PATTERN})\s+(\d{{4}})\b', re.IGNORECASE), '%d %b %Y'),
)
MONTH_DAY_NO_YEAR_PATTERN = re.compile(rf'\b({MONTH_PATTERN}|{MONTH_ABBR_PATTERN})\s+(\d{{1,2}})(?!,\s*\d{{4}})\b', re.IGNORECASE)
WARD_PATTERN = re.compile(r'\bWard\s*(?:No\.?)?\s*(\d+)\b', re.IGNORECASE)
MUNICIPALITY_PATTERN = re.compile(
    r'\b([A-Z][A-Za-z.-]*(?:\s+[A-Z][A-Za-z.-]*){0,3})\s+'
    r'(?:Municipality|Rural Municipality|Metropolitan City|Sub-Metropolitan City|municipality|rural municipality|metropolitan city|sub-metropolitan city)(?:-\d+)?\b'
)
WARD_MUNICIPALITY_PATTERN = re.compile(r'\b([A-Z][A-Za-z.-]*(?:\s+[A-Z][A-Za-z.-]*){0,3})-\d+\b')
QUALIFIER_PATTERN = re.compile(r'\b(?:at least|more than|over|around|about|approximately|feared|at most)\b', re.IGNORECASE)
DIRECT_EVENT_TITLE_PATTERN = re.compile(
    r'(?:landslide|mudslide|rockfall).{0,80}(?:killed|dead|died|missing|injured|buried)|'
    r'(?:killed|dead|died|missing|injured|buried).{0,80}(?:landslide|mudslide|rockfall)',
    re.IGNORECASE,
)
WEEKDAY_NAMES = ('monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday')
WEEKDAY_INDEX = {name: idx for idx, name in enumerate(WEEKDAY_NAMES)}
WEEKDAY_PATTERN = re.compile(r'\b(?:on\s+)?(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)(?:\s+(?:morning|afternoon|evening|night))?\b', re.IGNORECASE)
PREVIOUS_DAY_PATTERN = re.compile(
    r'\b(?:yesterday|last night|previous night|overnight|since last night)\b',
    re.IGNORECASE,
)
SAME_DAY_PATTERN = re.compile(
    r'\b(?:today|this morning|this afternoon|this evening|tonight|today morning)\b',
    re.IGNORECASE,
)
ONGOING_WEEKDAY_PATTERN = re.compile(
    r'\b(?:since|from)\s+(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b',
    re.IGNORECASE,
)
ONGOING_WEEKDAY_EVENT_START_PATTERN = re.compile(
    r'\b(?:occurred|started|began|hit|swept away|triggered)\b[^.]{0,120}\b(?:since|from)\s+(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)(?:\s+night)?\b',
    re.IGNORECASE,
)
SEARCH_CONTEXT_PATTERN = re.compile(
    r'\b(?:search|searched|searching|rescue|rescued|rescuing|conduct\s+a\s+search|difficult\s+to\s+search|could\s+not\s+conduct\s+a\s+search)\b',
    re.IGNORECASE,
)
RISK_TITLE_PATTERN = re.compile(
    r'\b(?:face|facing|faces|at\s+risk\s+of|risk\s+of)\b[^\n]{0,120}\b(?:landslide|landslides|mudslide|mudslides|rockfall|rockfalls)\b',
    re.IGNORECASE,
)
RAINFALL_CAUSAL_PATTERN = re.compile(
    r'(?:after|following|due to|because of|amid|triggered by|caused by)\s+(?:(?:heavy|continuous|incessant|relentless|torrential|monsoon)\s+){0,2}(?:rain|rains|rainfall|downpour)'
    r'|(?:(?:heavy|continuous|incessant|relentless|torrential|monsoon)\s+)+(?:rain|rains|rainfall|downpour).{0,80}(?:triggered|caused|led to|resulted in|sparked).{0,40}(?:landslide|mudslide|rockfall)'
    r'|(?:landslide|mudslide|rockfall).{0,80}(?:after|following|due to|because of|amid|triggered by|caused by).{0,40}(?:(?:heavy|continuous|incessant|relentless|torrential|monsoon)\s+){0,2}(?:rain|rains|rainfall|downpour)'
    r'|(?:rain|rains|rainfall|downpour)-triggered\s+(?:landslide|landslides|mudslide|mudslides|rockfall|rockfalls)',
    re.IGNORECASE,
)
RAINFALL_SIGNAL_PATTERN = re.compile(
    r'(?:(?:heavy|continuous|incessant|relentless|torrential|monsoon)\s+){0,2}(?:rain|rains|rainfall|downpour)|(?:rain|rainfall|downpour)-triggered',
    re.IGNORECASE,
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
    r'\b(?:[A-Z][A-Z.-]+(?:\s+[A-Z][A-Z.-]+)*|[A-Z][a-z.-]+(?:\s+[A-Z][a-z.-]+){0,3}),\s+'
    r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec|'
    r'January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}:',
)
MYREPUBLICA_PREAMBLE_IMPACT_PATTERN = re.compile(
    r'\b(?:\d+|[A-Za-z-]+)\s+(?:killed|dead|missing|injured)\b',
    re.IGNORECASE,
)
DATELINE_DISTRICT_PATTERN = re.compile(
    r'^(?:By\s+[A-Z][A-Za-z.\s-]+\s+)?(?P<primary>[A-Z][A-Za-z.-]*(?:\s+[A-Z][A-Za-z.-]*)*)'
    r'(?:\s+\((?P<district_paren>[A-Z][A-Za-z.-]*(?:\s+[A-Z][A-Za-z.-]*)*)\))?,\s+'
    r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec|January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}:',
    re.IGNORECASE,
)
DATELINE_DISTRICT_INLINE_PATTERN = re.compile(
    r'\b(?:By\s+[A-Z][A-Za-z.\s-]+\s+)?(?P<primary>[A-Z][A-Za-z.-]*(?:\s+[A-Z][A-Za-z.-]*)*)'
    r'(?:\s+\((?P<district_paren>[A-Z][A-Za-z.-]*(?:\s+[A-Z][A-Za-z.-]*)*)\))?,\s+'
    r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec|January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}:',
    re.IGNORECASE,
)
ROUTE_DESTINATION_PATTERN = re.compile(
    r'(?:passengers\s+going\s+to|leaving|heading\s+to|travelling\s+to\s+and\s+from|vehicles\s+to\s+and\s+from)\s+(.{0,120})',
    re.IGNORECASE,
)

GazetteerFunc = Callable[[str], str | None]

NUMBER_WORDS = {
    'one': 1,
    'two': 2,
    'three': 3,
    'four': 4,
    'five': 5,
    'six': 6,
    'seven': 7,
    'eight': 8,
    'nine': 9,
    'ten': 10,
    'eleven': 11,
    'twelve': 12,
    'thirteen': 13,
    'fourteen': 14,
    'fifteen': 15,
    'sixteen': 16,
    'seventeen': 17,
    'eighteen': 18,
    'nineteen': 19,
    'twenty': 20,
}


def extract_en(
    title: str | None,
    text: str,
    published_date_ad: str | None,
    gazetteer: dict[str, GazetteerFunc] | None,
    keywords_cfg: dict[str, Any] | None,
    *,
    published_year_hint: int | None = None,
) -> dict[str, Any]:
    """Extract structured event fields from an English article."""

    title = _normalize_source_title((title or '').strip())
    text = _trim_source_text(text.strip())
    if title and text.casefold().startswith(title.casefold()):
        combined = text.strip()
    else:
        combined = '\n'.join(part for part in (title, text) if part).strip()
    gazetteer = gazetteer or {}
    keyword_bundle = _normalize_keywords_cfg(keywords_cfg or {})

    district_normalizer = gazetteer.get('normalize_district', _normalize_district_en)
    municipality_normalizer = gazetteer.get('normalize_municipality', _normalize_municipality_en)
    municipality_mapper = gazetteer.get('municipality_to_district', municipality_to_district)
    province_mapper = gazetteer.get('district_to_province', district_to_province)

    place = extract_place_en(combined)
    explicit_district = _find_explicit_district(combined, district_normalizer)
    municipality = _resolve_municipality(place, municipality_normalizer)
    if municipality is None:
        municipality = _find_explicit_municipality(combined, municipality_normalizer)
    district = explicit_district
    conf_district = 0.0
    place_admin_level = place.place_admin_level
    ward = _normalize_ward(place.ward)
    road_disruption_title = _is_road_disruption_title(title)

    if explicit_district is not None:
        municipality = _resolve_municipality_for_district(
            combined,
            place,
            municipality,
            explicit_district,
            municipality_normalizer,
            municipality_mapper,
            road_disruption_title=road_disruption_title,
        )
        if municipality is None and place_admin_level == 'municipality':
            place_admin_level = 'district'

    if district is not None and municipality is None and explicit_district is None and road_disruption_title:
        route_match = ROUTE_DESTINATION_PATTERN.search(combined)
        if route_match is not None and district.casefold() in route_match.group(1).casefold():
            district = None
            conf_district = 0.0

    if explicit_district is not None and municipality is not None:
        mapped_district = municipality_mapper(municipality)
        if mapped_district is not None and mapped_district != explicit_district and mapped_district.casefold() in _lead_search_text(combined).casefold():
            explicit_district = mapped_district
            conf_district = max(conf_district, 0.88)
            if place_admin_level == 'district':
                place_admin_level = 'municipality' if not ward else 'ward'

    if explicit_district is not None:
        district = explicit_district
        conf_district = 0.95
        if place_admin_level != 'district':
            place_admin_level = 'district'
    elif municipality is not None:
        district = municipality_mapper(municipality)
        if district is not None:
            conf_district = 0.82
        if ward and place_admin_level != 'district':
            place_admin_level = 'ward'
        elif place_admin_level == 'unknown':
            place_admin_level = 'municipality'
    elif ward:
        place_admin_level = 'ward'

    event_date_ad, conf_date = _resolve_event_date(combined, published_date_ad, published_year_hint)
    deaths, missing, injured, conf_fatalities = _extract_casualties(combined, keyword_bundle['casualty_terms'])
    trigger, conf_trigger = _extract_trigger(combined, keyword_bundle['trigger_terms'])
    if trigger == 'unknown' and _is_road_disruption_title(title) and _has_lead_road_rainfall_context(combined):
        trigger, conf_trigger = 'rainfall', max(conf_trigger, 0.78)
    event_class, conf_class = _classify_event(
        title=title,
        combined=combined,
        district=district,
        conf_date=conf_date,
        deaths=deaths,
        missing=missing,
        injured=injured,
        landslide_terms=keyword_bundle['landslide_terms'],
        exclude_terms=keyword_bundle['exclude_terms'],
    )
    if event_class == 2 and district and event_date_ad and not _is_cumulative_toll_update(title, combined) and _has_direct_human_impact(
        deaths,
        missing,
        injured,
        title,
        combined,
    ):
        event_class, conf_class = 1, max(conf_class, 0.82)

    province = province_mapper(district) if district else None
    return {
        'class': event_class,
        'event_date_ad': event_date_ad,
        'district': district,
        'province': province,
        'deaths': deaths,
        'missing': missing,
        'injured': injured,
        'trigger': trigger,
        'municipality': municipality,
        'ward': ward,
        'place_admin_level': place_admin_level,
        'place_name_raw': place.place_name_raw,
        'place_candidates_json': place.place_candidates_json,
        'conf_place': place.conf_place,
        'conf_class': conf_class,
        'conf_date': conf_date,
        'conf_district': conf_district,
        'conf_fatalities': conf_fatalities,
        'conf_trigger': conf_trigger,
    }


def _normalize_source_title(title: str) -> str:
    return MYREPUBLICA_TITLE_SUFFIX_PATTERN.sub('', title).strip()



def _trim_source_text(text: str) -> str:
    if not text:
        return ''
    lead_match = MYREPUBLICA_LEAD_PATTERN.search(text)
    if lead_match is None:
        lead_match = MYREPUBLICA_DATELINE_PATTERN.search(text)
    if lead_match is not None:
        prefix = text[:lead_match.start()].strip()
        if prefix and MYREPUBLICA_PREAMBLE_IMPACT_PATTERN.search(prefix) is not None:
            impact_lines = [line.strip() for line in prefix.splitlines() if MYREPUBLICA_PREAMBLE_IMPACT_PATTERN.search(line)]
            preserved = ' '.join(impact_lines[-2:]).strip()
            if preserved:
                return f"{preserved}\n{text[lead_match.start():].lstrip()}"
        return text[lead_match.start():].lstrip()
    return text



def _normalize_keywords_cfg(keywords_cfg: dict[str, Any]) -> dict[str, Any]:
    landslide_terms = [str(term).casefold() for term in keywords_cfg.get('terms', {}).get('en', ['landslide'])]
    exclude_terms = [str(term).casefold() for term in keywords_cfg.get('exclude', {}).get('en', [])]
    trigger_terms = {
        label: [str(term).casefold() for term in values.get('en', [])]
        for label, values in dict(keywords_cfg.get('trigger_terms', {})).items()
    }
    casualty_terms = {
        label: [str(term).casefold() for term in values.get('en', [])]
        for label, values in dict(keywords_cfg.get('casualty_terms', {})).items()
    }
    casualty_terms.setdefault('deaths', [])
    casualty_terms['deaths'] = list(dict.fromkeys(casualty_terms['deaths'] + [
        'died', 'die', 'buried to death', 'death', 'killed',
        'lost their lives', 'lost his life', 'lost her life', 'lost their life',
    ]))
    casualty_terms.setdefault('missing', [])
    casualty_terms['missing'] = list(dict.fromkeys(casualty_terms['missing'] + ['go missing', 'went missing', 'gone missing']))
    return {
        'landslide_terms': landslide_terms,
        'exclude_terms': exclude_terms,
        'trigger_terms': trigger_terms,
        'casualty_terms': casualty_terms,
    }


def _normalize_district_en(name: str) -> str | None:
    return normalize_district(name, 'en')


def _normalize_municipality_en(name: str) -> str | None:
    return normalize_municipality(name, 'en')


def _find_explicit_district(text: str, district_normalizer: GazetteerFunc) -> str | None:
    lead_text = _lead_search_text(text)
    route_stripped_lead = _strip_route_destination_clause(lead_text)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    dateline_fallback: str | None = None
    for line in lines[:4]:
        for dateline_match in list(DATELINE_DISTRICT_PATTERN.finditer(line)) + list(DATELINE_DISTRICT_INLINE_PATTERN.finditer(line)):
            district_candidates = [
                _normalize_dateline_district_candidate(dateline_match.group('district_paren'), district_normalizer),
                _normalize_dateline_district_candidate(dateline_match.group('primary'), district_normalizer),
            ]
            for normalized in district_candidates:
                if normalized is None:
                    continue
                if normalized == 'Kathmandu':
                    dateline_fallback = normalized
                    continue
                return normalized
    district_pattern = re.compile(r'\b([A-Z][A-Za-z.-]*(?:\s+[A-Z][A-Za-z.-]*)*)\s+District\b')
    for match in district_pattern.finditer(route_stripped_lead):
        normalized = district_normalizer(match.group(1))
        if normalized is not None:
            return normalized
    for match in EN_DISTRICT_ALIASES_PATTERN.finditer(route_stripped_lead):
        normalized = district_normalizer(match.group(0))
        if normalized is None:
            continue
        if normalized == 'Kathmandu' and dateline_fallback is not None:
            continue
        return normalized
    token_pattern = re.compile(r'\b[A-Z][A-Za-z.-]*(?:\s+[A-Z][A-Za-z.-]*)*\b')
    for line in lines[:6] or [route_stripped_lead]:
        for token in token_pattern.findall(line):
            normalized = district_normalizer(token)
            if normalized is None:
                continue
            if normalized == 'Kathmandu' and dateline_fallback is not None:
                continue
            return normalized
    return dateline_fallback


def _normalize_dateline_district_candidate(candidate: str | None, district_normalizer: GazetteerFunc) -> str | None:
    if not candidate:
        return None
    normalized = district_normalizer(candidate)
    if normalized is not None:
        return normalized
    parts = candidate.split()
    for start in range(1, len(parts)):
        normalized = district_normalizer(' '.join(parts[start:]))
        if normalized is not None:
            return normalized
    return None


def _strip_route_destination_clause(text: str) -> str:
    return ROUTE_DESTINATION_PATTERN.sub('', text)


def _resolve_municipality(place: Any, municipality_normalizer: GazetteerFunc) -> str | None:
    if place.municipality:
        return place.municipality
    candidates = []
    if place.place_name_raw:
        candidates.append(place.place_name_raw)
    try:
        candidates.extend(json.loads(place.place_candidates_json))
    except Exception:
        pass
    seen: set[str] = set()
    for candidate in candidates:
        if not isinstance(candidate, str):
            continue
        key = candidate.casefold().strip()
        if not key or key in seen:
            continue
        seen.add(key)
        municipality = municipality_normalizer(candidate)
        if municipality is not None:
            return municipality
    return None


def _resolve_municipality_for_district(
    text: str,
    place: Any,
    municipality: str | None,
    district: str,
    municipality_normalizer: GazetteerFunc,
    municipality_mapper: GazetteerFunc,
    *,
    road_disruption_title: bool,
) -> str | None:
    candidates: list[str] = []
    if municipality is not None:
        candidates.append(municipality)
    if place.place_name_raw:
        candidates.append(place.place_name_raw)
    try:
        candidates.extend(json.loads(place.place_candidates_json))
    except Exception:
        pass
    for match in MUNICIPALITY_PATTERN.finditer(_lead_search_text(text)):
        candidates.append(match.group(0).rsplit('-', 1)[0].strip().title())

    matches: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if not isinstance(candidate, str):
            continue
        normalized = municipality_normalizer(candidate)
        if normalized is None or municipality_mapper(normalized) != district or normalized in seen:
            continue
        seen.add(normalized)
        matches.append(normalized)

    if not matches:
        if municipality is not None:
            mapped = municipality_mapper(municipality)
            if mapped is not None and mapped != district and mapped.casefold() in _lead_search_text(text).casefold():
                if road_disruption_title:
                    return None
                return municipality
        return None
    if road_disruption_title and len(matches) > 1:
        return None
    return matches[0]


def _find_explicit_municipality(text: str, municipality_normalizer: GazetteerFunc) -> str | None:
    lead_text = _lead_search_text(text)
    split_ward_match = re.search(
        r'\b([A-Z][A-Za-z.-]*(?:\s+[A-Z][A-Za-z.-]*){0,2})\s*,\s*([A-Z][A-Za-z.-]*(?:\s+[A-Z][A-Za-z.-]*){0,2})\s*[–—-]\s*\d+\b',
        lead_text,
    )
    if split_ward_match is not None:
        merged_base = f"{split_ward_match.group(1).strip().title()} {split_ward_match.group(2).strip().title()}"
        for suffix in ('Rural Municipality', 'Municipality'):
            normalized = municipality_normalizer(f"{merged_base} {suffix}")
            if normalized is not None:
                return normalized
    for match in MUNICIPALITY_PATTERN.finditer(lead_text):
        candidate = match.group(0).rsplit('-', 1)[0].strip().title()
        normalized = municipality_normalizer(candidate)
        if normalized is not None:
            return normalized
    for match in WARD_MUNICIPALITY_PATTERN.finditer(lead_text):
        normalized = municipality_normalizer(match.group(1).title())
        if normalized is not None:
            return normalized
    return None


def _normalize_ward(value: str | None) -> str | None:
    if not value:
        return None
    match = WARD_PATTERN.search(value)
    if not match:
        return value
    return f'Ward {match.group(1)}'


def _resolve_event_date(
    text: str,
    published_date_ad: str | None,
    published_year_hint: int | None,
) -> tuple[str | None, float]:
    lead_window = _lead_window(text, limit=900)
    anchor_value, anchor_conf = _extract_absolute_anchor_date(lead_window, published_date_ad, published_year_hint)
    if anchor_value is None and published_date_ad:
        anchor_value, anchor_conf = published_date_ad, 0.6
    if anchor_value is None:
        return None, 0.0
    try:
        anchor_date = date.fromisoformat(anchor_value)
    except ValueError:
        return None, 0.0

    if SAME_DAY_PATTERN.search(lead_window):
        return anchor_date.isoformat(), max(anchor_conf, 0.8)
    if PREVIOUS_DAY_PATTERN.search(lead_window):
        return (anchor_date - timedelta(days=1)).isoformat(), max(anchor_conf, 0.82)

    ongoing_weekday = ONGOING_WEEKDAY_PATTERN.search(lead_window)
    if ongoing_weekday is not None:
        event_start_match = ONGOING_WEEKDAY_EVENT_START_PATTERN.search(lead_window)
        weekday_target = (event_start_match or ongoing_weekday).group(1)
        if event_start_match is not None or _should_backshift_ongoing_rain_context(lead_window):
            inferred = _infer_weekday_date(anchor_date, weekday_target)
            if inferred is not None:
                return inferred.isoformat(), max(anchor_conf, 0.78)
        return anchor_date.isoformat(), max(anchor_conf, 0.74)

    weekday_name = _event_weekday_name(lead_window)
    if weekday_name:
        inferred = _infer_weekday_date(anchor_date, weekday_name)
        if inferred is not None:
            return inferred.isoformat(), max(anchor_conf, 0.78)
    return anchor_date.isoformat(), anchor_conf


def _extract_casualties(text: str, casualty_terms: dict[str, list[str]]) -> tuple[int | None, int | None, int | None, float]:
    lowered = text.casefold()
    values = {
        'deaths': None,
        'missing': None,
        'injured': None,
    }
    confidence = 0.0
    for label in ('deaths', 'missing', 'injured'):
        terms = [re.escape(term) for term in casualty_terms.get(label, []) if term]
        if not terms:
            continue
        term_group = '|'.join(terms)
        patterns = (
            re.compile(rf'\b(?P<qual>at least|more than|over|around|about|approximately|feared)?\s*(?P<num>\d+|[A-Za-z-]+)\s+(?:(?:other|others|additional|more)\s+)?(?:(?:people|persons?|others)\s+)?(?:(?:have|has|had|were|was|are|remain|remained|still)\s+)?(?:{term_group})\b', re.IGNORECASE),
            re.compile(rf'\b(?:{term_group})\b(?:\s+(?:is|was|were|has|have|had|stood\s+at|reached|reported\s+at))?(?:\s+(?:at\s+least|more\s+than|over|around|about|approximately))?\s*(?:[:=-]\s*)?(?P<num>\d+|[A-Za-z-]+)\b(?:\s+(?:people|persons?|others))?', re.IGNORECASE),
        )
        best_value = None
        best_conf = 0.0
        for pattern in patterns:
            for match in pattern.finditer(text):
                value = _parse_count(match.group('num'))
                if value is None:
                    continue
                qualifier = match.groupdict().get('qual') or ''
                current_conf = 0.75 if qualifier else 0.92
                if best_value is None or value > best_value:
                    best_value = value
                    best_conf = current_conf
        values[label] = best_value
        confidence = max(confidence, best_conf)
    if not any(value is not None for value in values.values()):
        confidence = 0.0
    if values['deaths'] is None:
        recovered_bodies_match = re.search(
            r'\b(?:the\s+)?bodies\s+of\s+(?P<num>\d+|[A-Za-z-]+)\s+'
            r'(?:persons?|people|individuals?)(?:\s+missing)?(?:\s+under\s+the\s+landslide\s+debris)?\s+'
            r'(?:at\s+[^.]{0,80}\s+)?(?:have\s+been|were)\s+recovered\b'
            r'|\b(?P<num2>\d+|[A-Za-z-]+)\s+bodies\s+(?:were|have\s+been)\s+recovered\b',
            text,
            re.IGNORECASE,
        )
        if recovered_bodies_match is not None:
            recovered_count = _parse_count(recovered_bodies_match.group('num') or recovered_bodies_match.group('num2') or '')
            if recovered_count is not None:
                values['deaths'] = recovered_count
                confidence = max(confidence, 0.82)
    if values['deaths'] is None:
        claimed_life_match = re.search(
            r'\bclaimed?\s+one\s+life\b'
            r'|\bclaimed?\s+the\s+life\s+of\b',
            text,
            re.IGNORECASE,
        )
        if claimed_life_match is not None:
            values['deaths'] = 1
            confidence = max(confidence, 0.74)
    if values['deaths'] is None:
        family_pair_dead = re.search(
            r'\b[A-Z][A-Za-z.-]+(?:\s+[A-Z][A-Za-z.-]+)*\s+and\s+(?:his|her|their)\s+'
            r'(?:son|daughter|wife|husband|mother|father|brother|sister)\s+were\s+found\s+dead\b',
            text,
            re.IGNORECASE,
        )
        if family_pair_dead is not None:
            values['deaths'] = 2
            confidence = max(confidence, 0.72)
    if values['deaths'] is None:
        singular_death_match = re.search(
            r'\b(?:a|one)\s+'
            r'(?:person|woman|man|worker|labou?rer|child|youth|motorcyclist|driver|passenger)\s+'
            r'(?:(?:has|had)\s+)?(?:died|was\s+killed|was\s+buried\s+to\s+death)\b'
            r'|\b(?:one)\s+(?:dies|died|was\s+killed)\b'
            r'|\broad worker buried to death\b',
            text,
            re.IGNORECASE,
        )
        if singular_death_match is not None:
            values['deaths'] = 1
            confidence = max(confidence, 0.76)
    return values['deaths'], values['missing'], values['injured'], confidence


def _extract_trigger(text: str, trigger_terms: dict[str, list[str]]) -> tuple[str, float]:
    lowered = text.casefold()
    if _contains_any(lowered, trigger_terms.get('earthquake', [])):
        return 'earthquake', 0.95
    if _has_anthropogenic_trigger(lowered, trigger_terms.get('road_construction', [])):
        return 'anthropogenic', 0.88
    if _has_rainfall_trigger(text, lowered, trigger_terms.get('rainfall', [])):
        return 'rainfall', 0.9
    return 'unknown', 0.3


def _should_backshift_ongoing_rain_context(lead_window: str) -> bool:
    sentences = [sentence.strip() for sentence in re.split(r'(?<=[.!?])\s+', lead_window) if sentence.strip()]
    for index, sentence in enumerate(sentences[1:], start=1):
        weekday_match = ONGOING_WEEKDAY_PATTERN.search(sentence)
        if weekday_match is None:
            continue
        sentence_cf = sentence.casefold()
        if not sentence_cf.startswith('it has been raining since'):
            continue
        previous = sentences[index - 1].casefold()
        if any(term in previous for term in ('landslide', 'landslides', 'mudslide', 'rockfall')) and any(term in previous for term in ('triggered by', 'following', 'due to', 'caused by')) and any(term in previous for term in ('rain', 'rainfall', 'rains', 'downpour')):
            return True
    return False


def _has_flood_companion_trigger(window_casefold: str) -> bool:
    return (
        'meanwhile' not in window_casefold
        and any(term in window_casefold for term in ('landslide', 'landslides', 'mudslide', 'mudslides', 'rockfall', 'rockfalls'))
        and any(term in window_casefold for term in ('flood', 'floods', 'inundation'))
    )


def _is_road_disruption_sentence(sentence_casefold: str) -> bool:
    return any(term in sentence_casefold for term in ('road', 'highway', 'corridor', 'road section')) and any(
        term in sentence_casefold for term in ('blocked', 'obstructed', 'disrupted', 'impassable')
    )


def _has_rainfall_trigger(text: str, text_casefold: str, terms: list[str]) -> bool:
    rainfall_terms = list(dict.fromkeys(list(terms) + ['rain', 'rains', 'rainfall', 'downpour']))
    if (
        not _contains_any(text_casefold, rainfall_terms)
        and RAINFALL_SIGNAL_PATTERN.search(text) is None
        and not _has_flood_companion_trigger(_lead_window(text, limit=900).casefold())
    ):
        return False
    sentences = [sentence for sentence in re.split(r'(?<=[.!?])\s+', text) if sentence]
    for index, sentence in enumerate(sentences):
        sentence_cf = sentence.casefold()
        if 'landslide' not in sentence_cf and 'mudslide' not in sentence_cf and 'rockfall' not in sentence_cf:
            continue
        if RAINFALL_CAUSAL_PATTERN.search(sentence) is not None:
            return True
        next_sentence_cf = sentences[index + 1].casefold() if index + 1 < len(sentences) else ''
        local_window = ' '.join(sentences[index:index + 2]).casefold()
        if _is_road_disruption_sentence(sentence_cf) and RAINFALL_CAUSAL_PATTERN.search(sentence) is None:
            continue
        phrase_hits = [
            phrase for phrase in (
                'heavy rainfall', 'continuous rainfall', 'incessant rainfall', 'incessant rains', 'torrential rain',
                'triggered by rains', 'along with a heavy rainfall', 'following continuous rainfall', 'due to the rains',
            ) if phrase in local_window
        ]
        if phrase_hits:
            if SEARCH_CONTEXT_PATTERN.search(local_window) is None and 'meanwhile' not in local_window:
                if any(phrase in sentence_cf for phrase in phrase_hits):
                    return True
                if next_sentence_cf and any(phrase in next_sentence_cf for phrase in phrase_hits):
                    if any(term in next_sentence_cf for term in ('landslide', 'landslides', 'flood', 'floods', 'inundation')):
                        return True
                    if any(term in sentence_cf for term in ('killed', 'dead', 'died', 'missing', 'injured', 'buried', 'swept away')):
                        return True
        if _has_flood_companion_trigger(local_window):
            return True
    lead_window = _lead_window(text, limit=900).casefold()
    if _has_flood_companion_trigger(lead_window):
        return True
    return False


def _classify_event(
    *,
    title: str | None,
    combined: str,
    district: str | None,
    conf_date: float,
    deaths: int | None,
    missing: int | None,
    injured: int | None,
    landslide_terms: list[str],
    exclude_terms: list[str],
) -> tuple[int, float]:
    lowered = combined.casefold()
    title_cf = (title or '').casefold()
    has_landslide = _contains_any(lowered, landslide_terms)
    if _contains_any(lowered, exclude_terms):
        return 3, 0.95
    if not has_landslide:
        return 3, 0.9
    has_human_impact = any(value is not None and int(value) > 0 for value in (deaths, missing, injured))
    road_disruption = any(term in title_cf for term in ('road', 'highway', 'corridor')) and any(
        term in title_cf for term in ('block', 'blocks', 'blocked', 'obstruct', 'obstructed', 'disrupt', 'disrupts', 'disrupted', 'disturb', 'disturbs', 'disturbed')
    )
    cumulative_toll_update = _is_cumulative_toll_update(title, combined)
    if cumulative_toll_update:
        return 2, 0.86
    if road_disruption and not has_human_impact:
        return 2, 0.84
    if not has_human_impact and title and RISK_TITLE_PATTERN.search(title):
        return 2, 0.82
    if district is not None and conf_date >= 0.75:
        return 1, 0.92
    return 2, 0.8




def _is_cumulative_toll_update(title: str | None, combined: str) -> bool:
    title_cf = (title or '').casefold()
    lowered = combined.casefold()
    return 'death toll' in title_cf or ('death toll' in lowered and any(term in lowered for term in ('climbed to', 'reaches', 'reached')))

def _has_direct_human_impact(
    deaths: int | None,
    missing: int | None,
    injured: int | None,
    title: str | None,
    combined: str,
) -> bool:
    if deaths is not None and int(deaths) > 0:
        return True
    if missing is not None and int(missing) > 0:
        return True
    if injured is not None and int(injured) >= 2:
        return True
    title_text = (title or '').strip()
    if title_text and DIRECT_EVENT_TITLE_PATTERN.search(title_text):
        return True
    return False




def _has_lead_road_rainfall_context(text: str) -> bool:
    lead = _lead_window(text, limit=900)
    sentences = [s for s in re.split(r'(?<=[.!?])\s+', lead) if s]
    first_sentences = sentences[:6]
    has_landslide_sentence = any(any(term in s.casefold() for term in ('landslide', 'landslides', 'mudslide', 'rockfall')) for s in first_sentences)
    has_rain_sentence = any(RAINFALL_SIGNAL_PATTERN.search(s) is not None for s in first_sentences)
    return has_landslide_sentence and has_rain_sentence


def _event_weekday_name(text: str) -> str | None:
    for sentence in re.split(r'(?<=[.!?])\s+', text):
        match = WEEKDAY_PATTERN.search(sentence)
        if match is None:
            continue
        sentence_cf = sentence.casefold()
        if any(term in sentence_cf for term in ('landslide', 'landslides', 'mudslide', 'rockfall', 'buried', 'killed', 'dead', 'missing', 'injured', 'occurred')):
            return match.group(1)
    return None


def _infer_weekday_date(published: date, weekday_name: str) -> date | None:
    target = WEEKDAY_INDEX.get(weekday_name.casefold())
    if target is None:
        return None
    delta = (published.weekday() - target) % 7
    return published - timedelta(days=delta)


def _has_anthropogenic_trigger(text_casefold: str, terms: list[str]) -> bool:
    if not _contains_any(text_casefold, terms):
        return False
    return any(phrase in text_casefold for phrase in (
        'road expansion', 'road widening', 'during construction', 'under construction',
        'construction work', 'while digging', 'digging soil', 'soil digging',
        'excavation', 'excavating', 'while plastering', 'plotting', 'dumped soil',
        'working for the construction', 'constructing the road', 'road construction taskforce',
    ))


def _contains_any(text: str, terms: list[str]) -> bool:
    return any(term and term in text for term in terms)


def _parse_count(raw_value: str) -> int | None:
    value = raw_value.strip().casefold()
    if value.isdigit():
        return int(value)
    return NUMBER_WORDS.get(value)


def _is_road_disruption_title(title: str | None) -> bool:
    title_cf = (title or '').casefold()
    return any(term in title_cf for term in ('road', 'highway', 'corridor')) and any(
        term in title_cf for term in ('block', 'blocks', 'blocked', 'obstruct', 'obstructed', 'disrupt', 'disrupts', 'disrupted', 'disturb', 'disturbs', 'disturbed')
    )


def _lead_search_text(text: str, limit: int = 900) -> str:
    stripped = text.strip()
    return stripped[:limit]


def _lead_window(text: str, limit: int = 420) -> str:
    """Use the title and first few body sentences for date inference."""

    stripped = text.strip()
    if not stripped:
        return ''
    parts = [part.strip() for part in stripped.splitlines() if part.strip()]
    if not parts:
        return ''
    title = parts[0]
    body = ' '.join(parts[1:5])
    body_sentences = re.split(r'(?<=[.!?])\s+', body) if body else []
    lead_body = ' '.join(body_sentences[:5])
    lead = ' '.join(part for part in (title, lead_body) if part)
    return lead[:limit]


def _extract_absolute_anchor_date(
    text: str,
    published_date_ad: str | None,
    published_year_hint: int | None,
) -> tuple[str | None, float]:
    for pattern, fmt in DATE_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        value = ' '.join(part.strip(',') for part in match.groups())
        try:
            return datetime.strptime(value, fmt).date().isoformat(), 0.95
        except ValueError:
            continue
    inferred_year = published_year_hint
    if inferred_year is None and published_date_ad:
        try:
            inferred_year = date.fromisoformat(published_date_ad).year
        except ValueError:
            inferred_year = None
    month_day_match = MONTH_DAY_NO_YEAR_PATTERN.search(text)
    if month_day_match and inferred_year is not None:
        value = f'{month_day_match.group(1)} {int(month_day_match.group(2))} {inferred_year}'
        for fmt in ('%B %d %Y', '%b %d %Y'):
            try:
                return datetime.strptime(value, fmt).date().isoformat(), 0.88
            except ValueError:
                continue
    return None, 0.0
