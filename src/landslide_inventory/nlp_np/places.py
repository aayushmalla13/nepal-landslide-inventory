"""Nepali place extraction helpers."""

from __future__ import annotations

import csv
from pathlib import Path
import re

from ..gazetteer import normalize_district
from ..nlp_attribution import is_person_attribution
from ..gazetteer_municipality import normalize_municipality
from ..unify.location import (
    PlaceCandidate,
    PlaceExtraction,
    dedupe_and_rank_candidates,
    finalize_place_extraction,
    normalize_key,
    province_from_district_or_name,
)

RESOURCE_DIR = Path(__file__).resolve().parents[3] / 'resources'
NP_TRIGGER_WORDS = (
    'पहिरो', 'वर्षा', 'बाढी', 'मृत्यु', 'बेपत्ता', 'घाइते', 'पुरियो', 'अवरुद्ध'
)
NP_CONTEXT_WORDS = NP_TRIGGER_WORDS + ('घर', 'सडक', 'नदी', 'उद्धार', 'बस्ती', 'जोखिम')
NP_ADMIN_SUFFIX_PATTERN = r'(?:महानगरपालिका|उपमहानगरपालिका|नगरपालिका|गाउँपालिका)'
NP_MUNICIPALITY_PATTERN = re.compile(
    rf'(?:[ऀ-ॿ]+(?:\s+[ऀ-ॿ]+){{0,3}})\s*{NP_ADMIN_SUFFIX_PATTERN}'
)
NP_WARD_PATTERN = re.compile(
    rf'(?:(?:[ऀ-ॿ]+(?:\s+[ऀ-ॿ]+){{0,3}})\s*{NP_ADMIN_SUFFIX_PATTERN}\s*[-–]?[०-९0-9]+\s*वडा|'
    rf'वडा\s*नं\.?\s*[०-९0-9]+(?:\s*,?\s*(?:[ऀ-ॿ]+(?:\s+[ऀ-ॿ]+){{0,3}})\s*{NP_ADMIN_SUFFIX_PATTERN})?)'
)
NP_DISTRICT_PATTERN = re.compile(r'((?:[ऀ-ॿ]+(?:\s+[ऀ-ॿ]+){0,2}))\s+जिल्ला')
NP_PROVINCE_PATTERN = re.compile(
    r'(?:कोशी प्रदेश|मधेश प्रदेश|बागमती प्रदेश|गण्डकी प्रदेश|गंडकी प्रदेश|लुम्बिनी प्रदेश|कर्णाली प्रदेश|सुदूरपश्चिम प्रदेश)'
)
NP_VILLAGE_PATTERN = re.compile(r'(?:[ऀ-ॿ]+(?:\s+[ऀ-ॿ]+){0,3})\s+(?:टोल|बस्ती)')
NP_POSTPOSITION_SUFFIXES = ('मा', 'को', 'का', 'ले', 'बाट', 'देखि', 'सम्म', 'सँग')


def _district_aliases_np() -> list[str]:
    aliases: set[str] = set()
    csv_path = RESOURCE_DIR / 'districts_np.csv'
    with csv_path.open('r', encoding='utf-8', newline='') as handle:
        for row in csv.DictReader(handle):
            aliases.add(str(row['district_np']).strip())
            for variant in str(row['variants_np']).split('|'):
                variant = variant.strip()
                if variant:
                    aliases.add(variant)
    return [alias for alias in aliases if alias]


NP_DISTRICT_ALIAS_PATTERN = re.compile(
    '|'.join(sorted((re.escape(value) for value in _district_aliases_np()), key=len, reverse=True))
)
NP_TIGHT_WARD_PATTERN = re.compile(
    rf'((?:[ऀ-ॿ]+(?:\s+[ऀ-ॿ]+){{0,1}})\s*{NP_ADMIN_SUFFIX_PATTERN}\s*[-–]?[०-९0-9]+\s*वडा)$'
)
NP_TIGHT_MUNICIPALITY_PATTERN = re.compile(
    rf'((?:[ऀ-ॿ]+(?:\s+[ऀ-ॿ]+){{0,1}})\s*{NP_ADMIN_SUFFIX_PATTERN})$'
)
NP_TIGHT_VILLAGE_PATTERN = re.compile(r'((?:[ऀ-ॿ]+(?:\s+[ऀ-ॿ]+){0,1})\s+(?:टोल|बस्ती))$')


def extract_place_np(text: str, municipality_to_district: dict[str, str] | None = None) -> PlaceExtraction:
    """Extract the best available Nepali place mention for an article."""

    candidates = _regex_candidates(text)
    return finalize_place_extraction(candidates, municipality_to_district_map=municipality_to_district, lang='np')


def build_address_ladders_np(text: str, municipality_to_district: dict[str, str] | None = None) -> list[str]:
    """Build address ladders from the best extracted Nepali place mention."""

    extraction = extract_place_np(text, municipality_to_district=municipality_to_district)
    best = next(iter(_best_candidates(text)), None)
    if extraction.place_name_raw is None or best is None:
        return []
    province = province_from_district_or_name(extraction.district, best.province, 'np')
    from ..unify.location import build_address_ladders
    return build_address_ladders(
        ward=extraction.ward,
        municipality=extraction.municipality,
        district=extraction.district,
        province=province,
    )


def _best_candidates(text: str) -> list[PlaceCandidate]:
    return dedupe_and_rank_candidates(_regex_candidates(text))


def _regex_candidates(text: str) -> list[PlaceCandidate]:
    candidates: list[PlaceCandidate] = []
    # A place written inside a home-address attribution -- "सिन्धुपाल्चोक
    # जिल्लाको मेलम्ची घर भएका चालक", the driver's home -- describes a person,
    # not the event. Such mentions are not place candidates at all; admitting
    # them let a victim's home district outrank the event district, which the
    # rest of the pipeline cannot detect because the result is self-consistent.
    for match in NP_WARD_PATTERN.finditer(text):
        if is_person_attribution(text, match.start(), match.end(), 'np'):
            continue
        ward_text = _clean_name(match.group(0), admin_level='ward')
        municipality = _resolve_municipality_from_raw(match.group(0))
        candidates.append(_candidate(text, ward_text, 'ward', match.start(), municipality=municipality))
    for match in NP_MUNICIPALITY_PATTERN.finditer(text):
        if is_person_attribution(text, match.start(), match.end(), 'np'):
            continue
        municipality_raw = _clean_name(match.group(0), admin_level='municipality')
        municipality = _resolve_municipality_from_raw(match.group(0))
        candidates.append(_candidate(text, municipality_raw, 'municipality', match.start(), municipality=municipality))
    for match in NP_DISTRICT_PATTERN.finditer(text):
        if is_person_attribution(text, match.start(1), match.end(1), 'np'):
            continue
        district_name = _clean_name(match.group(1), admin_level='district')
        normalized = _normalize_np_district_name(district_name)
        candidates.append(_candidate(text, district_name, 'district', match.start(), district=normalized))
    for match in NP_DISTRICT_ALIAS_PATTERN.finditer(text):
        district_name = _clean_name(match.group(0), admin_level='district')
        normalized = _normalize_np_district_name(district_name)
        if normalized is None:
            continue
        if is_person_attribution(text, match.start(), match.end(), 'np'):
            continue
        candidates.append(_candidate(text, district_name, 'district', match.start(), district=normalized))
    for match in NP_PROVINCE_PATTERN.finditer(text):
        province_name = _clean_name(match.group(0), admin_level='province')
        candidates.append(_candidate(text, province_name, 'province', match.start(), province=province_name))
    for match in NP_VILLAGE_PATTERN.finditer(text):
        village = _clean_name(match.group(0), admin_level='village')
        candidates.append(_candidate(text, village, 'village', match.start()))
    return candidates


def _resolve_municipality_from_raw(raw_text: str) -> str | None:
    direct = normalize_municipality(raw_text, 'np')
    if direct is not None:
        return direct
    suffix_match = re.search(NP_ADMIN_SUFFIX_PATTERN, raw_text)
    if suffix_match is None:
        return None
    suffix = suffix_match.group(0)
    prefix = raw_text[:suffix_match.start()]
    tokens = re.findall(r'[ऀ-ॿ]+', prefix)
    for size in (2, 1, 3):
        if len(tokens) < size:
            continue
        candidate = ' '.join(tokens[-size:]) + ' ' + suffix
        normalized = normalize_municipality(candidate, 'np')
        if normalized is not None:
            return normalized
    return None


def _candidate(
    text: str,
    name: str,
    admin_level: str,
    start: int,
    municipality: str | None = None,
    district: str | None = None,
    province: str | None = None,
) -> PlaceCandidate:
    score = _score_candidate(text, name, admin_level, start)
    if district:
        score += 2.5
    if municipality:
        score += 1.5
    return PlaceCandidate(
        name=name.strip(),
        admin_level=admin_level,
        score=score,
        start=start,
        municipality=municipality,
        district=district,
        province=province,
    )


def _score_candidate(text: str, name: str, admin_level: str, start: int) -> float:
    base_scores = {
        'ward': 6.0,
        'district': 5.5,
        'municipality': 4.5,
        'village': 3.5,
        'province': 2.5,
        'unknown': 1.0,
    }
    score = base_scores.get(admin_level, 1.0)
    context = text[max(0, start - 120): start + len(name) + 120]
    if any(word in context for word in NP_TRIGGER_WORDS):
        score += 2.0
    if any(word in context for word in NP_CONTEXT_WORDS):
        score += 0.5
    if any(token in name for token in ('वडा', 'गाउँपालिका', 'नगरपालिका', 'महानगरपालिका', 'उपमहानगरपालिका', 'टोल', 'बस्ती', 'जिल्ला', 'प्रदेश')):
        score += 1.5
    if len(normalize_key(name).split()) > 5:
        score -= 1.5
    score += max(0.0, 2.0 - (start / 800.0))
    return score


def _clean_name(name: str, admin_level: str) -> str:
    text = re.sub(r'\s+', ' ', name).strip(' ,;:।-–')
    text = re.sub(r'^(?:फेसबुक|मेसेन्जर|ट्विटर|इमेल)\s+', '', text)
    if admin_level == 'ward':
        matches = list(NP_TIGHT_WARD_PATTERN.finditer(text))
        if matches:
            text = matches[-1].group(1)
    elif admin_level == 'municipality':
        matches = list(NP_TIGHT_MUNICIPALITY_PATTERN.finditer(text))
        if matches:
            text = matches[-1].group(1)
    elif admin_level == 'village':
        matches = list(NP_TIGHT_VILLAGE_PATTERN.finditer(text))
        if matches:
            text = matches[-1].group(1)
    return text.strip(' ,;:।-–')


def _normalize_np_district_name(name: str) -> str | None:
    normalized = normalize_district(name, 'np')
    if normalized is not None:
        return normalized
    for suffix in NP_POSTPOSITION_SUFFIXES:
        if name.endswith(suffix) and len(name) > len(suffix) + 1:
            trimmed = name[: -len(suffix)]
            normalized = normalize_district(trimmed, 'np')
            if normalized is not None:
                return normalized
    return None
