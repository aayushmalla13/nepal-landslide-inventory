"""Tests for study-area scope filtering."""

from __future__ import annotations

from landslide_inventory.unify.scope_filter import ScopeRow, decide_scope


def _row(**overrides):
    base = {
        'url': 'https://example.com/article',
        'source': 'test',
        'title': 'Test',
        'text': 'Test text',
        'route_lang': 'en',
        'devanagari_ratio': 0.0,
        'district': None,
        'municipality': None,
    }
    base.update(overrides)
    return ScopeRow(**base)


def test_scope_district_present_is_in_nepal() -> None:
    decision = decide_scope(_row(district='Sindhupalchok'), 0.3)
    assert decision.in_nepal == 1
    assert decision.scope_reason == 'district_match'


def test_scope_municipality_present_is_in_nepal() -> None:
    decision = decide_scope(_row(municipality='Melamchi Municipality'), 0.3)
    assert decision.in_nepal == 1
    assert decision.scope_reason == 'municipality_match'


def test_scope_nepal_keyword_is_in_nepal() -> None:
    decision = decide_scope(_row(text='Heavy rain triggered landslides in Nepal.'), 0.3)
    assert decision.in_nepal == 1
    assert decision.scope_reason == 'nepal_keyword'


def test_scope_explicit_other_country_without_nepal_is_out() -> None:
    decision = decide_scope(_row(text='Landslides hit villages in China after heavy rain.'), 0.3)
    assert decision.in_nepal == 0
    assert decision.scope_reason == 'out_of_country'


def test_scope_global_roundup_is_out() -> None:
    decision = decide_scope(_row(text='Around the world, global disasters and landslides are increasing.'), 0.3)
    assert decision.in_nepal == 0
    assert decision.scope_reason == 'global_roundup'


def test_scope_ambiguous_without_signals_is_out() -> None:
    decision = decide_scope(_row(text='A landslide blocked a road.'), 0.3)
    assert decision.in_nepal == 0
    assert decision.scope_reason == 'no_location_signal'



def test_scope_foreign_article_with_noisy_nepal_district_is_out() -> None:
    decision = decide_scope(
        _row(
            text='Landslides and floods killed 167 people in the Philippines after Tropical Storm Megi.',
            district='Kathmandu',
        ),
        0.3,
    )
    assert decision.in_nepal == 0
    assert decision.scope_reason == 'out_of_country'



def test_scope_myrepublica_partner_suffix_does_not_force_global_roundup_for_nepal_event() -> None:
    decision = decide_scope(
        _row(
            source='myrepublica',
            title='Landslide kills five in Parbat, four still missing - myRepublica - The New York Times Partner, Latest news of Nepal in English',
            text='Subscribe Login Subscribe Politics. By Hari Krishna Gautam PARBAT, June 14: Five people were killed and four are still missing in a landslide at Durlung, Kusma Municipality-3, Parbat.',
            district='Parbat',
        ),
        0.3,
    )
    assert decision.in_nepal == 1
    assert decision.scope_reason == 'district_match'


def test_scope_myrepublica_foreign_story_with_trailing_nepal_noise_is_out() -> None:
    decision = decide_scope(
        _row(
            source='myrepublica',
            title='Floods, landslides kill 24 people in Indonesia - myRepublica - The New York Times Partner, Latest news of Nepal in English',
            text='By Associated Press JAKARTA, Indonesia, June 19: An Indonesian official says 24 people have been killed by flooding and landslides in central Java. Nepal records highest LPG imports in three months appears later as unrelated site noise.',
        ),
        0.3,
    )
    assert decision.in_nepal == 0
    assert decision.scope_reason == 'out_of_country'


def test_scope_hong_kong_story_is_out_of_country() -> None:
    decision = decide_scope(
        _row(
            source='myrepublica',
            title='Hong Kong democrats romp to local election landslide after months of protests - myRepublica - The New York Times Partner, Latest news of Nepal in English',
            text='HONG KONG, Nov 24: Hong Kong democrats secured a landslide victory in local elections after months of protests.',
        ),
        0.3,
    )
    assert decision.in_nepal == 0
    assert decision.scope_reason == 'out_of_country'


def test_scope_myrepublica_nepal_road_event_ignores_trailing_teasers() -> None:
    decision = decide_scope(
        _row(
            source='myrepublica',
            title='Road connecting Rasuwagadhi border point obstructed following landslides - myRepublica - The New York Times Partner, Latest news of Nepal in English',
            text="By Him Nath Devkota RASUWA, July 18: A road connecting the Rasuwagadhi border point has been obstructed since this morning following landslides in the Tatopanidada area along the Syafrubesi-Rasuwagadhi road. Vehicular movement has been disrupted following the rain-triggered landslides in the Tatopanidada area along the road, according to the District Police Office, Rasuwa. Rasuwagadhi is Nepal's international border point with the Tibet Autonomous Region of China. Nepal records highest LPG imports in three months. How Trump 2.0 Redefines Global Trade.",
            district='Rasuwa',
        ),
        0.3,
    )
    assert decision.in_nepal == 1
    assert decision.scope_reason == 'district_match'


def test_scope_foreign_term_word_boundary_does_not_match_inside_name() -> None:
    decision = decide_scope(
        _row(
            source='myrepublica',
            title='Siddhartha Highway blocked following landslides',
            text='By Mukti Prasad Nyaupane PALPA, July 18: The Tansen-Butwal road section of the Siddhartha Highway has been blocked following rain-triggered landslides in Tansen Municipality-8 since Thursday night.',
            district='Palpa',
        ),
        0.3,
    )
    assert decision.in_nepal == 1
    assert decision.scope_reason == 'district_match'
