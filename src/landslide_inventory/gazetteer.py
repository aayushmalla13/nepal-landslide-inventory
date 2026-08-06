"""District gazetteer helpers."""

from __future__ import annotations

import csv
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Iterable

RESOURCE_DIR = Path(__file__).resolve().parents[2] / "resources"
DISTRICTS_EN_CSV = RESOURCE_DIR / "districts_en.csv"
DISTRICTS_NP_CSV = RESOURCE_DIR / "districts_np.csv"

from .gazetteer_municipality import municipality_to_district, normalize_municipality


def normalize_district(name: str, lang: str) -> str | None:
    """Normalize a district name to the canonical English district."""

    alias_map = _district_aliases(lang)
    return alias_map.get(_normalize_key(name))


def district_to_province(district_en: str) -> str:
    """Return the province for a canonical district."""

    province = _district_provinces().get(district_en)
    if province is None:
        raise KeyError(f"Unknown district: {district_en}")
    return province


def all_districts() -> list[str]:
    """Return all canonical English districts."""

    return sorted(_district_provinces())


def gazetteer_exists(resources_dir: Path) -> bool:
    """Return whether the committed gazetteer files exist."""

    return (resources_dir / "districts_en.csv").exists() and (resources_dir / "districts_np.csv").exists()


@lru_cache(maxsize=2)
def _district_aliases(lang: str) -> dict[str, str]:
    """Build a district alias map for the requested language."""

    if lang not in {"en", "np"}:
        raise ValueError("lang must be 'en' or 'np'")

    aliases: dict[str, str] = {}
    if lang == "en":
        for row in _load_csv(DISTRICTS_EN_CSV):
            district = str(row["district"])
            for alias in _split_variants(row["variants_en"], district):
                aliases[_normalize_key(alias)] = district
    else:
        for row in _load_csv(DISTRICTS_NP_CSV):
            district = str(row["district_en"])
            for alias in _split_variants(row["variants_np"], str(row["district_np"])):
                aliases[_normalize_key(alias)] = district
    return aliases


@lru_cache(maxsize=1)
def _district_provinces() -> dict[str, str]:
    """Return canonical district-to-province mappings."""

    return {
        str(row["district"]): str(row["province"])
        for row in _load_csv(DISTRICTS_EN_CSV)
    }


def _load_csv(path: Path) -> list[dict[str, str]]:
    """Load a UTF-8 CSV file."""

    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _split_variants(raw_value: str, canonical: str) -> Iterable[str]:
    """Split pipe-separated variants and include the canonical form."""

    seen = {_normalize_key(canonical)}
    yield canonical
    for value in str(raw_value).split("|"):
        alias = value.strip()
        if not alias:
            continue
        key = _normalize_key(alias)
        if key in seen:
            continue
        seen.add(key)
        yield alias


def _normalize_key(value: str) -> str:
    """Normalize a district alias for stable lookup."""

    normalized = unicodedata.normalize("NFKC", value).strip().casefold()
    for character in ("-", "_", ",", ".", "/", "(", ")"):
        normalized = normalized.replace(character, " ")
    return " ".join(normalized.split())
