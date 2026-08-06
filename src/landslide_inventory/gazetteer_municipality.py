"""Municipality gazetteer helpers for offline municipality-to-district resolution."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import re
import unicodedata

from rapidfuzz import fuzz, process


RESOURCE_DIR = Path(__file__).resolve().parents[2] / 'resources'
MUNICIPALITIES_EN_CSV = RESOURCE_DIR / 'municipalities_en.csv'
MUNICIPALITIES_NP_CSV = RESOURCE_DIR / 'municipalities_np.csv'
FUZZY_THRESHOLD = 90.0


@dataclass(frozen=True)
class MunicipalityGazetteers:
    """Loaded municipality lookups for English and Nepali matching."""

    en_alias_to_canonical: dict[str, str]
    np_alias_to_canonical: dict[str, str]
    district_by_canonical: dict[str, str]


def load_municipality_gazetteers() -> MunicipalityGazetteers:
    """Load committed municipality gazetteers and build exact lookup maps."""

    return _load_municipality_gazetteers()


@lru_cache(maxsize=1)
def _load_municipality_gazetteers() -> MunicipalityGazetteers:
    from .gazetteer import all_districts

    districts = set(all_districts())
    en_alias_to_canonical: dict[str, str] = {}
    np_alias_to_canonical: dict[str, str] = {}
    district_by_canonical: dict[str, str] = {}

    for row in _load_csv(MUNICIPALITIES_EN_CSV):
        canonical = row['municipality_en_canonical'].strip()
        district = row['district_canonical'].strip()
        if district not in districts:
            raise ValueError(f'Unknown district in municipalities_en.csv: {district}')
        district_by_canonical[canonical] = district
        for alias in _split_variants(canonical, row['municipality_en_variants']):
            en_alias_to_canonical[_normalize_key(alias)] = canonical

    for row in _load_csv(MUNICIPALITIES_NP_CSV):
        canonical = row['municipality_en_canonical'].strip()
        district = row['district_canonical'].strip()
        if district not in districts:
            raise ValueError(f'Unknown district in municipalities_np.csv: {district}')
        district_by_canonical.setdefault(canonical, district)
        for alias in _split_variants(row['municipality_np_canonical'], row['municipality_np_variants']):
            np_alias_to_canonical[_normalize_key(alias)] = canonical

    return MunicipalityGazetteers(
        en_alias_to_canonical=en_alias_to_canonical,
        np_alias_to_canonical=np_alias_to_canonical,
        district_by_canonical=district_by_canonical,
    )


def normalize_municipality(name: str, lang: str) -> str | None:
    """Normalize a municipality name to its canonical English form."""

    gazetteers = load_municipality_gazetteers()
    alias_map = gazetteers.en_alias_to_canonical if lang == 'en' else gazetteers.np_alias_to_canonical
    lookup_keys = _lookup_keys(name, lang)
    for key in lookup_keys:
        exact = alias_map.get(key)
        if exact is not None:
            return exact
    if not lookup_keys:
        return None
    for key in lookup_keys:
        if len(key) < 4:
            continue
        match = _fuzzy_match(key, alias_map)
        if match is not None:
            return match
    return None


def municipality_to_district(municipality_en_canonical: str) -> str | None:
    """Return the canonical district for a canonical municipality name."""

    return load_municipality_gazetteers().district_by_canonical.get(municipality_en_canonical)


def _lookup_keys(value: str, lang: str) -> list[str]:
    raw = unicodedata.normalize('NFKC', value).strip()
    candidates: list[str] = []

    def add(candidate: str) -> None:
        key = _normalize_key(candidate)
        if key and key not in candidates:
            candidates.append(key)

    add(raw)
    if lang == 'np':
        suffixes = ('महानगरपालिका', 'उपमहानगरपालिका', 'नगरपालिका', 'गाउँपालिका')
        postpositions = ('को', 'का', 'मा', 'बाट', 'ले', 'देखि', 'सम्म', 'सँग')
        bare_with_ward = re.search(r'([ऀ-ॿ]+(?:\s+[ऀ-ॿ]+){0,2})\s*[–—-]\s*[०-९0-9]+', raw)
        if bare_with_ward is not None:
            add(bare_with_ward.group(1))
        for suffix in suffixes:
            if suffix not in raw:
                continue
            prefix = raw.split(suffix, 1)[0]
            tokens = re.findall(r'[ऀ-ॿ]+', prefix)
            for size in (3, 2, 1):
                if len(tokens) >= size:
                    add(' '.join(tokens[-size:]) + ' ' + suffix)
        for postposition in postpositions:
            stripped = re.sub(rf'^(?:[ऀ-ॿ]+(?:\s+[ऀ-ॿ]+){{0,2}})?{postposition}\s+', '', raw)
            if stripped != raw:
                add(stripped)
            stripped = re.sub(rf'^[ऀ-ॿ]+{postposition}\s+', '', raw)
            if stripped != raw:
                add(stripped)
    else:
        lowered = raw
        match = re.search(r'([A-Za-z][A-Za-z .-]*(?:Rural Municipality|Municipality|Metropolitan City|Sub[- ]metropolitan City))', lowered, re.IGNORECASE)
        if match is not None:
            add(match.group(1))
        tokens = raw.split()
        for size in (5, 4, 3, 2):
            if len(tokens) >= size:
                add(' '.join(tokens[-size:]))
    return candidates


def _admin_family(key: str) -> str | None:
    if 'rural municipality' in key or 'गाउँपालिका' in key:
        return 'rural'
    if 'sub metropolitan city' in key or 'sub metropolitan' in key or 'उपमहानगरपालिका' in key:
        return 'submetro'
    if 'metropolitan city' in key or 'महानगरपालिका' in key:
        return 'metro'
    if 'municipality' in key or 'नगरपालिका' in key:
        return 'municipality'
    return None


def _significant_tokens(key: str) -> set[str]:
    stop = {'rural', 'municipality', 'metropolitan', 'city', 'sub', 'गाउँपालिका', 'नगरपालिका', 'महानगरपालिका', 'उपमहानगरपालिका'}
    return {token for token in key.split() if token not in stop}


def _fuzzy_match(key: str, alias_map: dict[str, str]) -> str | None:
    input_family = _admin_family(key)
    input_tokens = _significant_tokens(key)
    choices = [choice for choice in sorted(alias_map) if input_family is None or _admin_family(choice) == input_family]
    if input_tokens:
        filtered = [choice for choice in choices if _significant_tokens(choice) & input_tokens]
        if filtered:
            choices = filtered
    matches = process.extract(
        key,
        choices,
        scorer=fuzz.ratio,
        processor=None,
        limit=2,
    )
    if not matches:
        return None
    top_key, top_score, _ = matches[0]
    if top_score < FUZZY_THRESHOLD:
        return None
    top_canonical = alias_map[top_key]
    if len(matches) > 1:
        second_key, second_score, _ = matches[1]
        second_canonical = alias_map[second_key]
        if second_score == top_score and second_canonical != top_canonical:
            return None
    return top_canonical


def _load_csv(path: Path) -> list[dict[str, str]]:
    with path.open('r', encoding='utf-8', newline='') as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _split_variants(canonical: str, raw_variants: str) -> list[str]:
    values = [canonical.strip()]
    values.extend(value.strip() for value in raw_variants.split('|') if value.strip())
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        key = _normalize_key(value)
        if not key or key in seen:
            continue
        seen.add(key)
        ordered.append(value)
    return ordered


def _normalize_key(value: str) -> str:
    normalized = unicodedata.normalize('NFKC', value).strip().casefold()
    for character in ('-', '_', ',', '.', '/', '(', ')'):
        normalized = normalized.replace(character, ' ')
    return ' '.join(normalized.split())
