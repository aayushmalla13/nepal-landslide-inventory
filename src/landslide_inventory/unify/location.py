"""Shared place extraction and district resolution helpers."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Iterable
import unicodedata

from ..gazetteer import district_to_province, normalize_district
from ..gazetteer_municipality import municipality_to_district

PLACE_ADMIN_LEVELS = {'ward', 'village', 'municipality', 'district', 'province', 'unknown'}

NEPAL_PROVINCES_EN = {
    'koshi province': 'Koshi',
    'madhesh province': 'Madhesh',
    'bagmati province': 'Bagmati',
    'gandaki province': 'Gandaki',
    'lumbini province': 'Lumbini',
    'karnali province': 'Karnali',
    'sudurpashchim province': 'Sudurpashchim',
}
NEPAL_PROVINCES_NP = {
    'कोशी प्रदेश': 'Koshi',
    'मधेश प्रदेश': 'Madhesh',
    'बागमती प्रदेश': 'Bagmati',
    'गण्डकी प्रदेश': 'Gandaki',
    'गंडकी प्रदेश': 'Gandaki',
    'लुम्बिनी प्रदेश': 'Lumbini',
    'कर्णाली प्रदेश': 'Karnali',
    'सुदूरपश्चिम प्रदेश': 'Sudurpashchim',
}


@dataclass(frozen=True)
class PlaceCandidate:
    """Single scored place candidate."""

    name: str
    admin_level: str
    score: float
    start: int
    municipality: str | None = None
    district: str | None = None
    province: str | None = None


@dataclass(frozen=True)
class PlaceExtraction:
    """Best available article-level place extraction output."""

    place_admin_level: str
    place_name_raw: str | None
    place_candidates_json: str
    district: str | None
    municipality: str | None
    ward: str | None
    conf_place: float

    def to_record(self) -> dict[str, object]:
        """Return a serializable schema-aligned record."""

        return {
            'place_admin_level': self.place_admin_level,
            'place_name_raw': self.place_name_raw,
            'place_candidates_json': self.place_candidates_json,
            'district': self.district,
            'municipality': self.municipality,
            'ward': self.ward,
            'conf_place': self.conf_place,
        }


def finalize_place_extraction(
    candidates: Iterable[PlaceCandidate],
    municipality_to_district_map: dict[str, str] | None = None,
    lang: str = 'en',
) -> PlaceExtraction:
    """Convert scored place candidates into the schema-aligned output."""

    ordered = dedupe_and_rank_candidates(candidates)
    if not ordered:
        return PlaceExtraction(
            place_admin_level='unknown',
            place_name_raw=None,
            place_candidates_json='[]',
            district=None,
            municipality=None,
            ward=None,
            conf_place=0.0,
        )

    best = ordered[0]
    municipality = best.municipality if best.admin_level in {'ward', 'municipality'} else None
    district = resolve_district(
        explicit_district=best.district or (best.name if best.admin_level == 'district' else None),
        municipality=municipality,
        lang=lang,
        municipality_to_district_map=municipality_to_district_map,
    )
    conf_place = round(min(0.99, max(0.05, best.score / 10.0)), 2)
    candidates_json = json.dumps([candidate.name for candidate in ordered[:10]], ensure_ascii=False)
    return PlaceExtraction(
        place_admin_level=best.admin_level if best.admin_level in PLACE_ADMIN_LEVELS else 'unknown',
        place_name_raw=best.name,
        place_candidates_json=candidates_json,
        district=district,
        municipality=municipality,
        ward=best.name if best.admin_level == 'ward' else None,
        conf_place=conf_place,
    )


def dedupe_and_rank_candidates(candidates: Iterable[PlaceCandidate]) -> list[PlaceCandidate]:
    """Deduplicate candidates and return a deterministic top-ranked list."""

    by_key: dict[str, PlaceCandidate] = {}
    for candidate in candidates:
        if not is_viable_candidate(candidate):
            continue
        key = normalize_key(candidate.name)
        if not key:
            continue
        current = by_key.get(key)
        if current is None or candidate_rank_tuple(candidate) < candidate_rank_tuple(current):
            by_key[key] = candidate
    return sorted(by_key.values(), key=candidate_rank_tuple)[:10]


def candidate_rank_tuple(candidate: PlaceCandidate) -> tuple[float, int, str]:
    """Return deterministic ranking tuple for a candidate."""

    return (-candidate.score, candidate.start, normalize_key(candidate.name))


def resolve_district(
    explicit_district: str | None,
    municipality: str | None,
    lang: str,
    municipality_to_district_map: dict[str, str] | None = None,
) -> str | None:
    """Resolve the canonical district when it is explicitly available or mapped."""

    if explicit_district:
        normalized = normalize_district(explicit_district, lang)
        if normalized is not None:
            return normalized
        fallback_lang = 'en' if lang == 'np' else 'np'
        normalized = normalize_district(explicit_district, fallback_lang)
        if normalized is not None:
            return normalized
    if municipality:
        if municipality_to_district_map and municipality in municipality_to_district_map:
            return municipality_to_district_map[municipality]
        return municipality_to_district(municipality)
    return None


def province_from_district_or_name(district: str | None, province_name: str | None, lang: str) -> str | None:
    """Resolve the province from district or an explicit province name."""

    if district:
        return district_to_province(district)
    if not province_name:
        return None
    normalized = normalize_key(province_name)
    province_map = NEPAL_PROVINCES_NP if lang == 'np' else NEPAL_PROVINCES_EN
    return province_map.get(normalized)


def build_address_ladders(
    ward: str | None = None,
    municipality: str | None = None,
    district: str | None = None,
    province: str | None = None,
) -> list[str]:
    """Build the deterministic address-ladder strings for later geocoding."""

    ladders: list[str] = []
    if ward and municipality and district:
        ladders.append(f'{ward}, {municipality}, {district}, Nepal')
    if municipality and district:
        ladders.append(f'{municipality}, {district}, Nepal')
    if district:
        ladders.append(f'{district}, Nepal')
    if province:
        ladders.append(f'{province}, Nepal')
    seen: set[str] = set()
    ordered: list[str] = []
    for ladder in ladders:
        key = normalize_key(ladder)
        if key in seen:
            continue
        seen.add(key)
        ordered.append(ladder)
    return ordered


def normalize_key(value: str) -> str:
    """Normalize a free-text place value for stable comparison."""

    normalized = unicodedata.normalize('NFKC', value).strip().casefold()
    for character in ('-', '_', ',', '.', '/', '(', ')'):
        normalized = normalized.replace(character, ' ')
    return ' '.join(normalized.split())


def is_viable_candidate(candidate: PlaceCandidate) -> bool:
    """Return whether a place candidate is plausible enough to keep."""

    name = candidate.name.strip()
    if not name:
        return False
    key = normalize_key(name)
    if not key or len(key) < 2:
        return False
    if _looks_like_noise(key):
        return False
    if candidate.admin_level == 'unknown' and candidate.score < 3.5:
        return False
    return True


def _looks_like_noise(key: str) -> bool:
    """Return whether the normalized candidate text looks like page chrome or a clause."""

    banned_tokens = {
        'facebook',
        'messenger',
        'twitter',
        'instagram',
        'youtube',
        'whatsapp',
        'viber',
        'email',
        'read more',
        'art culture',
        'art entertainment',
        'sports',
        'cricket',
        'football',
    }
    if key in banned_tokens:
        return True
    if any(token in key for token in ('share', 'follow us', 'subscribe')):
        return True
    if key.count(' ') >= 7 and not any(
        suffix in key
        for suffix in (
            'municipality',
            'rural municipality',
            'district',
            'province',
            'वडा',
            'नगरपालिका',
            'गाउँपालिका',
            'जिल्ला',
            'प्रदेश',
            'बस्ती',
            'टोल',
        )
    ):
        return True
    return False
