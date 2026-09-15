"""Tests for municipality gazetteer resources and district mapping."""

from __future__ import annotations

import csv
from pathlib import Path

from landslide_inventory.gazetteer import all_districts, municipality_to_district, normalize_municipality
from landslide_inventory.gazetteer_municipality import load_municipality_gazetteers

RESOURCE_DIR = Path(__file__).resolve().parents[1] / "resources"
EXPECTED_EN_COLUMNS = {
    "municipality_en_canonical",
    "municipality_en_variants",
    "district_canonical",
}
EXPECTED_NP_COLUMNS = {
    "municipality_en_canonical",
    "municipality_np_canonical",
    "municipality_np_variants",
    "district_canonical",
}


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def test_municipality_resource_files_exist() -> None:
    assert (RESOURCE_DIR / "municipalities_en.csv").exists()
    assert (RESOURCE_DIR / "municipalities_np.csv").exists()


def test_municipalities_en_schema_and_districts_are_valid() -> None:
    rows = _read_csv(RESOURCE_DIR / "municipalities_en.csv")
    assert rows
    assert set(rows[0]) == EXPECTED_EN_COLUMNS
    districts = set(all_districts())
    assert all(row["district_canonical"] in districts for row in rows)


def test_municipalities_np_schema_and_districts_are_valid() -> None:
    rows = _read_csv(RESOURCE_DIR / "municipalities_np.csv")
    assert rows
    assert set(rows[0]) == EXPECTED_NP_COLUMNS
    districts = set(all_districts())
    assert all(row["district_canonical"] in districts for row in rows)


def test_load_municipality_gazetteers_contains_expected_keys() -> None:
    gazetteers = load_municipality_gazetteers()
    assert "melamchi municipality" in gazetteers.en_alias_to_canonical
    assert "मेलम्ची नगरपालिका" in gazetteers.np_alias_to_canonical


def test_english_municipality_variant_resolves_to_correct_district() -> None:
    municipality = normalize_municipality("Melamchi", "en")
    assert municipality == "Melamchi Municipality"
    assert municipality_to_district(municipality) == "Sindhupalchok"


def test_nepali_municipality_variant_resolves_to_canonical_district() -> None:
    municipality = normalize_municipality("बाह्रविसे न.पा.", "np")
    assert municipality == "Barhabise Municipality"
    assert municipality_to_district(municipality) == "Sindhupalchok"


def test_unknown_municipality_returns_none() -> None:
    assert normalize_municipality("Imaginary Municipality", "en") is None
    assert normalize_municipality("काल्पनिक नगरपालिका", "np") is None


def test_mapping_returns_none_when_municipality_not_resolved() -> None:
    municipality = normalize_municipality("Not A Real Place", "en")
    assert municipality is None
    assert municipality_to_district("Not A Real Place") is None


def test_fuzzy_english_municipality_match_is_deterministic() -> None:
    municipality = normalize_municipality("Ichchakamana Rural Municipality", "en")
    assert municipality == "Ichchhyakamana Rural Municipality"


def test_abukhaireni_rural_municipality_maps_to_tanahu() -> None:
    municipality = normalize_municipality("Anbukhaireni Rural Municipality", "en")
    assert municipality == "Anbukhaireni Rural Municipality"
    assert municipality_to_district(municipality) == "Tanahu"


def test_binayi_triveni_rural_municipality_maps_to_nawalpur() -> None:
    municipality = normalize_municipality("Binayee Rural Municipality", "en")
    assert municipality == "Binayee Rural Municipality"
    assert municipality_to_district(municipality) == "Nawalpur"


def test_prefixed_nepali_municipality_string_resolves_to_canonical() -> None:
    municipality = normalize_municipality("काठमाडौंको तारकेश्वर नगरपालिका", "np")
    assert municipality == "Tarakeshwor Municipality"


def test_missing_true_municipality_entries_resolve_after_gazetteer_update() -> None:
    assert normalize_municipality("Sitganga Municipality", "en") == "Sitganga Municipality"
    assert normalize_municipality("चितवनको राप्ती नगरपालिका", "np") == "Rapti Municipality"


def test_fuzzy_municipality_match_does_not_cross_unrelated_names() -> None:
    assert normalize_municipality("Tokha Municipality", "en") == "Tokha Municipality"
    assert normalize_municipality("Sayal Rural Municipality", "en") == "Sayal Rural Municipality"


def test_nepali_ward_form_resolves_to_dilasaini_rural_municipality() -> None:
    assert normalize_municipality('डिलाशैनी–६ बांगाबगर', 'np') == 'Dilasaini Rural Municipality'


def test_every_legacy_canonical_name_still_resolves() -> None:
    """The rebuilt gazetteer must not orphan any name already in the inventory.

    Municipality strings written into the frozen v0.4.0 release use the previous
    canonical spellings. If any of them stopped resolving, that release would
    stop being reproducible.
    """

    import csv as _csv
    from pathlib import Path as _Path

    root = _Path(__file__).resolve().parents[1]
    legacy = root / "data" / "reference" / "sources" / "legacy_municipalities_en.csv"
    with legacy.open(encoding="utf-8", newline="") as handle:
        rows = list(_csv.DictReader(handle))
    unresolved = [
        row["municipality_en_canonical"]
        for row in rows
        if normalize_municipality(row["municipality_en_canonical"], "en") is None
    ]
    assert unresolved == []


def test_district_names_do_not_resolve_to_municipalities() -> None:
    """Eight districts share a name with a unit inside them.

    A bare district name must stay a district; otherwise "Ramechhap" in a
    dateline would be read as Ramechhap Municipality.
    """

    for name in ("Ramechhap", "Gorkha", "Kathmandu", "Bhaktapur", "Ilam", "Siraha"):
        assert normalize_municipality(name, "en") is None, name
    # The full form is still resolvable.
    assert normalize_municipality("Ramechhap Municipality", "en") == "Ramechhap Municipality"


def test_shared_names_refuse_to_infer_a_district() -> None:
    from landslide_inventory.gazetteer_municipality import (
        is_ambiguous_municipality,
        municipality_districts,
        municipality_to_district,
    )

    assert is_ambiguous_municipality("Godawari Municipality")
    assert municipality_to_district("Godawari Municipality") is None
    assert municipality_districts("Godawari Municipality") == ("Kailali", "Lalitpur")
    assert is_ambiguous_municipality("Kaligandaki Rural Municipality")
    assert municipality_to_district("Kaligandaki Rural Municipality") is None
    assert municipality_districts("Kaligandaki Rural Municipality") == ("Gulmi", "Syangja")
    assert municipality_to_district("Ichchhyakamana Rural Municipality") == "Chitwan"
