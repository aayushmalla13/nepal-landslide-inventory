"""Tests for best-available place extraction."""

from __future__ import annotations

import json

from landslide_inventory.nlp_en import extract_place_en
from landslide_inventory.nlp_np import extract_place_np
from landslide_inventory.unify.location import build_address_ladders


def test_english_municipality_only_populates_place_and_resolves_district() -> None:
    text = 'Heavy rain triggered a landslide in Melamchi Municipality, damaging several homes.'
    result = extract_place_en(text)
    assert result.place_admin_level == 'municipality'
    assert result.place_name_raw == 'Melamchi Municipality'
    assert result.municipality == 'Melamchi Municipality'
    assert result.district == 'Sindhupalchok'
    assert result.ward is None
    assert json.loads(result.place_candidates_json)[0] == 'Melamchi Municipality'



def test_english_district_mention_resolves_canonical_district() -> None:
    text = 'Two people died in a landslide in Sindhupalchok District after intense rainfall.'
    result = extract_place_en(text)
    assert result.place_admin_level == 'district'
    assert result.place_name_raw == 'Sindhupalchok'
    assert result.district == 'Sindhupalchok'
    assert result.municipality is None
    assert result.conf_place >= 0.7



def test_english_place_without_municipality_or_district_keeps_district_null() -> None:
    text = 'A landslide struck a hillside settlement near the river, damaging several homes.'
    result = extract_place_en(text)
    assert result.district is None



def test_nepali_ward_example_marks_ward_and_resolves_via_municipality() -> None:
    text = 'लगातार वर्षापछि मेलम्ची नगरपालिका-११ वडा क्षेत्रमा पहिरो खस्यो र बस्ती जोखिममा परेको छ।'
    result = extract_place_np(text)
    assert result.place_admin_level == 'ward'
    assert result.place_name_raw is not None
    assert 'वडा' in result.place_name_raw
    assert result.municipality == 'Melamchi Municipality'
    assert result.district == 'Sindhupalchok'
    assert result.ward is not None



def test_nepali_municipality_variant_resolves_canonical_municipality_and_district() -> None:
    text = 'बाह्रविसे नगरपालिका क्षेत्रमा पहिरो जाँदा सडक अवरुद्ध भएको छ।'
    result = extract_place_np(text)
    assert result.place_admin_level == 'municipality'
    assert result.municipality == 'Barhabise Municipality'
    assert result.district == 'Sindhupalchok'



def test_nepali_bare_district_resolves_canonical_district() -> None:
    text = 'बागलुङमा पहिरो खस्दा घर पुरिएको छ र सडक अवरुद्ध भएको छ।'
    result = extract_place_np(text)
    assert result.place_admin_level == 'district'
    assert result.district == 'Baglung'
    assert result.place_name_raw == 'बागलुङ'



def test_address_ladders_follow_the_expected_fallback_order() -> None:
    ladders = build_address_ladders(
        ward='Ward 5',
        municipality='Barhabise Municipality',
        district='Sindhupalchok',
        province='Bagmati',
    )
    assert ladders == [
        'Ward 5, Barhabise Municipality, Sindhupalchok, Nepal',
        'Barhabise Municipality, Sindhupalchok, Nepal',
        'Sindhupalchok, Nepal',
        'Bagmati, Nepal',
    ]
