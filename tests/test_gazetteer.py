"""Tests for district gazetteers."""

from __future__ import annotations

from landslide_inventory.gazetteer import all_districts, district_to_province, normalize_district


def test_all_districts_has_77_entries() -> None:
    assert len(all_districts()) == 77


def test_normalize_district_supports_nepali_alias() -> None:
    assert normalize_district("सिन्धुपाल्चोक", "np") == "Sindhupalchok"


def test_normalize_district_supports_english_alias() -> None:
    assert normalize_district("Sindhupalchowk", "en") == "Sindhupalchok"


def test_district_to_province_returns_expected_province() -> None:
    assert district_to_province("Sindhupalchok") == "Bagmati"
