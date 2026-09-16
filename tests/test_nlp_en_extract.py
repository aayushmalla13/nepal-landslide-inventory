"""Tests for English event extraction."""

from __future__ import annotations

from landslide_inventory.nlp_en.extract import extract_en

KEYWORDS_CFG = {
    'terms': {'en': ['landslide', 'mudslide', 'rockfall']},
    'exclude': {'en': ['political landslide', 'electoral landslide']},
    'trigger_terms': {
        'rainfall': {'en': ['rain', 'rainfall', 'monsoon']},
        'earthquake': {'en': ['earthquake', 'tremor']},
        'road_construction': {'en': ['road expansion', 'construction', 'excavator']},
    },
    'casualty_terms': {
        'deaths': {'en': ['killed', 'dead', 'deaths']},
        'missing': {'en': ['missing', 'disappeared']},
        'injured': {'en': ['injured', 'hurt', 'wounded']},
    },
}


def test_extract_en_explicit_district_case() -> None:
    result = extract_en(
        'Landslide kills two in Sindhupalchok',
        'Two people were killed in a landslide in Sindhupalchok District on July 12, 2023 after heavy rain.',
        '2023-07-13',
        None,
        KEYWORDS_CFG,
    )
    assert result['class'] == 1
    assert result['district'] == 'Sindhupalchok'
    assert result['event_date_ad'] == '2023-07-12'
    assert result['deaths'] == 2
    assert result['trigger'] == 'rainfall'
    assert result['conf_district'] >= 0.9


def test_extract_en_municipality_only_infers_district() -> None:
    result = extract_en(
        None,
        'A landslide struck Melamchi Municipality after monsoon rain, leaving one person injured.',
        '2024-08-01',
        None,
        KEYWORDS_CFG,
    )
    assert result['municipality'] == 'Melamchi Municipality'
    assert result['district'] == 'Sindhupalchok'
    assert result['class'] == 2
    assert result['place_admin_level'] == 'municipality'
    assert result['conf_district'] < 0.95


def test_extract_en_ward_case_preserves_ward() -> None:
    result = extract_en(
        None,
        'A landslide damaged houses in Ward 5 of Melamchi Municipality after heavy rain on July 15, 2024.',
        '2024-07-16',
        None,
        KEYWORDS_CFG,
    )
    assert result['ward'] == 'Ward 5'
    assert result['municipality'] == 'Melamchi Municipality'
    assert result['district'] == 'Sindhupalchok'
    assert result['place_admin_level'] == 'ward'


def test_extract_en_date_fallback_reduces_confidence() -> None:
    result = extract_en(
        'Landslide blocks road',
        'A landslide blocked the road in Melamchi Municipality after rain.',
        '2024-07-16',
        None,
        KEYWORDS_CFG,
    )
    assert result['event_date_ad'] == '2024-07-16'
    assert result['conf_date'] == 0.6
    assert result['class'] == 2



def test_extract_en_uses_year_hint_for_month_day_articles() -> None:
    result = extract_en(
        'Two buried to death in landslide in Sankhuwasabha',
        'Kimathanka, June 1 (RSS): Two people were buried to death in a landslide in Sankhuwasabha district today morning.',
        '2026-04-01',
        None,
        KEYWORDS_CFG,
        published_year_hint=2022,
    )
    assert result['event_date_ad'] == '2022-06-01'
    assert result['deaths'] == 2
    assert result['class'] == 1


def test_extract_en_infers_previous_day_from_last_night() -> None:
    result = extract_en(
        'Landslide kills one in Kaski',
        'A landslide last night killed one person in Kaski district.',
        '2024-07-16',
        None,
        KEYWORDS_CFG,
    )
    assert result['event_date_ad'] == '2024-07-15'
    assert result['class'] == 1



def test_extract_en_last_night_overrides_leadline_publish_day() -> None:
    result = extract_en(
        'Two persons of a single family missing in Taplejung landslide',
        'Taplejung, June 17 (RSS): Two persons of a family have gone missing in a landslide that occurred last night in Taplejung district.',
        '2026-04-01',
        None,
        KEYWORDS_CFG,
        published_year_hint=2022,
    )
    assert result['event_date_ad'] == '2022-06-16'
    assert result['class'] == 1


def test_extract_en_ignores_late_page_noise_for_dates() -> None:
    result = extract_en(
        'Five injured as landslide buries three vehicles in Lalitpur',
        'KATHMANDU, Sep 24: Five persons were injured as a landslide buried three vehicles in Lalitpur district on Thursday morning. Other teaser text mentions March 31 much later in the page.',
        '2020-09-24',
        None,
        KEYWORDS_CFG,
    )
    assert result['event_date_ad'] == '2020-09-24'



def test_extract_en_supports_abbreviated_month_names() -> None:
    result = extract_en(
        'Five injured as landslide buries three vehicles in Lalitpur',
        'KATHMANDU, Sep 24: Five persons were injured as a landslide buried three vehicles in Lalitpur district on Thursday morning.',
        None,
        None,
        KEYWORDS_CFG,
        published_year_hint=2020,
    )
    assert result['event_date_ad'] == '2020-09-24'


def test_extract_en_second_sentence_since_last_night_shifts_date() -> None:
    result = extract_en(
        'Landslide obstructs Narayangarh-Muglin road',
        'Muglin, June 9 (RSS): The road has been disrupted due to landslides. The landslide occurred near Topekhola in Chitwan and obstructed traffic since last night.',
        '2026-04-01',
        None,
        KEYWORDS_CFG,
        published_year_hint=2022,
    )
    assert result['event_date_ad'] == '2022-06-08'


def test_extract_en_source_trim_enables_weekday_backshift_for_myrepublica_style_lead() -> None:
    result = extract_en(
        'Landslide kills five in Parbat, four still missing - myRepublica - The New York Times Partner',
        'Subscribe Login Subscribe Politics Economy Society World. By Hari Krishna Gautam PARBAT, June 14: Five people were killed and four are still missing in a landslide at Durlung, Kusma Municipality-3, Parbat. Three bodies were found buried in the landslide debris after the incident on Saturday evening.',
        '2020-06-14',
        None,
        KEYWORDS_CFG,
        published_year_hint=2020,
    )
    assert result['event_date_ad'] == '2020-06-13'
    assert result['district'] == 'Parbat'


def test_extract_en_preserves_myrepublica_preamble_casualty_blurb_before_dateline() -> None:
    result = extract_en(
        'PHOTOS: Speaker Sapkota visits landslide-hit Lidi',
        'Subscribe Login Subscribe Politics Economy Society World. By Republica 4 killed, 34 still missing\n\nKATHMANDU, Aug 14: Speaker of the House of Representatives visited the landslide-hit site at Lidi in Sindhupalchowk. The rain-triggered landslide that occurred at 6 AM on Friday killed at least four people while 34 others have gone missing. Vice-chairperson of Jugal Rural Municipality shared that 15 people were injured in the landslide.',
        '2020-08-14',
        None,
        KEYWORDS_CFG,
        published_year_hint=2020,
    )
    assert result['deaths'] == 4
    assert result['missing'] == 34
    assert result['injured'] == 15
    assert result['district'] == 'Sindhupalchok'


def test_extract_en_claimed_one_life_phrase_sets_single_death() -> None:
    result = extract_en(
        'Seven houses buried in landslides in Baglung, one dead',
        'BAGLUNG, Aug 6: A landslide has buried four houses and claimed one life in Badigad Rural Municipality-9 in Baglung district. Another landslide buried three houses in Darling.',
        '2020-08-06',
        None,
        KEYWORDS_CFG,
        published_year_hint=2020,
    )
    assert result['deaths'] == 1
    assert result['district'] == 'Baglung'


def test_extract_en_recovers_rasuwa_location_even_with_nuwakot_dateline() -> None:
    result = extract_en(
        'Four bodies recovered from landslide debris',
        'By Republica NUWAKOT, August 9: The bodies of four persons missing under the landslide debris at Pairebensi of Uttargaya rural municipality – 4, Rasuwa have been recovered. The bodies of the rest were recovered on Monday.',
        '2017-08-09',
        None,
        KEYWORDS_CFG,
        published_year_hint=2017,
    )
    assert result['district'] == 'Rasuwa'
    assert result['municipality'] == 'Uttargaya Rural Municipality'
    assert result['deaths'] == 4


def test_extract_en_recovers_split_doramba_shailung_municipality() -> None:
    result = extract_en(
        'Ramechhap landslide: six dead bodies found, four missing',
        'KATHMANDU, Aug 25: The bodies of six people who had gone missing in a landslide that occurred in Lekhark, Doramba, Shailung-3, Ramechhap, have been found. Four people are still missing in the landslide. Meanwhile, the Charikot-Manthali road section along the Pushpalal Highway has been blocked due to flooding.',
        '2024-08-25',
        None,
        KEYWORDS_CFG,
        published_year_hint=2024,
    )
    assert result['municipality'] == 'Doramba Rural Municipality'
    assert result['district'] == 'Ramechhap'
    assert result['trigger'] == 'unknown'


def test_extract_en_panchthar_risk_story_backshifts_since_tuesday_night_start_and_stays_class_two() -> None:
    result = extract_en(
        'Six settlements in Panchthar face landslide risk - myRepublica - The New York Times Partner',
        'PHIDIM, June 26: Six settlements at Phalaincha, Yangwarak rural municipality-2 in Panchthar district are facing landslide risk following incessant rain. Chair of the rural municipality said that the landslide occurred in the area since Tuesday night following heavy downpour. A local house was washed away and dozens of houses are damaged by the landslide.',
        '2019-06-26',
        None,
        KEYWORDS_CFG,
        published_year_hint=2019,
    )
    assert result['event_date_ad'] == '2019-06-25'
    assert result['class'] == 2
    assert result['district'] == 'Panchthar'
    assert result['municipality'] == 'Yangwarak Rural Municipality'


def test_extract_en_kaligandaki_ongoing_rains_sentence_does_not_backshift_without_standalone_raining_clause() -> None:
    result = extract_en(
        'Landslide blocks Kaligandaki corridor',
        'BAGLUNG, July 23: The Baglung-Kaligandaki Corridor has been rendered impassable by landslides triggered by relentless rainfall. Ongoing rains since Monday evening have caused disruptions in Baglung Municipality-10 Dablyang along the corridor.',
        '2024-07-23',
        None,
        KEYWORDS_CFG,
        published_year_hint=2024,
    )
    assert result['event_date_ad'] == '2024-07-23'


def test_extract_en_kaligandaki_rain_since_tuesday_evening_backshifts_one_day() -> None:
    result = extract_en(
        'Landslide blocks Kaligandaki corridor',
        'BAGLUNG, July 31: The Kaligandaki Corridor has been blocked due to landslides triggered by incessant rainfall. It has been raining since Tuesday evening. The road was blocked due to a landslide that occurred at Dablyang, Baglung Municipality-10 of the corridor.',
        '2024-07-31',
        None,
        KEYWORDS_CFG,
        published_year_hint=2024,
    )
    assert result['event_date_ad'] == '2024-07-30'
    assert result['trigger'] == 'rainfall'


def test_extract_en_ramechhap_recovered_bodies_story_keeps_trigger_unknown_when_flooding_is_separate_update() -> None:
    result = extract_en(
        'Ramechhap landslide: six dead bodies found, four missing',
        'KATHMANDU, Aug 25: The bodies of six people who had gone missing in a landslide that occurred in Lekhark, Doramba, Shailung-3, Ramechhap, have been found. Four people are still missing in the landslide. However, Anjana Pahari was rescued safely from last night\'s landslide. Meanwhile, the Charikot-Manthali road section along the Pushpalal Highway has been blocked due to flooding.',
        '2024-08-25',
        None,
        KEYWORDS_CFG,
        published_year_hint=2024,
    )
    assert result['trigger'] == 'unknown'


def test_extract_en_ongoing_since_tuesday_story_keeps_dateline_day_for_dunai_case() -> None:
    result = extract_en(
        'Dunai in dark as landslide breaks hydropower canal',
        'JAJARKOT, Sept 6: Jajarkot district headquarters, Dunai Bazaar, has been in dark after the landslide disrupted supply of power generated from Jairigad Hydropower Project. Locals have been compelled to live in dark since Tuesday when the landslide swept away certain portion of the canal associated to the hydropower project on Tuesday.',
        '2018-09-06',
        None,
        KEYWORDS_CFG,
        published_year_hint=2018,
    )
    assert result['event_date_ad'] == '2018-09-06'


def test_extract_en_does_not_mark_rescue_excavator_story_as_anthropogenic() -> None:
    result = extract_en(
        'Four bodies recovered from landslide debris',
        'NUWAKOT, August 9: The body was found after a rescue team removed the rubble by using an excavator after a landslide on Sunday night.',
        '2017-08-09',
        None,
        KEYWORDS_CFG,
        published_year_hint=2017,
    )
    assert result['trigger'] != 'anthropogenic'


def test_extract_en_falls_back_to_explicit_municipality_in_body() -> None:
    result = extract_en(
        'Search operation underway to trace the whereabouts of three missing in Mehele landslide',
        'TAPLEJUNG, June 20: Search for those missing in the landslide that occurred at Mehele of Sidingba rural municipality-6 in Taplejung on Saturday night is underway.',
        '2023-06-20',
        None,
        KEYWORDS_CFG,
        published_year_hint=2023,
    )
    assert result['municipality'] == 'Sidingba Rural Municipality'
    assert result['district'] == 'Taplejung'


def test_extract_en_infers_two_deaths_from_family_pair_dead_phrase() -> None:
    result = extract_en(
        'Search operation underway to trace the whereabouts of three missing in Mehele landslide',
        'TAPLEJUNG, June 20: Keshar Bahadur Rai and his son were found dead in a landslide on Sunday morning.',
        '2023-06-20',
        None,
        KEYWORDS_CFG,
        published_year_hint=2023,
    )
    assert result['deaths'] == 2


def test_extract_en_keeps_trigger_unknown_when_rain_is_only_background_context() -> None:
    result = extract_en(
        '6 missing, including 5 of the same family, in landslide in Tilagufa',
        'KALIKOT, Oct 9: Five members from the same family went missing after a landslide swept away houses in Tilagufa Municipality-7. Police said that it was difficult to search for the missing persons due to continuous rain for the last five days.',
        '2022-10-09',
        None,
        KEYWORDS_CFG,
        published_year_hint=2022,
    )
    assert result['trigger'] == 'unknown'


def test_extract_en_full_tilagufa_story_keeps_trigger_unknown_when_rain_is_only_search_and_background_context() -> None:
    result = extract_en(
        '6 missing, including 5 of the same family, in landslide in Tilagufa',
        'KALIKOT, Oct 9: Five members from the same family went missing after a landslide that occurred in Baligaun, Tilagufa Municipality-7 of Kalikot district swept away by landslide. Police said that it was difficult to search for the missing persons due to continuous rain for the last five days. The incessant rainfall for the past few days has affected normal life in Kalikot. Karnali Highway and Karnali Corridor are blocked due to landslides. Roads have collapsed due to the rains and a number of houses have been destroyed.',
        '2022-10-09',
        None,
        KEYWORDS_CFG,
        published_year_hint=2022,
    )
    assert result['trigger'] == 'unknown'


def test_extract_en_flood_and_landslide_companion_context_sets_rainfall_trigger() -> None:
    result = extract_en(
        'Landslides and floods obstruct three road sections in Manang',
        'KATHMANDU, Aug 16: Landslides and floods have obstructed Pishang, Chameko Koto, and Timang Khola road sections in Dishyang-1. Floods in Pisang Khola of Dishyang rural municipality damaged the wooden bridge as a result of which the road-sections were blocked. Similarly, the landslide hit the road in Koto of Chame ward.',
        '2018-08-16',
        None,
        KEYWORDS_CFG,
        published_year_hint=2018,
    )
    assert result['trigger'] == 'rainfall'


def test_extract_en_cumulative_pyuthan_toll_story_sets_rainfall_trigger_from_flood_landslide_context() -> None:
    result = extract_en(
        'Death toll in Pyuthan landslides reaches 24',
        'PYUTHAN, July 27: The death toll from landslides that hit the district has climbed to 24 after seven more persons died in a landslide on Wednesday. According to police, 20 persons are still missing in landslides and floods across the district.',
        '2016-07-27',
        None,
        KEYWORDS_CFG,
        published_year_hint=2016,
    )
    assert result['trigger'] == 'rainfall'


def test_extract_en_uses_non_kathmandu_lead_district_when_dateline_is_desk_city() -> None:
    result = extract_en(
        'Landslides and floods obstruct three road sections in Manang',
        'KATHMANDU, Aug 16: Landslides and floods have obstructed Pishang, Chameko Koto, and Timang Khola road sections in Dishyang-1. Floods in Pisang Khola of Dishyang rural municipality damaged the wooden bridge as a result of which the road-sections were blocked.',
        '2018-08-16',
        None,
        KEYWORDS_CFG,
        published_year_hint=2018,
    )
    assert result['district'] == 'Manang'
    assert result['class'] == 2




def test_extract_en_prefers_event_district_over_destination_district_in_road_story() -> None:
    result = extract_en(
        'Landslide obstructs mid-hill highway',
        'Balewa, July 5 : The landslide caused by incessant rainfall here has obstructed the Baglung-Ghodabandhe section of the mid-hill highway since last night. The landslide occurred near Boke gully, the border of Baglung Municipality and Kathekhola Rural Municipality. The movement of vehicles on long and short routes has been disrupted. Connection to seven local levels in the western belt of the district has been lost due to road obstruction. Similarly, the vehicles heading to Rukum and Rolpa are also stranded.',
        '2026-04-01',
        None,
        KEYWORDS_CFG,
        published_year_hint=2022,
    )
    assert result['district'] == 'Baglung'
    assert result['event_date_ad'] == '2022-07-04'
    assert result['class'] == 2

def test_extract_en_road_disruption_titles_stay_class_two_without_human_impact() -> None:
    result = extract_en(
        'Siddhartha Highway blocked following landslides',
        'PALPA, July 18: The Tansen-Butwal road section of the Siddhartha Highway has been blocked following rain-triggered landslides in the Gaudepul area in Tansen Municipality-8 since Thursday night. No human casualty has been reported.',
        '2020-07-18',
        None,
        KEYWORDS_CFG,
        published_year_hint=2020,
    )
    assert result['class'] == 2
    assert result['district'] == 'Palpa'
    assert result['municipality'] == 'Tansen Municipality'


def test_extract_en_myrepublica_karnali_story_prefers_dateline_over_traveler_origin() -> None:
    result = extract_en(
        'Landslide blocks Karnali Highway',
        'Subscribe Login Subscribe Politics Economy Society. By Republica KALIKOT, June 13: Karnali Highway has been blocked due to landslides triggered by heavy rainfalls on Tuesday night. Road blockade has hit the passengers travelling from and to Surkhet, Nepalgunj, Kalikot, Jumla since this morning. Dipendra Upadhyaya of Jumla, Kankasundari-5, says the travelers have to face obstruction time to time due to negligence on the part of the government.',
        '2018-06-13',
        None,
        KEYWORDS_CFG,
        published_year_hint=2018,
    )
    assert result['district'] == 'Kalikot'
    assert result['municipality'] is None
    assert result['class'] == 2


def test_extract_en_dateline_district_beats_route_destination_mentions() -> None:
    result = extract_en(
        'Jai Prithvi Highway blocked due to landslide',
        'BAITADI, June 25: The Jai Prithvi Highway has been blocked since last night due to the landslide triggered by incessant rainfall. Passengers going to Bajhang via Baitadi and leaving Bajhang to other districts are stranded.',
        '2023-06-25',
        None,
        KEYWORDS_CFG,
        published_year_hint=2023,
    )
    assert result['district'] == 'Baitadi'
    assert result['class'] == 2


def test_extract_en_malikarjun_rural_municipality_maps_to_darchula() -> None:
    result = extract_en(
        'Landslide blocks Mahakali Highway',
        'DARCHULA, Aug 28: The Gokuleshwar-Khalanga road section of the Mahakali Highway has been blocked due to dry landslides that occurred along the road at Dhamigada, Malikarjun Rural Municipality-8, Melkhet, on Wednesday morning.',
        '2024-08-28',
        None,
        KEYWORDS_CFG,
        published_year_hint=2024,
    )
    assert result['district'] == 'Darchula'
    assert result['municipality'] == 'Malikaarjun Rural Municipality'
    assert result['trigger'] == 'unknown'
    assert result['class'] == 2


def test_extract_en_cumulative_death_toll_updates_stay_class_two_and_keep_same_day_anchor() -> None:
    result = extract_en(
        'Death toll in Pyuthan landslides reaches 24',
        'PYUTHAN, July 27: The death toll from landslides that hit the district has climbed to 24 after seven more persons died in a landslide on Wednesday. 17 persons were confirmed dead till yesterday afternoon. Seven persons were killed at Fopli-6 after the landslide buried their houses this morning.',
        '2016-07-27',
        None,
        KEYWORDS_CFG,
        published_year_hint=2016,
    )
    assert result['class'] == 2
    assert result['event_date_ad'] == '2016-07-27'


def test_extract_en_lost_their_lives_phrase_sets_deaths_and_weekday_backshift() -> None:
    result = extract_en(
        'Landslides wreak havoc, claim 3 in Lamjung',
        'LAMJUNG, Sept 13: Three people lost their lives due to landslides triggered by incessant rains in Lamjung district on Wednesday. The deceased have been identified as Atirupa Thapa, 65 and her 10-year-old granddaughter Sirisha Thapa of Pallotari of Marsyangdi rural municipality-3 and 46-year-old Bishnu Maya Gurung of ward no. 4 of the same rural municipality.',
        '2018-09-13',
        None,
        KEYWORDS_CFG,
        published_year_hint=2018,
    )
    assert result['deaths'] == 3
    assert result['event_date_ad'] == '2018-09-12'
    assert result['municipality'] == 'Marsyangdi Rural Municipality'


def test_extract_en_road_lead_rain_context_sets_rainfall_trigger_for_myrepublica_rows() -> None:
    result = extract_en(
        'Vehicular movement along Narayanghat-Mugling road disrupted for second time this week due to landslides',
        'CHITWAN, July 24: Vehicular movement along the Narayanghat-Mugling road section has been disrupted after landslides occurred at Charkilo area in Ichchakamana Rural Municipality-6. The area has been witnessing heavy rainfall for the past few days.',
        '2020-07-24',
        None,
        KEYWORDS_CFG,
        published_year_hint=2020,
    )
    assert result['trigger'] == 'rainfall'


def test_extract_en_road_lead_rain_context_works_when_rainfall_is_in_later_lead_paragraph() -> None:
    result = extract_en(
        'Vehicular movement along Narayanghat-Mugling road disrupted for second time this week due to landslides',
        'By Republica CHITWAN, July 24: Vehicular movement along the Narayanghat-Mugling road section has been disrupted after landslides occurred at Charkilo area in Ichchakamana Rural Municipality-6.\n\nThe key highway has been blocked for the second time this week. Earlier, the highway remained blocked for 36 hours since Monday morning.\n\nThe area has been witnessing heavy rainfall for the past few days.',
        '2020-07-24',
        None,
        KEYWORDS_CFG,
        published_year_hint=2020,
    )
    assert result['trigger'] == 'rainfall'


def test_extract_en_adjacent_sentence_rainfall_context_sets_trigger_for_bajura_case() -> None:
    result = extract_en(
        'One dies as landslide sweeps a house in Bajura',
        'BAJURA, July 8: A person has died after a landslide swept away a house in Budhinanda Municipality-2. The incident occurred following continuous rainfall in the area.',
        '2020-07-08',
        None,
        KEYWORDS_CFG,
        published_year_hint=2020,
    )
    assert result['trigger'] == 'rainfall'
    assert result['deaths'] == 1


def test_extract_en_torrential_downpour_sets_rainfall_trigger() -> None:
    result = extract_en(
        'Landslide obstructs Pasang Lhamu highway',
        'RASUWA, Sept 11: Transportation has come to a grinding halt along the Pasang Lhamu highway after torrential downpour triggered multiple landslides.',
        '2016-09-11',
        None,
        KEYWORDS_CFG,
        published_year_hint=2016,
    )
    assert result['trigger'] == 'rainfall'


def test_extract_en_parenthesized_dateline_and_last_night_shift_date() -> None:
    result = extract_en(
        'Landslide disrupts Narayanghat-Butwal road',
        'By Republica MADHYABINDU (NAWALPARASI), Aug 14: The Narayanghat-Butwal road section along the East-West Highway has been obstructed.\n\nThe Nawalparasi (Bardaghat Susta East) road has been obstructed again after a landslide occurred in Binayi Triveni Rural Municipality-2, Daunne, on Monday night.\n\nDeputy Superintendent of Police at the District Police Office, Bardaghat-Susta East, Bed Bahadur Poudel said the road that came into partial operation since Tuesday evening has been blocked following torrential rain last night.',
        '2024-08-14',
        None,
        KEYWORDS_CFG,
        published_year_hint=2024,
    )
    assert result['district'] == 'Nawalpur'
    assert result['municipality'] == 'Binayee Rural Municipality'
    assert result['event_date_ad'] == '2024-08-13'
    assert result['trigger'] == 'rainfall'



def test_extract_en_infers_single_death_from_a_person_has_died_phrase() -> None:
    result = extract_en(
        'One dies as landslide buries shed in Arghakhanchi',
        'ARGHAKHANCHI, Aug 20: A person has died after a landslide buried a shed in Bhangala, Sitganga Municipality, Arghakhanchi today. According to police, Bishnu Thapa died when a landslide triggered by rains buried a shed.',
        '2024-08-20',
        None,
        KEYWORDS_CFG,
        published_year_hint=2024,
    )
    assert result['deaths'] == 1
    assert result['trigger'] == 'rainfall'


def test_extract_en_infers_deaths_from_bodies_recovered_phrase() -> None:
    result = extract_en(
        'Four bodies recovered from landslide debris',
        'NUWAKOT, August 9: The bodies of four persons missing under the landslide debris at Pairebensi of Uttargaya rural municipality 4, Rasuwa have been recovered.',
        '2017-08-09',
        None,
        KEYWORDS_CFG,
        published_year_hint=2017,
    )
    assert result['deaths'] == 4


def test_extract_en_construction_context_sets_anthropogenic_trigger() -> None:
    result = extract_en(
        'Road worker buried to death in Gorkha landslide',
        'GORKHA, Aug 2: A laborer on duty died along the Arughat-Larke road section. He was buried in a landslide at Dharche Rural Municipality-3, Tatopani, according to Nepal Army Major Nishant Chhetri who heads the road construction taskforce. Nepal Army has been constructing the road connecting Tibet.',
        '2020-08-02',
        None,
        KEYWORDS_CFG,
        published_year_hint=2020,
    )
    assert result['deaths'] == 1
    assert result['trigger'] == 'anthropogenic'


def test_extract_en_dry_landslide_with_construction_context_sets_anthropogenic_trigger() -> None:
    result = extract_en(
        'Two buried to death in landslide in Sankhuwasabha',
        'KIMATHANKA, June 1: Two people were buried to death in a landslide at Nundhaki of Chainpur Municipality-1 in Sankhuwasabha district Wednesday morning. Police said the two were buried in a dry landslide while they were working for the construction of the Chainpur-Nundhaki road.',
        '2022-06-01',
        None,
        KEYWORDS_CFG,
        published_year_hint=2022,
    )
    assert result['deaths'] == 2
    assert result['trigger'] == 'anthropogenic'


def test_extract_en_prefers_same_district_municipality_over_victim_home_municipality() -> None:
    result = extract_en(
        'One killed in landslide',
        'KARNALI, July 5: A woman died in a dry landslide that occurred near Daurikhola, Panchapuri Rural Municipality-7 in Surkhet district today. The deceased has been identified as Amrita Jaisi of Turmakhand Rural Municipality-6, Achham district.',
        '2022-07-05',
        None,
        KEYWORDS_CFG,
        published_year_hint=2022,
    )
    assert result['district'] == 'Surkhet'
    assert result['municipality'] == 'Panchpuri Municipality'


def test_extract_en_road_articles_with_multiple_municipalities_leave_municipality_blank() -> None:
    result = extract_en(
        'Landslide obstructs Khandbari-Kimathanka Road',
        'Kimathanka, June 20 (RSS): A landslide triggered by continuous rain has obstructed the Khandbari to Kimathanka section of the North-South Road leading to Bhotkhola and Makalu rural municipalities in the Sankhuwasabha district.',
        '2022-06-20',
        None,
        KEYWORDS_CFG,
        published_year_hint=2022,
    )
    assert result['district'] == 'Sankhuwasabha'
    assert result['municipality'] is None



def test_extract_en_ward_form_bare_municipality_name_resolves() -> None:
    result = extract_en(
        'Landslide obstructs Narayangarh-Muglin road',
        'Muglin, June 9 (RSS): The landslide occurred near the Namsi Bridge at Ichchhakamana-6, Topekhola in Chitwan obstructing two-way road traffic since last night.',
        '2022-06-09',
        None,
        KEYWORDS_CFG,
        published_year_hint=2022,
    )
    assert result['municipality'] == 'Ichchhyakamana Rural Municipality'


def test_extract_en_supports_uppercase_dateline_month_day_without_year() -> None:
    result = extract_en(
        'Mudslide claims one in Dhading; one missing',
        'DHADING, JUNE 19\n\nThe landslide that occurred in Rubi Valley Rural Municipality-2 of in Dhading has claimed the life of one person while one person is still missing.',
        '2021-06-20',
        None,
        KEYWORDS_CFG,
    )
    assert result['event_date_ad'] == '2021-06-19'
    assert result['conf_date'] >= 0.88
    assert result['class'] == 1


def test_extract_en_body_district_phrase_outranks_a_neighbouring_bureau_dateline() -> None:
    """A dateline names the filing bureau, not necessarily the event district.

    Regression: "SURKHET, Aug 30: ... in Kalikot district" was stored as
    Surkhet. The error was invisible because the record was self-consistent.
    """

    result = extract_en(
        'Five houses swept away by landslide in Kalikot',
        'By Republica SURKHET, Aug 30: A landslide swept away five houses and killed one '
        'person in Kalikot district on Sunday morning. The landslide that occurred at Nagam '
        'Bazar of Tilagufa Municipality-1 at around 7:30 this morning killed one person, '
        'according to the District Police Office, Kalikot.',
        '2020-08-30',
        None,
        KEYWORDS_CFG,
        published_year_hint=2020,
    )
    assert result['district'] == 'Kalikot'
    assert result['municipality'] == 'Tilagufa Municipality'


def test_extract_en_lower_case_district_qualifier_is_recognised() -> None:
    """House style is "in Kalikot district"; requiring a capital D missed it."""

    result = extract_en(
        'Landslide kills one',
        'By Republica SURKHET, Aug 30: A landslide killed one person in Kalikot district '
        'on Sunday morning.',
        '2020-08-30',
        None,
        KEYWORDS_CFG,
        published_year_hint=2020,
    )
    assert result['district'] == 'Kalikot'


def test_extract_en_victims_home_municipality_does_not_relocate_the_event() -> None:
    """Regression: "Pilgrim dies in Rasuwa landslide" was stored as Rautahat.

    Chandrapur Municipality is in Rautahat, but it is the deceased's home
    address, not where the landslide happened.
    """

    result = extract_en(
        'Pilgrim dies in Rasuwa landslide',
        'By Republica RASUWA, Aug 3: A pilgrim heading toward Gosainkunda died on the way '
        'after being buried by a landslide. The deceased has been identified as Namrata '
        'Karki of Chandrpur Municipality-1, Rautahat. DSP Santosh Tamang confirmed that the '
        '35-year-old died during the incident at Mini-Gosainkunda-6 of Rasuwa district.',
        '2024-08-03',
        None,
        KEYWORDS_CFG,
        published_year_hint=2024,
    )
    assert result['district'] == 'Rasuwa'
    assert result['municipality'] != 'Chandrapur Municipality'


def test_district_near_municipality_guard_separates_qualification_from_co_occurrence() -> None:
    from landslide_inventory.gazetteer import normalize_district
    from landslide_inventory.nlp_en.extract import (
        _district_is_near_municipality,
        _municipality_stem,
    )

    normalizer = lambda name: normalize_district(name, 'en')  # noqa: E731

    assert _municipality_stem('Uttargaya Rural Municipality') == 'Uttargaya'
    assert _municipality_stem('Kathmandu Metropolitan City') == 'Kathmandu'
    assert _municipality_stem('Birgunj Sub-Metropolitan City') == 'Birgunj'

    qualifying = (
        'The bodies were recovered at Pairebensi of Uttargaya rural municipality - 4, '
        'Rasuwa on Wednesday.'
    )
    assert _district_is_near_municipality(
        qualifying, 'Uttargaya Rural Municipality', 'Rasuwa', normalizer
    ) is True

    boilerplate = (
        'Subscribe Login Politics Economy Society Rautahat Sports Republica Watch. '
        + 'Filler sentence. ' * 8
        + 'A landslide struck Chandrapur Municipality on Sunday.'
    )
    assert _district_is_near_municipality(
        boilerplate, 'Chandrapur Municipality', 'Rautahat', normalizer
    ) is False

    # A municipality whose name is not written in the text at all cannot be
    # judged; the guard declines rather than moving the event.
    assert _district_is_near_municipality(
        qualifying, 'Melamchi Municipality', 'Sindhupalchok', normalizer
    ) is False


def test_extract_en_reads_a_count_separated_from_the_death_verb() -> None:
    """"Four persons of a single family were buried to death" -- the apposition
    between the count and the verb hid these counts entirely."""

    result = extract_en(
        'Four of a single family killed in Syangja landslide',
        'POKHARA: Four persons of a single family were buried to death after '
        'torrential rain triggered a landslide at Kyarebhanjyang-7 of Syangja '
        'district on Saturday.',
        '2020-08-01',
        None,
        KEYWORDS_CFG,
        published_year_hint=2020,
    )
    assert result['deaths'] == 4


def test_extract_en_does_not_read_an_age_as_a_death_count() -> None:
    """"Thirty five year Babiran Khatun was killed" is one death, not thirty-five."""

    result = extract_en(
        "Woman crossing Baglung's landslide crushed by boulder",
        'BAGLUNG, Sept 17: Thirty five year Babiran Khatun was killed after a '
        'falling boulder crushed her while she was crossing the landslide at '
        'Turture of Badigad Rural Municipality.',
        '2020-09-17',
        None,
        KEYWORDS_CFG,
        published_year_hint=2020,
    )
    assert result['deaths'] != 35


def test_extract_en_records_an_explicit_zero_but_never_imputes_one() -> None:
    stated = extract_en(
        'Panchthar landslide destroys house',
        'PHIDIM: A house has been destroyed due to a landslide in Subhang of '
        'Panchthar district on Wednesday. The house is reported to be of local '
        'Gopal Bhandari. No human casualty has been reported, informed police.',
        '2019-07-10',
        None,
        KEYWORDS_CFG,
        published_year_hint=2019,
    )
    assert stated['deaths'] == 0

    silent = extract_en(
        'Landslide blocks highway',
        'PHIDIM: A landslide blocked the Mechi Highway on Wednesday. Traffic '
        'remains disrupted.',
        '2019-07-10',
        None,
        KEYWORDS_CFG,
        published_year_hint=2019,
    )
    assert silent['deaths'] is None


def test_extract_en_audit_driven_death_phrases() -> None:
    cases = (
        ('Death toll hits nine in Sindhupalchok landslide', 9),
        ('Landslide claims two in Sindhupalchok', 2),
        ('A family lost three members when the landslide buried their home.', 3),
        ('The Lama family, who lost their three members after a landslide, received relief.', 3),
        ('A mother and daughter died in the landslide.', 2),
        ('A mother and her two-year-old daughter died after being buried by a landslide.', 2),
        ('Man injured in landslide dies during treatment.', 1),
    )
    for statement, expected in cases:
        result = extract_en(
            statement,
            statement,
            '2021-07-30',
            None,
            KEYWORDS_CFG,
            published_year_hint=2021,
        )
        assert result['deaths'] == expected, statement


def test_extract_en_rescued_alive_is_an_explicit_zero() -> None:
    result = extract_en(
        'Worker rescued alive after landslide',
        'A worker buried by a landslide was rescued alive by local residents.',
        '2021-07-30',
        None,
        KEYWORDS_CFG,
        published_year_hint=2021,
    )
    assert result['deaths'] == 0
