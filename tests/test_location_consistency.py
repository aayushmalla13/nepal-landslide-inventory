"""Tests for the location-consistency validation stage."""

from __future__ import annotations

from landslide_inventory.unify.location_consistency import LocationCheckRow, decide_location_consistency


def _fake_en_factory(result):
    def _fake(*args, **kwargs):
        return result
    return _fake


def test_title_district_conflict_downgrades_and_clears_wrong_municipality() -> None:
    row = LocationCheckRow(
        url='https://example.com/conflict',
        source='setopati',
        title='रोल्पामा पहिरोले पुर्दा ६ जनाको मृत्यु',
        text='...',
        route_lang='np',
        published_date_ad='2020-09-14',
        event_class=1,
        district='Mustang',
        municipality='Thasang Rural Municipality',
        province='Gandaki',
    )
    decision = decide_location_consistency(
        row=row,
        keywords_cfg={},
        en_gazetteer={},
        np_gazetteer={},
        np_extractor=_fake_en_factory({'district': 'Rolpa', 'municipality': None}),
    )
    assert decision.location_consistent == 0
    assert decision.location_reason == 'title_district_conflict'
    assert decision.updated_district == 'Rolpa'
    assert decision.updated_municipality is None
    assert decision.updated_class == 2


def test_title_municipality_conflict_prefers_title_municipality() -> None:
    row = LocationCheckRow(
        url='https://example.com/conflict-2',
        source='myrepublica',
        title='Melamchi Municipality hit by landslide',
        text='...',
        route_lang='en',
        published_date_ad='2023-07-10',
        event_class=1,
        district='Manang',
        municipality=None,
        province='Gandaki',
    )
    decision = decide_location_consistency(
        row=row,
        keywords_cfg={},
        en_gazetteer={},
        np_gazetteer={},
        en_extractor=_fake_en_factory({'district': 'Sindhupalchok', 'municipality': 'Melamchi Municipality'}),
    )
    assert decision.location_consistent == 0
    assert decision.location_reason == 'title_municipality_conflict'
    assert decision.updated_district == 'Sindhupalchok'
    assert decision.updated_municipality == 'Melamchi Municipality'
    assert decision.updated_class == 2


def test_matching_title_location_is_left_consistent() -> None:
    row = LocationCheckRow(
        url='https://example.com/match',
        source='himalayan-times',
        title='Landslide kills two in Dhading',
        text='...',
        route_lang='en',
        published_date_ad='2024-07-16',
        event_class=1,
        district='Dhading',
        municipality=None,
        province='Bagmati',
    )
    decision = decide_location_consistency(
        row=row,
        keywords_cfg={},
        en_gazetteer={},
        np_gazetteer={},
        en_extractor=_fake_en_factory({'district': 'Dhading', 'municipality': None}),
    )
    assert decision.location_consistent == 1
    assert decision.location_reason == 'title_match'
    assert decision.updated_district == 'Dhading'
    assert decision.updated_class is None
