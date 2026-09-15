"""English place extraction helpers."""

from __future__ import annotations

from functools import lru_cache
import re

import spacy

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

EN_TRIGGER_WORDS = (
    'landslide', 'rain', 'rainfall', 'flood', 'buried', 'killed', 'dead', 'missing', 'injured', 'collapse'
)
EN_CONTEXT_WORDS = EN_TRIGGER_WORDS + ('house', 'road', 'river', 'settlement', 'rescue', 'monsoon')
EN_MUNICIPALITY_PATTERN = re.compile(
    r'\b[A-Z][A-Za-z.-]*(?:\s+[A-Z][A-Za-z.-]*)*\s+'
    r'(?:Rural Municipality|Municipality|Metropolitan City|Sub[- ]metropolitan City)\b'
)
EN_WARD_PATTERN = re.compile(
    r'\bWard(?:\s+No\.?)?\s*\d+\b(?:\s*(?:of|in|,)\s*[A-Z][A-Za-z.-]*(?:\s+[A-Z][A-Za-z.-]*)*\s+'
    r'(?:Rural Municipality|Municipality|Metropolitan City|Sub[- ]metropolitan City))?'
)
EN_DISTRICT_PATTERN = re.compile(r'\b([A-Z][A-Za-z.-]*(?:\s+[A-Z][A-Za-z.-]*)*)\s+District\b')
EN_PROVINCE_PATTERN = re.compile(
    r'\b(?:Koshi|Madhesh|Bagmati|Gandaki|Lumbini|Karnali|Sudurpashchim)\s+Province\b'
)
EN_VILLAGE_PATTERN = re.compile(r'\b[A-Z][A-Za-z.-]*(?:\s+[A-Z][A-Za-z.-]*)*\s+Village\b')
EN_DISTRICT_ALIASES_PATTERN = re.compile(
    r'\b(?:Achham|Arghakhanchi|Baglung|Baitadi|Bajhang|Bajura|Banke|Bara|Bardiya|Bhaktapur|Bhojpur|Chitwan|Dadeldhura|Dailekh|Dang|Darchula|Dhading|Dhankuta|Dhanusha|Dolakha|Dolpa|Doti|Gorkha|Gulmi|Humla|Ilam|Jajarkot|Jhapa|Jumla|Kailali|Kalikot|Kanchanpur|Kapilvastu|Kaski|Kathmandu|Kavrepalanchok|Khotang|Lalitpur|Lamjung|Mahottari|Makwanpur|Manang|Morang|Mugu|Mustang|Myagdi|Nawalparasi East|Nawalparasi West|Nawalpur|Nuwakot|Okhaldhunga|Palpa|Panchthar|Parasi|Parbat|Parsa|Pyuthan|Ramechhap|Rasuwa|Rautahat|Rolpa|Rukum East|Rukum West|Rupandehi|Salyan|Sankhuwasabha|Saptari|Sarlahi|Sindhuli|Sindhupalchok|Sindhupalchowk|Siraha|Solukhumbu|Sunsari|Surkhet|Syangja|Tanahun|Taplejung|Terhathum|Udayapur)\b'
)


def extract_place_en(text: str, municipality_to_district: dict[str, str] | None = None) -> PlaceExtraction:
    """Extract the best available English place mention for an article."""

    candidates: list[PlaceCandidate] = []
    candidates.extend(_regex_candidates(text))
    candidates.extend(_ner_candidates(text))
    return finalize_place_extraction(candidates, municipality_to_district_map=municipality_to_district, lang='en')


def build_address_ladders_en(text: str, municipality_to_district: dict[str, str] | None = None) -> list[str]:
    """Build address ladders from the best extracted English place mention."""

    extraction = extract_place_en(text, municipality_to_district=municipality_to_district)
    if extraction.place_name_raw is None:
        return []
    best = next(iter(_best_candidates(text)), None)
    if best is None:
        return []
    province = province_from_district_or_name(extraction.district, best.province, 'en')
    from ..unify.location import build_address_ladders
    return build_address_ladders(
        ward=extraction.ward,
        municipality=extraction.municipality,
        district=extraction.district,
        province=province,
    )


def _best_candidates(text: str) -> list[PlaceCandidate]:
    candidates: list[PlaceCandidate] = []
    candidates.extend(_regex_candidates(text))
    candidates.extend(_ner_candidates(text))
    return dedupe_and_rank_candidates(candidates)


def _regex_candidates(text: str) -> list[PlaceCandidate]:
    candidates: list[PlaceCandidate] = []
    # A place inside a home-address attribution -- "the deceased has been
    # identified as Namrata Karki of Chandrpur Municipality-1, Rautahat" --
    # belongs to a person, not to the event, and must not become a place
    # candidate. See nlp_attribution for why this matters at district scale.
    for match in EN_WARD_PATTERN.finditer(text):
        if is_person_attribution(text, match.start(), match.end(), 'en'):
            continue
        municipality_match = EN_MUNICIPALITY_PATTERN.search(match.group(0))
        municipality_raw = municipality_match.group(0) if municipality_match else None
        municipality = normalize_municipality(municipality_raw, 'en') if municipality_raw else None
        candidates.append(_candidate(text, match.group(0), 'ward', match.start(), municipality=municipality))
    for match in EN_MUNICIPALITY_PATTERN.finditer(text):
        if is_person_attribution(text, match.start(), match.end(), 'en'):
            continue
        municipality_raw = match.group(0)
        municipality = normalize_municipality(municipality_raw, 'en')
        candidates.append(_candidate(text, municipality_raw, 'municipality', match.start(), municipality=municipality))
    for match in EN_DISTRICT_PATTERN.finditer(text):
        if is_person_attribution(text, match.start(1), match.end(1), 'en'):
            continue
        district_name = match.group(1)
        normalized = normalize_district(district_name, 'en')
        candidates.append(_candidate(text, district_name, 'district', match.start(), district=normalized))
    for match in EN_DISTRICT_ALIASES_PATTERN.finditer(text):
        district_name = match.group(0)
        normalized = normalize_district(district_name, 'en')
        if normalized is None:
            continue
        if is_person_attribution(text, match.start(), match.end(), 'en'):
            continue
        candidates.append(_candidate(text, district_name, 'district', match.start(), district=normalized))
    for match in EN_PROVINCE_PATTERN.finditer(text):
        candidates.append(_candidate(text, match.group(0), 'province', match.start(), province=match.group(0)))
    for match in EN_VILLAGE_PATTERN.finditer(text):
        candidates.append(_candidate(text, match.group(0), 'village', match.start()))
    return candidates


def _ner_candidates(text: str) -> list[PlaceCandidate]:
    document = _nlp()(text)
    candidates: list[PlaceCandidate] = []
    for entity in document.ents:
        if entity.label_ not in {'GPE', 'LOC'}:
            continue
        district = normalize_district(entity.text, 'en')
        admin_level = 'district' if district else 'unknown'
        candidates.append(_candidate(text, entity.text, admin_level, entity.start_char, district=district))
    return candidates


@lru_cache(maxsize=1)
def _nlp():
    try:
        return spacy.load('en_core_web_sm', disable=['tagger', 'parser', 'lemmatizer'])
    except Exception:
        return spacy.blank('en')


def _candidate(
    text: str,
    name: str,
    admin_level: str,
    start: int,
    municipality: str | None = None,
    district: str | None = None,
    province: str | None = None,
) -> PlaceCandidate:
    cleaned_name = _clean_name(name)
    score = _score_candidate(text, cleaned_name, admin_level, start)
    if district:
        score += 2.5
    if municipality:
        score += 1.5
    return PlaceCandidate(
        name=cleaned_name,
        admin_level=admin_level,
        score=score,
        start=start,
        municipality=municipality,
        district=district,
        province=province,
    )


def _clean_name(name: str) -> str:
    text = re.sub(r'\s+', ' ', name).strip(' ,;:-')
    return text


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
    context = text[max(0, start - 120): start + len(name) + 120].casefold()
    if any(word in context for word in EN_TRIGGER_WORDS):
        score += 2.0
    if any(word in context for word in EN_CONTEXT_WORDS):
        score += 0.5
    if any(token in name for token in ('Ward', 'Municipality', 'District', 'Province', 'Village')):
        score += 1.5
    if admin_level == 'unknown':
        if not any(word in context for word in EN_CONTEXT_WORDS):
            score -= 1.5
        if len(normalize_key(name).split()) > 3:
            score -= 1.0
    score += max(0.0, 2.0 - (start / 800.0))
    return score
