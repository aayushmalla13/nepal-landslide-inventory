"""Nepali event extraction helpers."""

from __future__ import annotations

import json
import re
from datetime import date, timedelta
from typing import Any, Callable

from ..gazetteer import district_to_province, normalize_district
from ..nlp_attribution import is_person_attribution
from ..nlp_counts import (
    NEPALI_BODY_RECOVERY_VERBS,
    NEPALI_NUMBER_ALTERNATION,
    NEPALI_PERSON_NOUN_ALTERNATION,
    explicit_zero_is_safe,
    parse_nepali_number,
)
from ..gazetteer_municipality import municipality_to_district, normalize_municipality
from ..preprocess.dates import bs_to_ad, detect_bs_date, devanagari_to_ascii_digits
from .places import extract_place_np

NP_WARD_CAPTURE_PATTERN = re.compile(r'(?:वडा\s*नं\.?\s*([०-९0-9]+)|([०-९0-9]+)\s*वडा)')
NP_DISTRICT_PATTERN = re.compile(r'((?:[ऀ-ॿ]+(?:\s+[ऀ-ॿ]+){0,2}))\s+जिल्ला')
NP_MUNICIPALITY_PATTERN = re.compile(
    r'([ऀ-ॿ]+(?:\s+[ऀ-ॿ]+){0,3}\s*(?:महानगरपालिका|उपमहानगरपालिका|नगरपालिका|गाउँपालिका))(?:\s*[–—-]?\s*[०-९0-9]+)?'
)
NP_WARD_MUNICIPALITY_PATTERN = re.compile(r'([ऀ-ॿ]+(?:\s+[ऀ-ॿ]+){0,2})\s*[–—-]\s*[०-९0-9]+')
NP_POSTPOSITION_SUFFIXES = ('मा', 'को', 'का', 'ले', 'बाट', 'देखि', 'सम्म', 'सँग')
GazetteerFunc = Callable[[str], str | None]
NP_DIRECT_EVENT_TITLE_PATTERN = re.compile(
    r'(?:पहिरो|भूस्खलन|ढिस्को).{0,80}(?:मृत्यु|मृत|बेपत्ता|घाइते|पुरियो|बगायो|अवरुद्ध)|'
    r'(?:मृत्यु|मृत|बेपत्ता|घाइते|पुरियो|बगायो|अवरुद्ध).{0,80}(?:पहिरो|भूस्खलन|ढिस्को)',
)
NP_PREVIOUS_DAY_PATTERN = re.compile(r'(?:गएराति(?!देखि)|गए राति(?!देखि)|हिजो|अघिल्लो राति)')
NP_PREVIOUS_EVENT_SINCE_PATTERN = re.compile(r'(?:गएरातिदेखि|गए रातिदेखि)[^.]{0,100}(?:अवरुद्ध|बन्द|ठप्प|सञ्चालनमा रोक|सवारी अलपत्र)')
NP_SAME_DAY_PATTERN = re.compile(r'(?:आज|आज बिहान|आज दिउँसो|आज राति)')
NP_WEEKDAY_NAMES = ('सोमबार', 'मंगलबार', 'मङ्गलबार', 'बुधबार', 'बुधवार', 'बिहीबार', 'बिहिबार', 'शुक्रबार', 'शनिबार', 'शनिवार', 'आइतबार', 'आइतवार')
NP_WEEKDAY_INDEX = {name: idx for idx, name in enumerate(('सोमबार', 'मंगलबार', 'बुधबार', 'बिहीबार', 'शुक्रबार', 'शनिबार', 'आइतबार'))}
NP_WEEKDAY_INDEX.update({
    'मङ्गलबार': NP_WEEKDAY_INDEX['मंगलबार'],
    'बुधवार': NP_WEEKDAY_INDEX['बुधबार'],
    'बिहिबार': NP_WEEKDAY_INDEX['बिहीबार'],
    'शनिवार': NP_WEEKDAY_INDEX['शनिबार'],
    'आइतवार': NP_WEEKDAY_INDEX['आइतबार'],
})
NP_WEEKDAY_PATTERN = re.compile(r'(सोमबार|मंगलबार|मङ्गलबार|बुधबार|बुधवार|बिहीबार|बिहिबार|शुक्रबार|शनिबार|शनिवार|आइतबार|आइतवार)(?:\s*(?:बिहान|दिउँसो|बेलुकी|बेलुका|राति))?')
NP_EXPLICIT_TIME_PATTERN = re.compile(
    r'(?:(?:बिहान|दिउँसो|बेलुकी|बेलुका|राति)\s*(?:करिब|करीब|साढे)?\s*[०-९0-9]{1,2}(?:\s*[:ः]\s*[०-९0-9]{1,2})?\s*बजे(?:तिर|देखि(?:नै)?|सम्म)?|'
    r'(?:साढे\s*)?[०-९0-9]{1,2}(?:\s*[:ः]\s*[०-९0-9]{1,2})?\s*बजे(?:तिर|देखि(?:नै)?|सम्म)?)'
)
NP_FOLLOWUP_TITLE_PATTERN = re.compile(r'(अघि|नियन्त्रण|राहत|सहयोग|अस्थायी आवास|शव फेला|उपचार|पुनःस्थापन|वितरण)')
NP_DAY_MONTH_NO_YEAR_PATTERN = re.compile(
    r'(?<!\d)([०-९0-9]{1,2})\s*(बैशाख|वैशाख|जेठ|असार|साउन|भदौ|असोज|कात्तिक|कार्तिक|मंसिर|पुष|पुस|माघ|फागुन|चैत)(?=(?:,|\s|$))'
)
NP_MONTH_DAY_NO_YEAR_PATTERN = re.compile(
    r'(बैशाख|वैशाख|जेठ|असार|साउन|भदौ|असोज|कात्तिक|कार्तिक|मंसिर|पुष|पुस|माघ|फागुन|चैत)\s*([०-९0-9]{1,2})(?:\s*गते)?'
)


def extract_np(
    title: str | None,
    text: str,
    published_date_ad: str | None,
    gazetteer: dict[str, GazetteerFunc] | None,
    keywords_cfg: dict[str, Any] | None,
    *,
    published_year_hint: int | None = None,
) -> dict[str, Any]:
    """Extract structured event fields from a Nepali article."""

    title = (title or '').strip()
    text = text.strip()
    combined = '\n'.join(part for part in (title, text) if part).strip()
    gazetteer = gazetteer or {}
    keyword_bundle = _normalize_keywords_cfg(keywords_cfg or {})

    district_normalizer = gazetteer.get('normalize_district', _normalize_district_np)
    municipality_normalizer = gazetteer.get('normalize_municipality', _normalize_municipality_np)
    municipality_mapper = gazetteer.get('municipality_to_district', municipality_to_district)
    province_mapper = gazetteer.get('district_to_province', district_to_province)

    place = extract_place_np(combined)
    explicit_district = _find_explicit_district_np(combined, district_normalizer)
    municipality = _resolve_municipality(place, municipality_normalizer)
    if municipality is None:
        municipality = _find_explicit_municipality_np(combined, municipality_normalizer)
    district = explicit_district
    conf_district = 0.0
    place_admin_level = place.place_admin_level
    ward = _normalize_ward_np(place.ward or place.place_name_raw)

    if explicit_district is not None:
        district = explicit_district
        conf_district = 0.95
        place_admin_level = 'district'
    if district is not None:
        municipality = _resolve_municipality_for_district(
            combined,
            place,
            municipality,
            district,
            municipality_normalizer,
            municipality_mapper,
        )
    if explicit_district is None and municipality is not None:
        district = municipality_mapper(municipality)
        if district is not None:
            conf_district = 0.82
        if ward:
            place_admin_level = 'ward'
        elif place_admin_level == 'unknown':
            place_admin_level = 'municipality'
    elif ward:
        place_admin_level = 'ward'

    event_date_ad, conf_date = _resolve_event_date(combined, published_date_ad, published_year_hint)
    deaths, missing, injured, conf_fatalities = _extract_casualties(combined, keyword_bundle['casualty_terms'])
    trigger, conf_trigger = _extract_trigger(combined, keyword_bundle['trigger_terms'])
    event_class, conf_class = _classify_event(
        combined=combined,
        district=district,
        conf_date=conf_date,
        landslide_terms=keyword_bundle['landslide_terms'],
        exclude_terms=keyword_bundle['exclude_terms'],
    )
    if event_class == 2 and district and event_date_ad and _has_direct_human_impact(
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


def _normalize_keywords_cfg(keywords_cfg: dict[str, Any]) -> dict[str, Any]:
    landslide_terms = [str(term) for term in keywords_cfg.get('terms', {}).get('np', ['पहिरो'])]
    exclude_terms = [str(term) for term in keywords_cfg.get('exclude', {}).get('np', [])]
    trigger_terms = {
        label: [str(term) for term in values.get('np', [])]
        for label, values in dict(keywords_cfg.get('trigger_terms', {})).items()
    }
    casualty_terms = {
        label: [str(term) for term in values.get('np', [])]
        for label, values in dict(keywords_cfg.get('casualty_terms', {})).items()
    }
    return {
        'landslide_terms': landslide_terms,
        'exclude_terms': exclude_terms,
        'trigger_terms': trigger_terms,
        'casualty_terms': casualty_terms,
    }


def _normalize_district_np(name: str) -> str | None:
    normalized = normalize_district(name, 'np')
    if normalized is not None:
        return normalized
    for suffix in NP_POSTPOSITION_SUFFIXES:
        if name.endswith(suffix) and len(name) > len(suffix) + 1:
            normalized = normalize_district(name[: -len(suffix)], 'np')
            if normalized is not None:
                return normalized
    return None


def _normalize_municipality_np(name: str) -> str | None:
    return normalize_municipality(name, 'np')


def _find_explicit_district_np(text: str, district_normalizer: GazetteerFunc) -> str | None:
    for match in NP_DISTRICT_PATTERN.finditer(text):
        normalized = district_normalizer(match.group(1))
        if normalized is None:
            continue
        # "सिन्धुपाल्चोक जिल्लाको मेलम्ची घर भएका चालक" names the driver's home,
        # not the landslide site. Skipping the attributed mention lets a later
        # "<X> जिल्ला" -- or the place extractor below -- supply the event
        # district instead of relocating the event to a victim's home.
        if is_person_attribution(text, match.start(1), match.end(1), 'np'):
            continue
        return normalized
    place = extract_place_np(text)
    if place.place_admin_level == 'district' and place.district is not None:
        if place.district == 'Kathmandu':
            for municipality_match in NP_MUNICIPALITY_PATTERN.finditer(_lead_window(text)):
                municipality = normalize_municipality(municipality_match.group(1), 'np')
                mapped_district = municipality_to_district(municipality) if municipality is not None else None
                if mapped_district and mapped_district != 'Kathmandu':
                    return mapped_district
        return place.district
    return None


def _find_explicit_municipality_np(text: str, municipality_normalizer: GazetteerFunc) -> str | None:
    lead_text = _lead_window(text)
    for match in NP_MUNICIPALITY_PATTERN.finditer(lead_text):
        normalized = municipality_normalizer(match.group(1))
        if normalized is not None:
            return normalized
    for match in NP_WARD_MUNICIPALITY_PATTERN.finditer(lead_text):
        normalized = municipality_normalizer(match.group(1))
        if normalized is not None:
            return normalized
    return None


def _resolve_municipality_for_district(
    text: str,
    place: Any,
    municipality: str | None,
    district: str,
    municipality_normalizer: GazetteerFunc,
    municipality_mapper: GazetteerFunc,
) -> str | None:
    if municipality is not None and municipality_mapper(municipality) == district:
        return municipality
    candidates: list[str] = []
    if place.place_name_raw:
        candidates.append(place.place_name_raw)
    try:
        candidates.extend(json.loads(place.place_candidates_json))
    except Exception:
        pass
    for match in NP_MUNICIPALITY_PATTERN.finditer(_lead_window(text)):
        candidates.append(match.group(1))
    seen: set[str] = set()
    for candidate in candidates:
        if not isinstance(candidate, str):
            continue
        key = candidate.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        normalized = municipality_normalizer(candidate)
        if normalized is not None and municipality_mapper(normalized) == district:
            return normalized
    return municipality if municipality is not None and municipality_mapper(municipality) == district else None


def _resolve_municipality(place: Any, municipality_normalizer: GazetteerFunc) -> str | None:
    if place.municipality:
        return place.municipality
    candidates: list[str] = []
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
        key = candidate.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        municipality = municipality_normalizer(candidate)
        if municipality is not None:
            return municipality
    return None


def _normalize_ward_np(value: str | None) -> str | None:
    if not value:
        return None
    match = NP_WARD_CAPTURE_PATTERN.search(value)
    if match is None:
        return None
    number = match.group(1) or match.group(2)
    return f'वडा {number}'


def _resolve_event_date(
    text: str,
    published_date_ad: str | None,
    published_year_hint: int | None,
) -> tuple[str | None, float]:
    lead_window = _lead_window(text, limit=1000)
    anchor_value, anchor_conf = _extract_explicit_anchor_date(lead_window, published_year_hint)
    if anchor_value is None and _should_search_full_text_for_anchor(text):
        anchor_value, anchor_conf = _extract_explicit_anchor_date(text, published_year_hint)
    if anchor_value is None and published_date_ad:
        anchor_value, anchor_conf = published_date_ad, 0.6
    if anchor_value is None:
        return None, 0.0
    try:
        anchor_date = date.fromisoformat(anchor_value)
    except ValueError:
        return None, 0.0

    same_day_match = NP_SAME_DAY_PATTERN.search(lead_window)
    previous_day_match = NP_PREVIOUS_DAY_PATTERN.search(lead_window)
    previous_event_since_match = NP_PREVIOUS_EVENT_SINCE_PATTERN.search(lead_window)
    direct_event_signal = NP_DIRECT_EVENT_TITLE_PATTERN.search(lead_window) is not None

    if same_day_match and (not previous_day_match or direct_event_signal):
        return anchor_date.isoformat(), max(anchor_conf, 0.8)
    if previous_day_match:
        return (anchor_date - timedelta(days=1)).isoformat(), max(anchor_conf, 0.82)
    if previous_event_since_match and direct_event_signal:
        return (anchor_date - timedelta(days=1)).isoformat(), max(anchor_conf, 0.78)
    if same_day_match:
        return anchor_date.isoformat(), max(anchor_conf, 0.8)

    weekday_match = NP_WEEKDAY_PATTERN.search(lead_window)
    if weekday_match and anchor_conf < 0.9:
        inferred = _infer_weekday_date(anchor_date, weekday_match.group(1))
        if inferred is not None:
            return inferred.isoformat(), max(anchor_conf, 0.78)

    explicit_time_match = NP_EXPLICIT_TIME_PATTERN.search(lead_window)
    if explicit_time_match and direct_event_signal and anchor_conf < 0.75:
        return anchor_date.isoformat(), 0.78
    return anchor_date.isoformat(), anchor_conf


# Context marking a number as a running total rather than this event's toll.
# Checked in a window around each candidate, so a legitimately late figure
# ("15 people were injured in the landslide") survives while a context figure
# ("90 have died nationwide since the monsoon began") does not.
AGGREGATE_CONTEXT_PATTERN = re.compile(
    r'nationwide|across the country|country-?wide|so far|since the (?:monsoon|onset|beginning)'
    r'|this (?:monsoon|year|season)|in the (?:past|last)\s+\w+\s+(?:years?|months?|weeks?)'
    r'|to date|cumulative|overall|in total|altogether|total of'
    r'|देशभर|देशैभरि|देशभरि|अहिलेसम्म|हालसम्म|यसवर्ष|यस वर्ष|यो मनसुन|कुल|जम्मा|यता',
    re.IGNORECASE,
)


def _is_aggregate_context(text: str, start: int, end: int, window: int = 90) -> bool:
    """Whether a numeric match sits in running-total context."""

    return AGGREGATE_CONTEXT_PATTERN.search(text[max(0, start - window):end + window]) is not None


# AGE VETO -- see the longer note in nlp_en/extract.py.
#
# The reverse casualty pattern here is deliberately loose::
#
#     (?:मृत्यु|मृत|...)[^0-9]{0,8}(?P<num>\d+)
#
# so any digit within eight characters of a death word is read as a toll. Nepali
# reporting puts the victim's family's ages exactly there::
#
#     "मृतककी ९० वर्षीया सासू टुलकीमाया"   (the deceased's 90-year-old mother-in-law)
#
# which recorded 90 deaths for an article headlined "पहिरोले घर पुरिँदा
# महिलाको मृत्यु" -- one woman. It was the single largest fatality figure in the
# whole inventory.
#
# An age in Nepali is marked by the word that follows it, वर्ष / बर्ष and their
# adjectival forms (वर्षीय, वर्षीया, बर्षे). That suffix is unambiguous: a count
# of dead people is never followed by "years".
NP_AGE_SUFFIX_PATTERN = re.compile(r'^\s*(?:वर्ष|बर्ष|वर्ष्|बर्ष्)')


def _is_age_context(text: str, start: int, end: int) -> bool:
    """Whether a numeric match is a person's age rather than a count."""

    return NP_AGE_SUFFIX_PATTERN.search(text[end:end + 12]) is not None


def _casualty_scope(text: str, lead_chars: int = 400) -> str:
    """Restrict casualty search to the headline and lead.

    See the identical note in nlp_en/extract.py: taking the maximum number
    anywhere in the body returned the nationwide season-to-date total instead of
    this event's toll, inflating recorded deaths roughly sevenfold.
    """

    if not text:
        return ''
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return text[:lead_chars]
    return '\n'.join(lines[:2])[:lead_chars] or text[:lead_chars]


def _extract_casualties(text: str, casualty_terms: dict[str, list[str]]) -> tuple[int | None, int | None, int | None, float]:
    normalized_text = devanagari_to_ascii_digits(text)
    casualty_scope = _casualty_scope(normalized_text)
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
        # A count of people is written either as digits or as a numeral word,
        # and the word form dominates for small tolls -- "तीन जनाको मृत्यु".
        # The numeral must be followed by a person classifier or a person noun,
        # which is what keeps `छ` (both "six" and the verb "is") from firing on
        # every sentence.
        number = rf'\d+|{NEPALI_NUMBER_ALTERNATION}'
        person = NEPALI_PERSON_NOUN_ALTERNATION
        patterns = (
            re.compile(
                rf'(?P<qual>कम्तीमा|कम्तिमा|करिब|झण्डै)?\s*(?P<num>{number})\s*'
                rf'(?:{person})\w*\s*(?:{term_group})'
            ),
            # The death term is often separated from the count by a short
            # descriptive clause -- "दुई जनाको ढिस्को खसेर मृत्यु" (two people
            # died when a mound collapsed). The gap is bounded and may not
            # cross a danda, so it cannot reach into the next sentence.
            re.compile(
                rf'(?P<qual>कम्तीमा|कम्तिमा|करिब|झण्डै)?\s*(?P<num>{number})\s*'
                rf'(?:{person})\w*[^।\n]{{0,40}}?(?:{term_group})'
            ),
            re.compile(rf'(?:{term_group})[^0-9]{{0,8}}(?P<num>\d+)'),
        )
        best_value = None
        best_conf = 0.0
        # See the English extractor: lead first, full body only as a fallback,
        # first match rather than largest, running totals vetoed.
        for search_text in (casualty_scope, normalized_text):
            if best_value is not None:
                break
            for pattern in patterns:
                if best_value is not None:
                    break
                for match in pattern.finditer(search_text):
                    if _is_aggregate_context(search_text, match.start(), match.end()):
                        continue
                    if _is_age_context(search_text, match.start('num'), match.end('num')):
                        continue
                    raw = match.group('num')
                    value = int(raw) if raw.isdigit() else parse_nepali_number(raw)
                    if value is None:
                        continue
                    qualifier = match.groupdict().get('qual') or ''
                    best_value = value
                    # A word-form numeral is as reliable as a digit here,
                    # because the pattern already required a person classifier
                    # after it; an approximate qualifier is what lowers trust.
                    best_conf = 0.75 if qualifier else 0.92
                    break
        values[label] = best_value
        confidence = max(confidence, best_conf)

    if values['deaths'] is None:
        recovered, recovered_conf = _deaths_from_body_recovery(normalized_text, casualty_scope)
        if recovered is not None:
            values['deaths'] = recovered
            confidence = max(confidence, recovered_conf)

    if not any(value is not None for value in values.values()):
        # Only now, with nothing counted anywhere, may an explicit statement
        # that nobody was harmed be recorded as a zero. See nlp_counts.
        if explicit_zero_is_safe(text, 'np', extracted_any_count=False):
            return 0, None, None, 0.88
        confidence = 0.0
    return values['deaths'], values['missing'], values['injured'], confidence


# "शव फेला परेको छ" -- a body has been found -- confirms a death without using
# any death term, so a toll written this way was invisible to the casualty
# patterns above. It is the standard construction in recovery reporting and
# accounts for a large share of the Nepali articles that carried death language
# but no extracted count.
NP_BODY_RECOVERY_VERB_GROUP = '|'.join(NEPALI_BODY_RECOVERY_VERBS)


def _deaths_from_body_recovery(text: str, scope: str) -> tuple[int | None, float]:
    """Read a confirmed death toll from a body-recovery sentence."""

    pattern = re.compile(
        rf'(?P<num>\d+|{NEPALI_NUMBER_ALTERNATION})\s*'
        rf'(?:{NEPALI_PERSON_NOUN_ALTERNATION})\w*\s*'
        rf'(?:को|का|के)?\s*शव\s*[^।.]{{0,20}}?(?:{NP_BODY_RECOVERY_VERB_GROUP})'
    )
    for search_text in (scope, text):
        for match in pattern.finditer(search_text):
            if _is_aggregate_context(search_text, match.start(), match.end()):
                continue
            if _is_age_context(search_text, match.start('num'), match.end('num')):
                continue
            raw = match.group('num')
            value = int(raw) if raw.isdigit() else parse_nepali_number(raw)
            if value is None:
                continue
            return value, 0.86
    return None, 0.0


def _extract_trigger(text: str, trigger_terms: dict[str, list[str]]) -> tuple[str, float]:
    if _contains_any(text, trigger_terms.get('earthquake', [])):
        return 'earthquake', 0.95
    if _has_anthropogenic_trigger_np(text, trigger_terms.get('road_construction', [])):
        return 'anthropogenic', 0.88
    if _contains_any(text, trigger_terms.get('rainfall', [])):
        return 'rainfall', 0.9
    return 'unknown', 0.3


# Phrases in which earthworks are the SETTING OF THE FAILURE rather than its
# aftermath. The English route has required a confirming phrase like this since
# it was written (`_has_anthropogenic_trigger`); the Nepali route did not, and
# matched its three bare configured terms directly.
#
# That asymmetry was expensive. `डोजर` is the machine that *clears* a landslide,
# and `निर्माण` appears in every "निर्माणाधीन सडक" -- a road under construction
# is where landslides happen, not a reason the slope moved. Between them they
# tagged 452 canonical events `anthropogenic`, which the analysis then dropped;
# 416 were Nepali-route, and reading them shows the great majority are ordinary
# rainfall-triggered landslides ("कालीखोलामा पहिरो, मुग्लिन सडक अवरुद्ध",
# "एकैदिन तीस ठाउँमा पहिरो").
#
# Deliberately absent: मजदुर and कामदार. Labourers are killed by real landslides
# too, and their presence says nothing about what moved the slope.
NP_ANTHROPOGENIC_CONTEXT = (
    # Burial by *placed* earth -- a spoil heap, a sand pile.
    'माटोको ढिस्को',
    'बालुवाको ढिस्को',
    'ढिस्कोले पुरि',
    'ढिस्कोमा पुरि',
    'ढिस्काले पुरि',
    # Extraction and earthmoving as the site of the failure.
    'प्लटिङ',
    'क्रसर',
    'उत्खनन',
    'खन्दै गरेको ठाउँ',
    'खन्ने क्रम',
    'खनेको ठाउँ',
    'पर्खाल लगाउँदा',
    'सडक विस्तारका क्रम',
    'सुरुङमार्ग निर्माण',
)


def _has_anthropogenic_trigger_np(text: str, terms: list[str]) -> bool:
    """Return whether human earthworks caused the failure, not merely followed it.

    Mirrors the English route's two-part test: a configured term must appear
    *and* a phrase placing the earthworks at the failure itself. Either half
    alone is not evidence.
    """

    if not _contains_any(text, terms):
        return False
    return any(phrase in text for phrase in NP_ANTHROPOGENIC_CONTEXT)


def _classify_event(
    *,
    combined: str,
    district: str | None,
    conf_date: float,
    landslide_terms: list[str],
    exclude_terms: list[str],
) -> tuple[int, float]:
    if _contains_any(combined, exclude_terms):
        return 3, 0.95
    has_landslide = _contains_any(combined, landslide_terms)
    if not has_landslide:
        return 3, 0.9
    if district is not None and conf_date >= 0.75:
        return 1, 0.92
    return 2, 0.8


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
    if title_text and NP_DIRECT_EVENT_TITLE_PATTERN.search(title_text):
        return True
    return False


def _infer_weekday_date(published: date, weekday_name: str) -> date | None:
    target = NP_WEEKDAY_INDEX.get(weekday_name)
    if target is None:
        return None
    delta = (published.weekday() - target) % 7
    return published - timedelta(days=delta)


def _contains_any(text: str, terms: list[str]) -> bool:
    return any(term and term in text for term in terms)


def _lead_window(text: str, limit: int = 700) -> str:
    """Use the earliest article text for date inference to avoid boilerplate and later references."""

    stripped = text.strip()
    if not stripped:
        return ''
    return stripped[:limit]


def _extract_explicit_anchor_date(
    text: str,
    published_year_hint: int | None,
) -> tuple[str | None, float]:
    bs_date = detect_bs_date(text)
    if bs_date is not None:
        return bs_to_ad(bs_date).isoformat(), 0.95
    if published_year_hint is not None:
        hinted = _infer_bs_no_year_date(text, published_year_hint)
        if hinted is not None:
            return hinted, 0.88
    return None, 0.0


def _should_search_full_text_for_anchor(text: str) -> bool:
    first_line = text.splitlines()[0] if text else ''
    return bool(NP_FOLLOWUP_TITLE_PATTERN.search(first_line))


def _infer_bs_no_year_date(text: str, published_year_hint: int) -> str | None:
    normalized = devanagari_to_ascii_digits(text)
    match = NP_DAY_MONTH_NO_YEAR_PATTERN.search(normalized)
    if match is not None:
        day = int(match.group(1))
        month_name = match.group(2)
    else:
        reverse_match = NP_MONTH_DAY_NO_YEAR_PATTERN.search(normalized)
        if reverse_match is None:
            return None
        month_name = reverse_match.group(1)
        day = int(reverse_match.group(2))
    month_map = {
        'बैशाख': 1,
        'वैशाख': 1,
        'जेठ': 2,
        'असार': 3,
        'साउन': 4,
        'भदौ': 5,
        'असोज': 6,
        'कात्तिक': 7,
        'कार्तिक': 7,
        'मंसिर': 8,
        'पुष': 9,
        'पुस': 9,
        'माघ': 10,
        'फागुन': 11,
        'चैत': 12,
    }
    month = month_map.get(month_name)
    if month is None or not (1 <= day <= 32):
        return None
    candidates: list[date] = []
    for bs_year in range(published_year_hint + 55, published_year_hint + 58):
        try:
            candidate = bs_to_ad((bs_year, month, day))
        except Exception:
            continue
        if abs(candidate.year - published_year_hint) <= 1:
            candidates.append(candidate)
    if not candidates:
        return None
    for candidate in candidates:
        if candidate.year == published_year_hint:
            return candidate.isoformat()
    return candidates[0].isoformat()
