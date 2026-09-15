"""Tests for unified extraction stage helpers."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from landslide_inventory.db import connect_sqlite, initialize_sqlite
from landslide_inventory.gazetteer import all_districts, district_to_province, normalize_district, normalize_municipality, municipality_to_district
from landslide_inventory.unify.extract_stage import (
    ArticleRow,
    _effective_published_year_hint,
    _reconcile_place,
    build_article_event_record,
    merge_extractor_outputs,
    upsert_article_event,
)


def test_merge_extractor_outputs_prefers_higher_confidence_fields() -> None:
    left = {
        'district': None,
        'municipality': None,
        'place_name_raw': None,
        'place_candidates_json': '[]',
        'class': 2,
        'event_date_ad': None,
        'conf_class': 0.7,
        'conf_date': 0.1,
        'conf_district': 0.0,
        'conf_place': 0.1,
        'conf_fatalities': 0.3,
        'conf_trigger': 0.2,
        'trigger': 'unknown',
    }
    right = {
        'district': 'Sindhupalchok',
        'municipality': 'Melamchi Municipality',
        'place_name_raw': 'Melamchi Municipality',
        'place_candidates_json': '["Melamchi Municipality"]',
        'class': 1,
        'event_date_ad': '2024-07-15',
        'conf_class': 0.9,
        'conf_date': 0.95,
        'conf_district': 0.82,
        'conf_place': 0.88,
        'conf_fatalities': 0.5,
        'conf_trigger': 0.9,
        'trigger': 'rainfall',
    }
    merged = merge_extractor_outputs(left, right)
    assert merged['district'] == 'Sindhupalchok'
    assert merged['municipality'] == 'Melamchi Municipality'
    assert merged['place_name_raw'] == 'Melamchi Municipality'
    assert merged['trigger'] == 'rainfall'


def test_build_article_event_record_downgrades_class_one_without_district() -> None:
    row = ArticleRow(
        url='https://example.com/article',
        source='test',
        title='Test',
        year_hint=None,
        published_date_raw='2024-07-16',
        published_date_ad='2024-07-16',
        text='test',
        route_lang='en',
        mixed_flag=False,
    )

    def fake_en(*args, **kwargs):
        return {
            'class': 1,
            'event_date_ad': '2024-07-16',
            'district': None,
            'province': None,
            'deaths': None,
            'missing': None,
            'injured': None,
            'trigger': 'rainfall',
            'municipality': None,
            'ward': None,
            'place_admin_level': 'unknown',
            'place_name_raw': None,
            'place_candidates_json': '[]',
            'conf_place': 0.1,
            'conf_class': 0.95,
            'conf_date': 0.95,
            'conf_district': 0.0,
            'conf_fatalities': 0.0,
            'conf_trigger': 0.9,
        }

    record = build_article_event_record(
        row=row,
        extracted_at='2024-07-16T00:00:00+00:00',
        keywords_cfg={},
        en_gazetteer={},
        np_gazetteer={},
        study_start=date(2015, 1, 1),
        study_end=date(2024, 12, 31),
        en_extractor=fake_en,
    )
    assert record['district'] is None
    assert record['class'] != 1




def test_build_article_event_record_enforces_study_period_and_municipality_district_consistency() -> None:
    row = ArticleRow(
        url='https://example.com/mismatch',
        source='test',
        title='Mismatch',
        year_hint=None,
        published_date_raw='2014-01-09',
        published_date_ad='2014-01-09',
        text='test',
        route_lang='en',
        mixed_flag=False,
    )

    def fake_en(*args, **kwargs):
        return {
            'class': 1,
            'event_date_ad': '2014-01-09',
            'district': 'Manang',
            'province': 'Gandaki',
            'deaths': None,
            'missing': None,
            'injured': None,
            'trigger': 'rainfall',
            'municipality': 'Melamchi Municipality',
            'ward': None,
            'place_admin_level': 'municipality',
            'place_name_raw': 'Melamchi Municipality',
            'place_candidates_json': '["Melamchi Municipality"]',
            'conf_place': 0.99,
            'conf_class': 0.95,
            'conf_date': 0.95,
            'conf_district': 0.95,
            'conf_fatalities': 0.0,
            'conf_trigger': 0.9,
        }

    record = build_article_event_record(
        row=row,
        extracted_at='2024-07-16T00:00:00+00:00',
        keywords_cfg={},
        en_gazetteer={},
        np_gazetteer={},
        study_start=date(2015, 1, 1),
        study_end=date(2024, 12, 31),
        en_extractor=fake_en,
    )
    # The record must not assert a municipality outside its own district. Since
    # 2026-08-14 that is resolved by keeping the established district and
    # dropping the contradicting municipality, rather than by moving the event
    # to the municipality's district.
    #
    # The reason is measured, not stylistic. With the 753-unit gazetteer, a
    # municipality that disagrees with an already-extracted district is usually
    # a person's home address ("the deceased ... of Chandrpur Municipality-1,
    # Rautahat" in a story about a landslide in Rasuwa), and letting it win
    # relocated events to the wrong district. The language extractors already
    # adjudicate the genuine case -- a dateline that is not the event district
    # -- before the record reaches this stage. See
    # scripts/score_district_development.py for the ablation on the labelled
    # development set.
    assert record['district'] == 'Manang'
    assert record['province'] == 'Gandaki'
    assert record['municipality'] is None
    assert record['ward'] is None
    assert record['place_admin_level'] == 'district'
    assert record['event_date_ad'] is None
    assert record['class'] == 2


def test_reconcile_place_fills_a_missing_district_from_an_unambiguous_municipality() -> None:
    """The enlarged gazetteer is allowed to *add* a district, never to move one."""

    canonical = set(all_districts())
    district, municipality, ward = _reconcile_place(
        None, 'Melamchi Municipality', 'Ward 3', canonical
    )
    assert (district, municipality, ward) == ('Sindhupalchok', 'Melamchi Municipality', 'Ward 3')


def test_reconcile_place_keeps_a_municipality_that_agrees_with_the_district() -> None:
    canonical = set(all_districts())
    assert _reconcile_place('Sindhupalchok', 'Melamchi Municipality', 'Ward 3', canonical) == (
        'Sindhupalchok',
        'Melamchi Municipality',
        'Ward 3',
    )


def test_reconcile_place_accepts_an_ambiguous_municipality_that_matches_the_district() -> None:
    """Godawari Municipality exists in both Lalitpur and Kailali."""

    canonical = set(all_districts())
    assert _reconcile_place('Lalitpur', 'Godawari Municipality', None, canonical) == (
        'Lalitpur',
        'Godawari Municipality',
        None,
    )
    assert _reconcile_place('Kailali', 'Godawari Municipality', None, canonical) == (
        'Kailali',
        'Godawari Municipality',
        None,
    )
    # With no district to disambiguate it, a shared name cannot pick one.
    assert _reconcile_place(None, 'Godawari Municipality', None, canonical) == (
        None,
        'Godawari Municipality',
        None,
    )


def test_reconcile_place_drops_a_contradicting_municipality_rather_than_moving_the_event() -> None:
    canonical = set(all_districts())
    assert _reconcile_place('Rasuwa', 'Chandrapur Municipality', 'Ward 1', canonical) == (
        'Rasuwa',
        None,
        None,
    )


def test_article_event_upsert_is_idempotent(tmp_path: Path) -> None:
    database_path = tmp_path / 'data' / 'raw_sqlite' / 'inventory.sqlite'
    initialize_sqlite(database_path)
    record = {
        'url': 'https://example.com/article',
        'source': 'test',
        'title': 'Test',
        'published_date_raw': '2024-07-16',
        'published_date_ad': '2024-07-16',
        'route_lang': 'en',
        'mixed_flag': 0,
        'class': 2,
        'event_date_ad': '2024-07-16',
        'district': 'Sindhupalchok',
        'province': 'Bagmati',
        'municipality': 'Melamchi Municipality',
        'ward': None,
        'place_admin_level': 'municipality',
        'place_name_raw': 'Melamchi Municipality',
        'place_candidates_json': '["Melamchi Municipality"]',
        'deaths': None,
        'missing': None,
        'injured': 1,
        'trigger': 'rainfall',
        'conf_class': 0.8,
        'conf_date': 0.6,
        'conf_district': 0.82,
        'conf_place': 0.88,
        'conf_fatalities': 0.92,
        'conf_trigger': 0.9,
        'extracted_at': '2024-07-16T00:00:00+00:00',
    }
    with connect_sqlite(database_path) as connection:
        upsert_article_event(connection, record)
        upsert_article_event(connection, record)
        connection.commit()
        count = connection.execute('SELECT COUNT(*) FROM article_events').fetchone()[0]
    assert count == 1


def test_build_article_event_record_downgrades_partner_retrospective_class_one() -> None:
    row = ArticleRow(
        url='https://example.com/partner',
        source='test',
        title='21 dead, 38 missing in floods and landslides in Sankhuwasabha in 10 years - The New York Times Partner',
        year_hint=None,
        published_date_raw='2024-08-08',
        published_date_ad='2024-08-08',
        text='Experts said the district has seen repeated disasters over the years.',
        route_lang='en',
        mixed_flag=False,
    )

    def fake_en(*args, **kwargs):
        return {
            'class': 1,
            'event_date_ad': '2023-06-17',
            'district': 'Sankhuwasabha',
            'province': 'Koshi',
            'deaths': 21,
            'missing': 38,
            'injured': None,
            'trigger': 'rainfall',
            'municipality': 'Silichong Rural Municipality',
            'ward': None,
            'place_admin_level': 'municipality',
            'place_name_raw': 'Silichong Rural Municipality',
            'place_candidates_json': '["Silichong Rural Municipality"]',
            'conf_place': 0.9,
            'conf_class': 0.95,
            'conf_date': 0.95,
            'conf_district': 0.95,
            'conf_fatalities': 0.9,
            'conf_trigger': 0.9,
        }

    record = build_article_event_record(
        row=row,
        extracted_at='2024-08-08T00:00:00+00:00',
        keywords_cfg={},
        en_gazetteer={},
        np_gazetteer={},
        study_start=date(2015, 1, 1),
        study_end=date(2024, 12, 31),
        en_extractor=fake_en,
    )
    assert record['class'] == 2
    assert record['district'] == 'Sankhuwasabha'


def test_build_article_event_record_promotes_specific_fallback_date_event_to_class_one() -> None:
    row = ArticleRow(
        url='https://example.com/fallback-event',
        source='test',
        title='1 dies, 8 missing in Rasuwa landslide',
        year_hint=None,
        published_date_raw='2024-08-08',
        published_date_ad='2024-08-08',
        text='A landslide in Rasuwa district left one person dead and eight missing.',
        route_lang='en',
        mixed_flag=False,
    )

    def fake_en(*args, **kwargs):
        return {
            'class': 2,
            'event_date_ad': '2024-08-08',
            'district': 'Rasuwa',
            'province': 'Bagmati',
            'deaths': 1,
            'missing': 8,
            'injured': None,
            'trigger': 'rainfall',
            'municipality': None,
            'ward': None,
            'place_admin_level': 'district',
            'place_name_raw': 'Rasuwa',
            'place_candidates_json': '["Rasuwa"]',
            'conf_place': 0.8,
            'conf_class': 0.8,
            'conf_date': 0.6,
            'conf_district': 0.95,
            'conf_fatalities': 0.9,
            'conf_trigger': 0.9,
        }

    record = build_article_event_record(
        row=row,
        extracted_at='2024-08-08T00:00:00+00:00',
        keywords_cfg={},
        en_gazetteer={},
        np_gazetteer={},
        study_start=date(2015, 1, 1),
        study_end=date(2024, 12, 31),
        en_extractor=fake_en,
    )
    assert record['class'] == 1
    assert record['event_date_ad'] == '2024-08-08'
    assert record['district'] == 'Rasuwa'



def test_build_article_event_record_keeps_displacement_only_fallback_event_as_class_two() -> None:
    row = ArticleRow(
        url='https://example.com/displaced',
        source='test',
        title='कास्कीको रिभानमा ठूलो पहिरो, १५ घर परिवार विस्थापित',
        year_hint=None,
        published_date_raw='2024-08-08',
        published_date_ad='2024-08-08',
        text='कास्कीमा ठूलो पहिरो जाँदा १५ घर परिवार विस्थापित भए।',
        route_lang='np',
        mixed_flag=False,
    )

    def fake_np(*args, **kwargs):
        return {
            'class': 2,
            'event_date_ad': '2024-08-08',
            'district': 'Kaski',
            'province': 'Gandaki',
            'deaths': None,
            'missing': None,
            'injured': None,
            'trigger': 'rainfall',
            'municipality': None,
            'ward': None,
            'place_admin_level': 'district',
            'place_name_raw': 'Kaski',
            'place_candidates_json': '["Kaski"]',
            'conf_place': 0.8,
            'conf_class': 0.8,
            'conf_date': 0.6,
            'conf_district': 0.95,
            'conf_fatalities': 0.0,
            'conf_trigger': 0.9,
        }

    record = build_article_event_record(
        row=row,
        extracted_at='2024-08-08T00:00:00+00:00',
        keywords_cfg={},
        en_gazetteer={},
        np_gazetteer={},
        study_start=date(2015, 1, 1),
        study_end=date(2024, 12, 31),
        np_extractor=fake_np,
    )
    assert record['class'] == 2


def test_build_article_event_record_keeps_followup_fallback_event_as_class_two() -> None:
    row = ArticleRow(
        url='https://example.com/followup',
        source='test',
        title='अब सिन्धुपालचोकको पहिरोमा पुरिएर बेपत्ता भएका ६ जनाको खोजी नगरिने',
        year_hint=None,
        published_date_raw='2024-08-08',
        published_date_ad='2024-08-08',
        text='सिन्धुपालचोकको पहिरोमा पुरिएर बेपत्ता भएका ६ जनाको खोजी नगरिने जनाइएको छ।',
        route_lang='np',
        mixed_flag=False,
    )

    def fake_np(*args, **kwargs):
        return {
            'class': 2,
            'event_date_ad': '2024-08-08',
            'district': 'Sindhupalchok',
            'province': 'Bagmati',
            'deaths': None,
            'missing': 6,
            'injured': None,
            'trigger': 'rainfall',
            'municipality': None,
            'ward': None,
            'place_admin_level': 'district',
            'place_name_raw': 'Sindhupalchok',
            'place_candidates_json': '["Sindhupalchok"]',
            'conf_place': 0.8,
            'conf_class': 0.8,
            'conf_date': 0.6,
            'conf_district': 0.95,
            'conf_fatalities': 0.9,
            'conf_trigger': 0.9,
        }

    record = build_article_event_record(
        row=row,
        extracted_at='2024-08-08T00:00:00+00:00',
        keywords_cfg={},
        en_gazetteer={},
        np_gazetteer={},
        study_start=date(2015, 1, 1),
        study_end=date(2024, 12, 31),
        np_extractor=fake_np,
    )
    assert record['class'] == 2


def test_build_article_event_record_keeps_specific_partner_fatal_event_as_class_one() -> None:
    row = ArticleRow(
        url='https://example.com/partner-event',
        source='test',
        title='Road worker buried to death in Gorkha landslide - The New York Times Partner',
        year_hint=None,
        published_date_raw='2024-08-08',
        published_date_ad='2024-08-08',
        text='A landslide in Gorkha district killed one road worker and injured others.',
        route_lang='en',
        mixed_flag=False,
    )

    def fake_en(*args, **kwargs):
        return {
            'class': 1,
            'event_date_ad': '2024-08-08',
            'district': 'Gorkha',
            'province': 'Gandaki',
            'deaths': 1,
            'missing': None,
            'injured': 2,
            'trigger': 'anthropogenic',
            'municipality': 'Dharche Rural Municipality',
            'ward': None,
            'place_admin_level': 'municipality',
            'place_name_raw': 'Dharche Rural Municipality',
            'place_candidates_json': '["Dharche Rural Municipality"]',
            'conf_place': 0.9,
            'conf_class': 0.95,
            'conf_date': 0.95,
            'conf_district': 0.95,
            'conf_fatalities': 0.9,
            'conf_trigger': 0.9,
        }

    record = build_article_event_record(
        row=row,
        extracted_at='2024-08-08T00:00:00+00:00',
        keywords_cfg={},
        en_gazetteer={},
        np_gazetteer={},
        study_start=date(2015, 1, 1),
        study_end=date(2024, 12, 31),
        en_extractor=fake_en,
    )
    assert record['class'] == 1
    assert record['district'] == 'Gorkha'



def test_build_article_event_record_promotes_injury_event_with_inferred_date_to_class_one() -> None:
    row = ArticleRow(
        url='https://example.com/injury-event',
        source='test',
        title='Five injured as landslide buries three vehicles in Lalitpur',
        year_hint=2020,
        published_date_raw='2020-09-24',
        published_date_ad='2020-09-24',
        text='Five people were injured after a landslide buried three vehicles in Lalitpur.',
        route_lang='en',
        mixed_flag=False,
    )

    def fake_en(*args, **kwargs):
        return {
            'class': 2,
            'event_date_ad': '2020-09-24',
            'district': 'Lalitpur',
            'province': 'Bagmati',
            'deaths': None,
            'missing': None,
            'injured': 5,
            'trigger': 'rainfall',
            'municipality': None,
            'ward': None,
            'place_admin_level': 'district',
            'place_name_raw': 'Lalitpur',
            'place_candidates_json': '["Lalitpur"]',
            'conf_place': 0.8,
            'conf_class': 0.8,
            'conf_date': 0.6,
            'conf_district': 0.95,
            'conf_fatalities': 0.9,
            'conf_trigger': 0.9,
        }

    record = build_article_event_record(
        row=row,
        extracted_at='2024-08-08T00:00:00+00:00',
        keywords_cfg={},
        en_gazetteer={},
        np_gazetteer={},
        study_start=date(2015, 1, 1),
        study_end=date(2024, 12, 31),
        en_extractor=fake_en,
    )
    assert record['class'] == 1
    assert record['district'] == 'Lalitpur'


def test_build_article_event_record_prefers_published_date_year_over_discovery_hint() -> None:
    row = ArticleRow(
        url='https://www.onlinekhabar.com/2025/08/example-story',
        source='online-khabar',
        title='Example',
        year_hint=2024,
        published_date_raw='७ भदौ, काठमाडौं',
        published_date_ad='2025-08-23',
        text='७ भदौ, काठमाडौं । पहिरो गएको छ।',
        route_lang='np',
        mixed_flag=False,
    )
    captured: dict[str, int | None] = {}

    def fake_np(*args, **kwargs):
        captured['published_year_hint'] = kwargs.get('published_year_hint')
        return {
            'class': 2,
            'event_date_ad': '2025-08-23',
            'district': 'Kathmandu',
            'province': 'Bagmati',
            'deaths': None,
            'missing': None,
            'injured': None,
            'trigger': 'rainfall',
            'municipality': 'Tokha Municipality',
            'ward': None,
            'place_admin_level': 'municipality',
            'place_name_raw': 'Tokha Municipality',
            'place_candidates_json': '["Tokha Municipality"]',
            'conf_place': 0.9,
            'conf_class': 0.8,
            'conf_date': 0.9,
            'conf_district': 0.82,
            'conf_fatalities': 0.0,
            'conf_trigger': 0.9,
        }

    build_article_event_record(
        row=row,
        extracted_at='2025-08-23T00:00:00+00:00',
        keywords_cfg={},
        en_gazetteer={},
        np_gazetteer={},
        study_start=date(2015, 1, 1),
        study_end=date(2025, 12, 31),
        np_extractor=fake_np,
    )
    assert captured['published_year_hint'] == 2025


def test_build_article_event_record_trims_noisy_nepali_preamble() -> None:
    row = ArticleRow(
        url='https://www.onlinekhabar.com/2025/07/example-story',
        source='online-khabar',
        title='चार ठाउँमा खसेको पहिरोले पासाङल्हामु राजमार्ग अवरुद्ध',
        year_hint=2024,
        published_date_raw=None,
        published_date_ad='2025-07-02',
        text='''{{data.tags[i].name}} सबै रिज्ल्ट हेर्नुस + क्रिकेट

News Summary Generated by OK AI. Editorially reviewed. गोसाइँकुण्ड गाउँपालिकाका चार ठाउँमा पहिरो खस्दा पासाङ ल्हामु राजमार्ग अवरुद्ध भएको छ। १८ असार, काठमाडौं । रसुवाको गोसाइँकुण्ड गाउँपालिकाका चार ठाउँमा पहिरो खस्दा पासाङ ल्हामु राजमार्ग अवरुद्ध भएको छ ।''',
        route_lang='np',
        mixed_flag=False,
    )
    record = build_article_event_record(
        row=row,
        extracted_at='2025-07-02T00:00:00+00:00',
        keywords_cfg={
            'terms': {'np': ['पहिरो', 'भूस्खलन'], 'en': ['landslide']},
            'exclude': {'np': [], 'en': []},
            'trigger_terms': {'rainfall': {'np': ['वर्षा'], 'en': ['rain']}},
            'casualty_terms': {'deaths': {'np': ['मृत्यु'], 'en': ['dead']}, 'missing': {'np': ['बेपत्ता'], 'en': ['missing']}, 'injured': {'np': ['घाइते'], 'en': ['injured']}},
        },
        en_gazetteer={
            'normalize_district': lambda name: normalize_district(name, 'en'),
            'normalize_municipality': lambda name: normalize_municipality(name, 'en'),
            'municipality_to_district': municipality_to_district,
            'district_to_province': district_to_province,
        },
        np_gazetteer={
            'normalize_district': lambda name: normalize_district(name, 'np'),
            'normalize_municipality': lambda name: normalize_municipality(name, 'np'),
            'municipality_to_district': municipality_to_district,
            'district_to_province': district_to_province,
        },
        study_start=date(2015, 1, 1),
        study_end=date(2025, 12, 31),
    )
    assert record['class'] in (1, 2)
    assert record['district'] == 'Rasuwa'
    assert record['event_date_ad'] == '2025-07-02'



def test_build_article_event_record_trims_myrepublica_title_suffix_before_extraction() -> None:
    row = ArticleRow(
        url='https://example.com/myrepublica-story',
        source='myrepublica',
        title='Landslide kills five in Parbat, four still missing - myRepublica - The New York Times Partner, Latest news of Nepal in English',
        year_hint=2020,
        published_date_raw='2020-06-14',
        published_date_ad='2020-06-14',
        text='Subscribe Login Subscribe Politics Economy Society. By Hari Krishna Gautam PARBAT, June 14: Five people were killed and four are still missing in a landslide.',
        route_lang='en',
        mixed_flag=False,
    )
    captured = {}

    def fake_en(title, text, *args, **kwargs):
        captured['title'] = title
        captured['text'] = text
        return {
            'class': 2,
            'event_date_ad': '2020-06-13',
            'district': 'Parbat',
            'province': 'Gandaki',
            'deaths': 5,
            'missing': 4,
            'injured': None,
            'trigger': 'rainfall',
            'municipality': 'Kushma Municipality',
            'ward': None,
            'place_admin_level': 'municipality',
            'place_name_raw': 'Kushma Municipality',
            'place_candidates_json': '["Kushma Municipality"]',
            'conf_place': 0.9,
            'conf_class': 0.8,
            'conf_date': 0.88,
            'conf_district': 0.95,
            'conf_fatalities': 0.9,
            'conf_trigger': 0.9,
        }

    build_article_event_record(
        row=row,
        extracted_at='2020-06-14T00:00:00+00:00',
        keywords_cfg={},
        en_gazetteer={},
        np_gazetteer={},
        study_start=date(2015, 1, 1),
        study_end=date(2024, 12, 31),
        en_extractor=fake_en,
    )
    assert 'The New York Times Partner' not in captured['title']
    assert captured['text'].startswith('Landslide kills five in Parbat, four still missing')
    assert 'Subscribe Login Subscribe' not in captured['text']



def test_build_article_event_record_promotes_strong_body_driven_class_three_to_class_one() -> None:
    row = ArticleRow(
        url='https://example.com/mehele-story',
        source='myrepublica',
        title='Search operation underway to trace the whereabouts of three missing in Mehele landslide - myRepublica - The New York Times Partner',
        year_hint=2023,
        published_date_raw='2023-06-20',
        published_date_ad='2023-06-20',
        text='By Republica TAPLEJUNG, June 20: Search for those missing in the landslide that occurred at Mehele of Sidingba rural municipality-6 in Taplejung on Saturday night is underway. Of them, one was found dead on Sunday morning while three members of a single family are still missing.',
        route_lang='en',
        mixed_flag=False,
    )

    def fake_en(*args, **kwargs):
        return {
            'class': 3,
            'event_date_ad': '2023-06-17',
            'district': 'Taplejung',
            'province': 'Koshi',
            'deaths': None,
            'missing': 3,
            'injured': None,
            'trigger': 'unknown',
            'municipality': None,
            'ward': None,
            'place_admin_level': 'district',
            'place_name_raw': 'Taplejung',
            'place_candidates_json': '["Taplejung"]',
            'conf_place': 0.95,
            'conf_class': 0.7,
            'conf_date': 0.88,
            'conf_district': 0.95,
            'conf_fatalities': 0.9,
            'conf_trigger': 0.3,
        }

    record = build_article_event_record(
        row=row,
        extracted_at='2023-06-20T00:00:00+00:00',
        keywords_cfg={},
        en_gazetteer={},
        np_gazetteer={},
        study_start=date(2015, 1, 1),
        study_end=date(2024, 12, 31),
        en_extractor=fake_en,
    )
    assert record['class'] == 1


def test_build_article_event_record_does_not_double_count_title_when_prepared_text_repeats_it() -> None:
    row = ArticleRow(
        url='https://example.com/baglung-story',
        source='myrepublica',
        title='Seven houses buried in landslides in Baglung, one dead - myRepublica - The New York Times Partner',
        year_hint=2020,
        published_date_raw='2020-08-06',
        published_date_ad='2020-08-06',
        text='By Republica BAGLUNG, Aug 6: A landslide has buried four houses and claimed one life in Badigad Rural Municipality-9 in Baglung district. Another landslide buried three houses in Darling, Badigad Rural Municipality-10.',
        route_lang='en',
        mixed_flag=False,
    )

    record = build_article_event_record(
        row=row,
        extracted_at='2020-08-06T00:00:00+00:00',
        keywords_cfg={
            'terms': {'en': ['landslide', 'mudslide', 'rockfall'], 'np': ['पहिरो', 'भूस्खलन']},
            'exclude': {'en': ['political landslide', 'electoral landslide'], 'np': []},
            'trigger_terms': {
                'rainfall': {'en': ['rain', 'rainfall', 'monsoon'], 'np': ['वर्षा']},
                'earthquake': {'en': ['earthquake', 'tremor'], 'np': ['भूकम्प']},
                'road_construction': {'en': ['road expansion', 'construction', 'excavator'], 'np': []},
            },
            'casualty_terms': {
                'deaths': {'en': ['killed', 'dead', 'deaths'], 'np': ['मृत्यु']},
                'missing': {'en': ['missing', 'disappeared'], 'np': ['बेपत्ता']},
                'injured': {'en': ['injured', 'hurt', 'wounded'], 'np': ['घाइते']},
            },
        },
        en_gazetteer={
            'normalize_district': lambda name: normalize_district(name, 'en'),
            'normalize_municipality': lambda name: normalize_municipality(name, 'en'),
            'municipality_to_district': municipality_to_district,
            'district_to_province': district_to_province,
        },
        np_gazetteer={
            'normalize_district': lambda name: normalize_district(name, 'np'),
            'normalize_municipality': lambda name: normalize_municipality(name, 'np'),
            'municipality_to_district': municipality_to_district,
            'district_to_province': district_to_province,
        },
        study_start=date(2015, 1, 1),
        study_end=date(2024, 12, 31),
    )
    assert record['deaths'] == 1
    assert record['district'] == 'Baglung'


def test_build_article_event_record_does_not_promote_road_disruption_fallback_without_human_impact() -> None:
    row = ArticleRow(
        url='https://example.com/dunai-story',
        source='myrepublica',
        title='Dunai in dark as landslide breaks hydropower canal',
        year_hint=2018,
        published_date_raw='2018-09-06',
        published_date_ad='2018-09-06',
        text='By Republica DOLPA, Sept 6: Dunai has gone dark after a landslide broke a hydropower canal and disrupted supply.',
        route_lang='en',
        mixed_flag=False,
    )

    def fake_en(*args, **kwargs):
        return {
            'class': 3,
            'event_date_ad': '2018-09-06',
            'district': 'Dolpa',
            'province': 'Karnali',
            'deaths': None,
            'missing': None,
            'injured': None,
            'trigger': 'unknown',
            'municipality': 'Thuli Bheri Municipality',
            'ward': None,
            'place_admin_level': 'municipality',
            'place_name_raw': 'Dunai',
            'place_candidates_json': '["Dunai"]',
            'conf_place': 0.9,
            'conf_class': 0.7,
            'conf_date': 0.85,
            'conf_district': 0.9,
            'conf_fatalities': 0.0,
            'conf_trigger': 0.3,
        }

    record = build_article_event_record(
        row=row,
        extracted_at='2018-09-06T00:00:00+00:00',
        keywords_cfg={},
        en_gazetteer={},
        np_gazetteer={},
        study_start=date(2015, 1, 1),
        study_end=date(2024, 12, 31),
        en_extractor=fake_en,
    )
    assert record['class'] != 1


def test_prepare_extraction_text_preserves_full_bs_year_in_setopati_followup() -> None:
    from landslide_inventory.unify.extract_stage import _prepare_extraction_text

    text = (
        "पहिरो आएकोे एक वर्षपछि बल्ल फलाम गाडेर जस्ताले घेरिएको अस्थायी आवासमा बस्न पाउँदा निशामाई तामाङ खुसी भएकी छन्। "
        "जुगल गाउँपालिका-२ गोल्चेको लिदीमा २०७७ साउन ३० गते बिहान ६ः३० बजे खसेको पहिरोमा घरबास गुमाएका ३१ परिवारलाई एक वर्षपछि अस्थायी आवासमा सारिएको हो।"
    )

    prepared = _prepare_extraction_text(
        "setopati",
        "पहिरोले श्रीमानसहित आठ सदस्य गुमाएकी निशामाईलाई अस्थायी आवासको मल्हमपट्टि",
        text,
    )

    assert "२०७७ साउन ३० गते" in prepared


def test_prepare_extraction_text_trims_parenthesized_myrepublica_dateline() -> None:
    from landslide_inventory.unify.extract_stage import _prepare_extraction_text

    text = (
        "Subscribe Login Subscribe Politics Economy Society World. "
        "By Republica MADHYABINDU (NAWALPARASI), Aug 14: The Narayanghat-Butwal road section along the East-West Highway has been obstructed."
    )

    prepared = _prepare_extraction_text(
        "myrepublica",
        "Landslide disrupts Narayanghat-Butwal road - myRepublica - The New York Times Partner",
        text,
    )

    assert prepared.startswith("Landslide disrupts Narayanghat-Butwal road\nMADHYABINDU (NAWALPARASI), Aug 14:")
    assert "Subscribe Login Subscribe" not in prepared



def test_effective_published_year_hint_coerces_string_discovered_year() -> None:
    assert _effective_published_year_hint(None, '2023') == 2023
    assert _effective_published_year_hint(None, 'bad') is None
