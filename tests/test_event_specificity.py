"""Tests for the event-specificity filtering stage."""

from __future__ import annotations

from datetime import date

import pytest

from landslide_inventory.unify.event_specificity import SpecificityRow, decide_specificity

STUDY_START = date(2015, 1, 1)
STUDY_END = date(2026, 12, 31)


def build_row(**overrides: object) -> SpecificityRow:
    base = {
        'url': 'https://example.com/article',
        'source': 'test',
        'title': 'Landslide kills two in Dhading',
        'text': 'A landslide hit Dhading district yesterday. Rescue teams recovered two bodies.',
        'published_date_ad': '2024-07-16',
        'route_lang': 'en',
        'mixed_flag': False,
        'devanagari_ratio': 0.0,
        'event_class': 1,
        'event_date_ad': '2024-07-16',
        'district': 'Dhading',
        'municipality': None,
        'deaths': 2,
        'missing': None,
        'injured': None,
    }
    base.update(overrides)
    return SpecificityRow(**base)


def test_real_event_article_is_specificity_ok() -> None:
    decision = decide_specificity(build_row(), STUDY_START, STUDY_END)
    assert decision.specificity_ok == 1
    assert decision.specificity_reason == 'event_specific'


@pytest.mark.parametrize(
    ('title', 'text'),
    [
        (
            'Siddhababa tunnel work: Butwal-Palpa road to be shut during nighttime only',
            'The road will close for scheduled tunnel construction at a landslide-prone site.',
        ),
        (
            'Nepali Army rolls out three-phase monsoon disaster plan',
            'The preparedness plan covers rescue after possible floods and landslides.',
        ),
    ],
)
def test_planned_work_and_preparedness_are_context_only(title: str, text: str) -> None:
    row = build_row(title=title, text=text, deaths=None, missing=None, injured=None)
    decision = decide_specificity(row, STUDY_START, STUDY_END)
    assert decision.specificity_ok == 0
    assert decision.specificity_reason == 'context_only'


def test_unrelated_parliamentary_story_is_not_recast_from_late_context() -> None:
    row = build_row(
        title='Lawmakers seek investigation into student death',
        text=(
            'The national assembly discussed the student death and the police investigation. ' * 12
            + 'A different lawmaker later described a landslide in another district.'
        ),
        district='Surkhet',
        deaths=2,
    )
    decision = decide_specificity(row, STUDY_START, STUDY_END)
    assert decision.specificity_ok == 0
    assert decision.specificity_reason == 'context_only'


def test_hazard_named_parliamentary_rescue_followup_is_preserved() -> None:
    row = build_row(
        title='चितवन पहिरोमा बेपत्ताको खोजी गर्न सांसदहरूले गराए सरकारको ध्यानाकर्षण',
        text='चितवनमा पहिरोले दुई बस बगाउँदा यात्रु बेपत्ता भएका थिए। खोजी जारी छ।',
        district='Chitwan',
        deaths=None,
        missing=20,
    )
    decision = decide_specificity(row, STUDY_START, STUDY_END)
    assert decision.specificity_ok == 1


def test_primary_bus_collision_is_not_recast_from_landslide_road_context() -> None:
    row = build_row(
        title='बसको ठक्करबाट ज्यान गुमाएका हवल्दार घर पुग्न लागेका थिए',
        text=(
            'बसले ठक्कर दिँदा उनको घटनास्थलमै मृत्यु भयो। दुर्घटनाबारे प्रहरीले अनुसन्धान गरिरहेको छ। '
            'घटना भएको ठाउँमा सडकको केही भाग पहिरोले पुरेको हुँदा मोड साँघुरो थियो।'
        ),
        district='Baitadi',
        deaths=1,
    )
    decision = decide_specificity(row, STUDY_START, STUDY_END)
    assert decision.specificity_ok == 0
    assert decision.specificity_reason == 'context_only'


def test_landslide_caused_vehicle_crash_remains_an_event() -> None:
    row = build_row(
        title='Bus accident kills one in Dhading',
        text='A landslide caused the bus accident in Dhading district yesterday.',
        district='Dhading',
        deaths=1,
    )
    decision = decide_specificity(row, STUDY_START, STUDY_END)
    assert decision.specificity_ok == 1


def test_foreign_hazard_location_overrides_victim_home_district() -> None:
    row = build_row(
        title='व्यक्ति सम्पर्क विहीन, क्षेत्र सुरक्षित',
        text=(
            'इलामका पाँच जना अझै सम्पर्कमा आएका छैनन्। सिक्किममा ठूलो बाढी गएको थियो। '
            'उनीहरू सिक्किममा निर्माण श्रमिकका रूपमा गएका थिए।'
        ),
        district='Ilam',
        deaths=None,
        missing=5,
    )
    decision = decide_specificity(row, STUDY_START, STUDY_END)
    assert decision.specificity_ok == 0
    assert decision.specificity_reason == 'out_of_country'


def test_foreign_national_does_not_override_nepal_landslide_location() -> None:
    row = build_row(
        title='Landslide kills worker in Sindhupalchok',
        text='A landslide occurred in Sindhupalchok, Nepal and killed an Indian worker.',
        district='Sindhupalchok',
        deaths=1,
    )
    decision = decide_specificity(row, STUDY_START, STUDY_END)
    assert decision.specificity_ok == 1


def test_event_detection_does_not_require_successful_location_extraction() -> None:
    row = build_row(
        title='पहिरोले पासाङ ल्हामु राजमार्ग बन्द',
        text='पहिरोका कारण राजमार्ग बन्द भएको छ।',
        district=None,
        municipality=None,
        event_date_ad=None,
        deaths=None,
        missing=None,
        injured=None,
    )
    decision = decide_specificity(row, STUDY_START, STUDY_END)
    assert decision.specificity_ok == 1
    assert decision.specificity_reason == 'event_specific_title'


def test_monsoon_roundup_is_rejected() -> None:
    row = build_row(
        title='Death toll reaches 244 in this monsoon',
        text='This monsoon has killed 244 people overall across the country so far.',
        district=None,
        municipality=None,
        event_date_ad=None,
        deaths=244,
    )
    decision = decide_specificity(row, STUDY_START, STUDY_END)
    assert decision.specificity_ok == 0
    assert decision.specificity_reason == 'context_only'
    assert decision.updated_class == 3


def test_risk_warning_is_rejected() -> None:
    row = build_row(
        title='Five villages at high risk of landslide',
        text='Officials issued a warning that heavy rainfall likely could trigger landslides.',
        district='Myagdi',
        event_date_ad=None,
        deaths=None,
    )
    decision = decide_specificity(row, STUDY_START, STUDY_END)
    assert decision.specificity_ok == 0
    assert decision.specificity_reason == 'risk_only'
    assert decision.updated_class == 3


def test_out_of_country_with_nepali_victims_is_rejected() -> None:
    row = build_row(
        title='Three Nepalis die in Uttarakhand landslide',
        text='Three Nepali labourers died after a landslide hit Uttarakhand in India.',
        district=None,
        municipality=None,
        event_date_ad='2024-07-16',
        deaths=3,
    )
    decision = decide_specificity(row, STUDY_START, STUDY_END)
    assert decision.specificity_ok == 0
    assert decision.specificity_reason == 'out_of_country'
    assert decision.updated_class == 3
    assert decision.updated_class == 3


def test_damage_only_without_event_signal_is_rejected() -> None:
    row = build_row(
        title='Road damage reported after monsoon rain',
        text='The road damage caused heavy loss and property damage in the area.',
        district=None,
        municipality=None,
        event_date_ad=None,
        deaths=None,
        missing=None,
        injured=None,
    )
    decision = decide_specificity(row, STUDY_START, STUDY_END)
    assert decision.specificity_ok == 0
    assert decision.specificity_reason == 'damage_only'


def test_no_signal_defaults_to_no_location_signal() -> None:
    row = build_row(
        title='Monsoon season continues',
        text='Officials discussed weather preparedness at a meeting.',
        district=None,
        municipality=None,
        event_date_ad=None,
        deaths=None,
        missing=None,
        injured=None,
    )
    decision = decide_specificity(row, STUDY_START, STUDY_END)
    assert decision.specificity_ok == 0
    assert decision.specificity_reason == 'no_location_signal'



def test_multi_district_nepali_roundup_is_rejected() -> None:
    row = build_row(
        title='१५ जिल्लामा बाढीपहिरोबाट ४७ जनाको मृत्यु, १५ बेपत्ता ८ घाइते',
        text='१५ जिल्लामा बाढीपहिरोबाट ४७ जनाको मृत्यु, १५ बेपत्ता ८ घाइते भएको गृह मन्त्रालयले जनाएको छ।',
        district='Panchthar',
        municipality=None,
        event_date_ad='2017-08-13',
        deaths=47,
        missing=15,
        injured=8,
    )
    decision = decide_specificity(row, STUDY_START, STUDY_END)
    assert decision.specificity_ok == 0
    assert decision.specificity_reason == 'roundup'
    assert decision.updated_class == 2



def test_concrete_followup_recovery_piece_is_retained() -> None:
    row = build_row(
        title='बझाङमा पहिरोमा बेपत्ता युवकको २८ दिनपछि शव फेला',
        text='बझाङमा पहिरोमा बेपत्ता भएका युवकको २८ दिनपछि शव फेला परेको प्रहरीले जनाएको छ।',
        district='Bajhang',
        municipality=None,
        event_date_ad='2020-08-09',
        deaths=1,
    )
    decision = decide_specificity(row, STUDY_START, STUDY_END)
    assert decision.specificity_ok == 1
    assert decision.specificity_reason == 'event_specific_followup'
    assert decision.updated_class is None


def test_concrete_relief_followup_piece_is_retained() -> None:
    row = build_row(
        title='सिन्धुपाल्चोक पहिरो: १८ जनाको शव भेटियो, मृतकका परिवारलाई १ लाख राहत दिइने',
        text='मृतकका परिवारलाई राहत दिइने र क्षतिपूर्ति उपलब्ध गराइने सरकारले जनाएको छ।',
        district='Sindhupalchok',
        municipality=None,
        event_date_ad='2020-08-16',
        deaths=18,
    )
    decision = decide_specificity(row, STUDY_START, STUDY_END)
    assert decision.specificity_ok == 1
    assert decision.specificity_reason == 'event_specific_followup'
    assert decision.updated_class is None



def test_metaphorical_landslide_title_is_rejected() -> None:
    row = build_row(
        title='Maoist Centre’s landslide victory in Rukum East',
        text='The party took a commanding lead in the local election vote count.',
        district='Rukum East',
        municipality='Bhume Rural Municipality',
        event_date_ad='2022-05-17',
        deaths=None,
        missing=None,
        injured=None,
    )
    decision = decide_specificity(row, STUDY_START, STUDY_END)
    assert decision.specificity_ok == 0
    assert decision.specificity_reason == 'metaphor'
    assert decision.updated_class == 3



def test_election_landslide_win_title_is_rejected() -> None:
    row = build_row(
        title='RSP sweeps all four Parsa constituencies in landslide wins',
        text='The party won the election after vote counting in all constituencies.',
        district='Parsa',
        municipality=None,
        event_date_ad='2026-03-08',
        deaths=None,
        missing=None,
        injured=None,
    )
    decision = decide_specificity(row, STUDY_START, STUDY_END)
    assert decision.specificity_ok == 0
    assert decision.specificity_reason == 'metaphor'
    assert decision.updated_class == 3




def test_foreign_title_place_overrides_nepal_section_boilerplate() -> None:
    row = build_row(
        source='himalayan-times',
        title='16 Nepalis feared buried in Uttarakhand landslide',
        text='KATHMANDU, AUGUST 04 Sixteen Nepalis near Rudra Prayag district of Uttarakhand, India, are feared buried after a landslide. Embassy of Nepal, New Delhi, confirmed the report.',
        district='Kathmandu',
        municipality=None,
        event_date_ad='2023-08-04',
        deaths=2,
        missing=16,
        injured=None,
    )
    decision = decide_specificity(row, STUDY_START, STUDY_END)
    assert decision.specificity_ok == 0
    assert decision.specificity_reason == 'out_of_country'
    assert decision.updated_class == 3


def test_ratopati_foreign_title_suffix_does_not_mask_out_of_country() -> None:
    row = build_row(
        source='ratopati',
        title="अफगानिस्तानमा पहिरो, ४ जनाको मृत्यु, ६ घाइते | Nepal's first 24-hour updated news portal - Ratopati",
        text='काठमाडाैँ । अफगानिस्तानको पूर्वी क्षेत्र कापिसा प्रान्तमा शुक्रबार राति परेको पहिरोले घरमा क्षति पुर्‍याउँदा चार जनाको मृत्यु भएको छ।',
        district='Parbat',
        municipality=None,
        event_date_ad='2026-02-13',
        deaths=4,
        missing=None,
        injured=6,
    )
    decision = decide_specificity(row, STUDY_START, STUDY_END)
    assert decision.specificity_ok == 0
    assert decision.specificity_reason == 'out_of_country'
    assert decision.updated_class == 3


def test_nepali_new_zealand_landslide_is_rejected_as_out_of_country() -> None:
    row = build_row(
        source='online-khabar',
        title='न्युजिल्यान्डको माउन्ट माउन्गानुईमा भीषण पहिरो, बालबालिकासहित कैयौँ बेपत्ता',
        text='८ माघ, काठमाडौं । न्युजिल्यान्डको उत्तरी टापुमा अवस्थित पर्यटकीय क्षेत्रमा गएको पहिरोमा कैयौँ मानिसहरू बेपत्ता भएका छन्।',
        district='Kathmandu',
        municipality=None,
        event_date_ad='2026-01-22',
        deaths=None,
        missing=4,
        injured=None,
    )
    decision = decide_specificity(row, STUDY_START, STUDY_END)
    assert decision.specificity_ok == 0
    assert decision.specificity_reason == 'out_of_country'


def test_nepali_demonym_does_not_make_nepal_event_out_of_country() -> None:
    row = build_row(
        title='पहिरोले बगाउँदा कपिलवस्तुमा दुई भारतीय नागरिक बेपत्ता',
        text='कपिलवस्तुमा गएको पहिरोमा दुई भारतीय नागरिक बेपत्ता भएका छन्।',
        district='Kapilvastu',
        municipality=None,
        event_date_ad='2021-07-20',
        deaths=None,
        missing=2,
        injured=None,
    )
    decision = decide_specificity(row, STUDY_START, STUDY_END)
    assert decision.specificity_ok == 1
    assert decision.specificity_reason == 'event_specific'
    assert decision.updated_class is None




def test_regional_damage_summary_is_rejected_as_roundup() -> None:
    row = build_row(
        source='setopati',
        title='बाढी पहिरोको कारण कोशी, मधेस र बागमती प्रदेशमा कहाँ कस्तो छ क्षति?',
        text='विभिन्न प्रदेशमा बाढी पहिरोका कारण भएको क्षतिको समग्र विवरण प्रस्तुत गरिएको छ।',
        district='Ilam',
        municipality='Illam Municipality',
        event_date_ad='2025-10-05',
        deaths=None,
        missing=None,
        injured=None,
    )
    decision = decide_specificity(row, STUDY_START, STUDY_END)
    assert decision.specificity_ok == 0
    assert decision.specificity_reason == 'roundup'
    assert decision.updated_class == 2


def test_multiple_landslide_road_reopening_is_rejected_as_multi_event() -> None:
    row = build_row(
        title='Narayangadh-Muglin road reopens after multiple landslides',
        text='The road reopened after crews cleared landslide debris from the highway.',
        district='Chitwan',
        municipality='Ichchhyakamana Rural Municipality',
        event_date_ad='2025-09-16',
        deaths=None,
        missing=None,
        injured=None,
    )
    decision = decide_specificity(row, STUDY_START, STUDY_END)
    assert decision.specificity_ok == 0
    assert decision.specificity_reason == 'multi_event'
    assert decision.updated_class == 2


def test_landslide_control_project_is_rejected_as_context() -> None:
    row = build_row(
        source='ratopati',
        title='अरनिको राजमार्गको कोदारीमा ४७ करोडको विशाल पहिरो नियन्त्रण आयोजना सुरु, २५० घर जोगिने',
        text='पहिरो नियन्त्रण आयोजनाको काम सुरु भएको र घरहरू जोगिने समाचार हो।',
        district='Rautahat',
        municipality=None,
        event_date_ad='2026-03-19',
        deaths=None,
        missing=None,
        injured=None,
    )
    decision = decide_specificity(row, STUDY_START, STUDY_END)
    assert decision.specificity_ok == 0
    assert decision.specificity_reason == 'context_only'
    assert decision.updated_class == 3


def test_non_event_article_with_body_noise_is_rejected() -> None:
    row = build_row(
        source='ekantipur',
        title='डडेलधुरामा हाटबजार सञ्चालन गर्ने तयारी',
        text='जिल्लामा उत्पादित तरकारी बिक्रीका लागि हाटबजार सञ्चालन तयारी भएको छ।',
        district='Kathmandu',
        municipality=None,
        event_date_ad='2026-03-28',
        deaths=None,
        missing=None,
        injured=None,
    )
    decision = decide_specificity(row, STUDY_START, STUDY_END)
    assert decision.specificity_ok == 0
    assert decision.specificity_reason == 'context_only'
    assert decision.updated_class == 3


def test_direct_casualty_title_is_not_downgraded_by_roundup_boilerplate() -> None:
    row = build_row(
        title='Five injured as landslide buries three vehicles in Lalitpur',
        text='Subscribe Login Latest news. Five injured after a landslide buried three vehicles in Lalitpur. Our search uses full-text indexing.',
        district='Lalitpur',
        event_date_ad='2020-09-24',
        deaths=None,
        missing=None,
        injured=5,
    )
    decision = decide_specificity(row, STUDY_START, STUDY_END)
    assert decision.specificity_ok == 1
    assert decision.specificity_reason == 'event_specific'



def test_myrepublica_trim_prevents_risk_false_positive_from_related_noise() -> None:
    row = build_row(
        source='myrepublica',
        title='Search operation underway to trace the whereabouts of three missing in Mehele landslide - myRepublica - The New York Times Partner',
        text='Subscribe Login Subscribe Politics Economy Society. By Republica TAPLEJUNG, June 20: Search for those missing in the landslide that occurred at Mehele of Sidingba rural municipality-6 in Taplejung on Saturday night is underway. Locals are carrying out searches for the missing ones. unrelated teaser text about 12 families at risk appears much later.',
        district='Taplejung',
        municipality=None,
        event_date_ad='2023-06-17',
        missing=3,
        deaths=None,
        injured=None,
    )
    decision = decide_specificity(row, STUDY_START, STUDY_END)
    assert decision.specificity_ok == 1
    assert decision.specificity_reason == 'event_specific'



def test_direct_event_title_is_not_downgraded_by_risk_teaser_noise() -> None:
    row = build_row(
        source='myrepublica',
        title='Search operation underway to trace the whereabouts of three missing in Mehele landslide - myRepublica - The New York Times Partner',
        text='Subscribe Login Subscribe Politics Economy Society. By Republica TAPLEJUNG, June 20: Search for those missing in the landslide that occurred at Mehele of Sidingba rural municipality-6 in Taplejung on Saturday night is underway. Locals along with police personnel are carrying out searches for the missing ones. Much later, unrelated teaser text says other families are at risk.',
        district='Taplejung',
        municipality='Sidingba Rural Municipality',
        event_date_ad='2023-06-17',
        missing=3,
        deaths=2,
        injured=None,
    )
    decision = decide_specificity(row, STUDY_START, STUDY_END)
    assert decision.specificity_ok == 1
    assert decision.specificity_reason == 'event_specific'


def test_policy_relief_discussion_is_context_only() -> None:
    row = build_row(
        source='myrepublica',
        title='Lawmakers call for prompt relief to flood and landslide affected people - myRepublica - The New York Times Partner',
        text='KATHMANDU, Aug 14: Lawmakers speaking in the meeting of the House of Representatives drew the attention of the government to provide relief to flood and landslide affected people at the earliest.',
        district='Lalitpur',
        municipality=None,
        event_date_ad='2018-08-14',
        deaths=None,
        missing=None,
        injured=None,
    )
    decision = decide_specificity(row, STUDY_START, STUDY_END)
    assert decision.specificity_ok == 0
    assert decision.specificity_reason == 'context_only'
    assert decision.updated_class == 3


def test_background_analysis_piece_is_context_only() -> None:
    row = build_row(
        source='myrepublica',
        title='Flooding, landslides blamed for poor SLC results - myRepublica - The New York Times Partner',
        text='SURKHET, June 24: Students said flooding and landslides were blamed for poor SLC results after the August disaster hampered their studies.',
        district=None,
        municipality=None,
        event_date_ad='2015-06-24',
        deaths=None,
        missing=None,
        injured=None,
    )
    decision = decide_specificity(row, STUDY_START, STUDY_END)
    assert decision.specificity_ok == 0
    assert decision.specificity_reason == 'context_only'
    assert decision.updated_class == 3


def test_nationwide_roundup_without_single_location_is_context_only() -> None:
    row = build_row(
        title='Floods and landslides toll climbs to 111',
        text='The death toll from floods and landslides across the country has risen to 111, and people remain missing in various districts.',
        district=None,
        municipality=None,
        event_date_ad='2017-08-16',
        deaths=111,
        missing=36,
        injured=None,
    )
    decision = decide_specificity(row, STUDY_START, STUDY_END)
    assert decision.specificity_ok == 0
    assert decision.specificity_reason == 'context_only'
    assert decision.updated_class == 3


def test_myrepublica_local_aggregate_fatalities_story_is_context_only() -> None:
    row = build_row(
        source='myrepublica',
        title='Death toll from floods, landslides and inundation rises to 102, with 64 still missing - myRepublica - The New York Times Partner',
        text='KATHMANDU, Sept 29: The number of fatalities due to floods, landslides and inundation following continuous rainfall has reached 102. According to the Armed Police Force of Nepal, 64 individuals are missing due to floods, landslides, and inundation. The highest number of fatalities, 48, has occurred in the Kathmandu Valley and 15 deaths in Koshi Province have been recorded so far.',
        district='Kathmandu',
        municipality=None,
        event_date_ad='2024-09-29',
        deaths=15,
        missing=64,
        injured=45,
    )
    decision = decide_specificity(row, STUDY_START, STUDY_END)
    assert decision.specificity_ok == 0
    assert decision.specificity_reason == 'context_only'
    assert decision.updated_class == 3


def test_opposition_relief_statement_is_context_only() -> None:
    row = build_row(
        source='myrepublica',
        title='Opposition alliance demands govt ensure effective relief and rescue to help those affected by flood, landslides - myRepublica - The New York Times Partner',
        text='KATHMANDU, June 17: The opposition alliance has demanded the government make relief and rescue efforts effective to help those affected by floods, landslides and inundation. Issuing a joint press statement, the leaders asked the government to provide food, shelter and other relief materials to those affected.',
        district='Kathmandu',
        municipality=None,
        event_date_ad='2021-06-17',
        deaths=None,
        missing=None,
        injured=None,
    )
    decision = decide_specificity(row, STUDY_START, STUDY_END)
    assert decision.specificity_ok == 0
    assert decision.specificity_reason == 'context_only'
    assert decision.updated_class == 3


def test_bajura_houses_at_risk_story_is_risk_only() -> None:
    row = build_row(
        source='myrepublica',
        title='Over 150 houses in Bajura at risk of dry landslide - myRepublica - The New York Times Partner',
        text='MARTADI, August 16: A dry landslide has continued for days at Swamikartik Rural Municipality-1 in Bajura district, putting over 150 houses at risk of being washed away. The landslide has continued to fall for the past two days. As a result, the areas around Juddi are at a risk of being swept away.',
        district='Bajura',
        municipality=None,
        event_date_ad='2021-08-16',
        deaths=None,
        missing=None,
        injured=None,
    )
    decision = decide_specificity(row, STUDY_START, STUDY_END)
    assert decision.specificity_ok == 0
    assert decision.specificity_reason == 'risk_only'
    assert decision.updated_class == 3


def test_multi_incident_sindhupalchok_story_is_roundup() -> None:
    row = build_row(
        source='myrepublica',
        title='Ten people killed in separate landslides in Sindhupalchowk - myRepublica - The New York Times Partner',
        text='SINDHUPALCHOWK, Aug 3: Ten people were killed in two separate incidents of landslides triggered by incessant rainfall in Sindhupalchowk on Sunday night. In a separate incident of landslide, a husband and wife were killed in Panchpokhari Thangpal Rural Municipality-2 on Sunday night.',
        district='Sindhupalchok',
        municipality='Panchpokhari Thangpal Rural Municipality',
        event_date_ad='2020-08-02',
        deaths=10,
        missing=None,
        injured=1,
    )
    decision = decide_specificity(row, STUDY_START, STUDY_END)
    assert decision.specificity_ok == 0
    assert decision.specificity_reason == 'roundup'
    assert decision.updated_class == 2


def test_parbat_single_incident_is_not_roundup_just_because_followup_sentence_starts_with_similarly() -> None:
    row = build_row(
        source='myrepublica',
        title='Landslide kills five in Parbat, four still missing - myRepublica - The New York Times Partner',
        text='PARBAT, June 14: Five people were killed and four are still missing in a landslide at Durlung, Kusma Municipality-3, Parbat. Three bodies were found buried in the landslide debris after the incident on Saturday evening. Similarly, Samrat Thapa, Bibek Thapa, Janesh BK and Pramish BK are still missing in the landslide.',
        district='Parbat',
        municipality='Kushma Municipality',
        event_date_ad='2020-06-13',
        deaths=5,
        missing=4,
        injured=None,
    )
    decision = decide_specificity(row, STUDY_START, STUDY_END)
    assert decision.specificity_ok == 1
    assert decision.specificity_reason == 'event_specific'


def test_multi_incident_baglung_story_is_roundup() -> None:
    row = build_row(
        source='myrepublica',
        title='Three killed, three missing in landslides in Baglung - myRepublica - The New York Times Partner',
        text='BAGLUNG, August 4: Two persons were killed in a landslide at Bahungaun of Nisikhola Rural Municipality-2 early this morning. Likewise, 54-year old Om Bahadur BK also lost his life in a landslide occurred at Dhorpatan Municipality-5. Similarly, Lal Bahadur Sinjali\'s mother aged 65 also has gone missing in a landslide at Nisikhola Rural Municipality-1.',
        district='Baglung',
        municipality='Nisikhola Rural Municipality',
        event_date_ad='2017-08-04',
        deaths=3,
        missing=3,
        injured=None,
    )
    decision = decide_specificity(row, STUDY_START, STUDY_END)
    assert decision.specificity_ok == 0
    assert decision.specificity_reason == 'roundup'
    assert decision.updated_class == 2


def test_missing_family_title_is_not_downgraded_by_generic_likewise_sentence() -> None:
    row = build_row(
        source='myrepublica',
        title='Two of a family missing in Taplejung landslide - myRepublica - The New York Times Partner',
        text='TAPLEJUNG, June 17: Two persons of a family have gone missing in a landslide that occurred last night at Khewang village in Sirijunga Rural Municipality-7, Taplejung. Tulasa Adhikari and her daughter-in-law Yashoda Adhikari are missing in the landslide. Likewise, heavy landslides have occurred at different places in the district following the torrential rainfall.',
        district='Taplejung',
        municipality='Sirijangha Rural Municipality',
        event_date_ad='2022-06-16',
        deaths=None,
        missing=2,
        injured=None,
    )
    decision = decide_specificity(row, STUDY_START, STUDY_END)
    assert decision.specificity_ok == 1
    assert decision.specificity_reason == 'event_specific'


def test_myrepublica_toll_rises_story_is_context_only() -> None:
    row = build_row(
        source='myrepublica',
        title='Death toll from floods, landslides and inundation rises to 102, with 64 still missing - myRepublica - The New York Times Partner',
        text='KATHMANDU, Sept 30: The death toll from floods, landslides and inundation across the country has risen to 102, while 64 people are still missing in various districts.',
        district=None,
        municipality=None,
        event_date_ad='2024-09-30',
        deaths=102,
        missing=64,
        injured=None,
    )
    decision = decide_specificity(row, STUDY_START, STUDY_END)
    assert decision.specificity_ok == 0
    assert decision.specificity_reason == 'context_only'
    assert decision.updated_class == 3


def test_single_district_phrase_is_not_misread_as_multi_district_roundup() -> None:
    row = build_row(
        source='myrepublica',
        title='Five injured as landslide buries three vehicles in Lalitpur - myRepublica - The New York Times Partner',
        text='KATHMANDU, Sep 24: Five persons were injured as a landslide triggered by incessant rainfall buried three vehicles along the Kanti Lokpath road in Lalitpur district on Thursday morning. The government has not been able to airlift the injured so far due to bad weather.',
        district='Lalitpur',
        municipality=None,
        event_date_ad='2020-09-24',
        deaths=None,
        missing=None,
        injured=5,
    )
    decision = decide_specificity(row, STUDY_START, STUDY_END)
    assert decision.specificity_ok == 1
    assert decision.specificity_reason == 'event_specific'


def test_myrepublica_single_road_event_is_not_roundup_just_because_it_says_since_last_night() -> None:
    row = build_row(
        source='myrepublica',
        title='Vehicular movement along Prithvi Highway disturbed following dry landslides - myRepublica - The New York Times Partner',
        text='By Republica TANAHU, June 23: Vehicular movement along the Prithvi Highway has been obstructed since last night following dry landslides at Aina cliff of Abukhaireni Rural Municipality-2 of Tanahu district.',
        district='Tanahu',
        municipality='Anbukhaireni Rural Municipality',
        event_date_ad='2020-06-22',
        deaths=None,
        missing=None,
        injured=None,
    )
    decision = decide_specificity(row, STUDY_START, STUDY_END)
    assert decision.specificity_ok == 1
    assert decision.specificity_reason == 'event_specific'


def test_setopati_five_year_summary_is_roundup() -> None:
    row = build_row(
        source='setopati',
        title='बाढी पहिरोका कारण पाँच वर्षमा एक हजार बढीको मृत्यु',
        text='बाढी पहिरोका कारण पाँच वर्षमा एक हजार बढीको मृत्यु भएको तथ्यांक सार्वजनिक गरिएको छ।',
        district='Bardiya',
        municipality=None,
        event_date_ad='2017-08-26',
        deaths=1000,
        missing=None,
        injured=None,
    )
    decision = decide_specificity(row, STUDY_START, STUDY_END)
    assert decision.specificity_ok == 0
    assert decision.specificity_reason == 'roundup'
    assert decision.updated_class == 2


def test_setopati_specific_update_title_is_retained() -> None:
    row = build_row(
        source='setopati',
        title='तनहुँमा पहिरोले दुईको मृत्यु, पाँच जना बेपत्ता (अपडेट)',
        text='तनहुँमा पहिरोले दुईको मृत्यु भएको छ र पाँच जना अझै बेपत्ता छन्। (अपडेट)',
        district='Tanahu',
        municipality='Myagde Rural Municipality',
        event_date_ad='2020-07-13',
        deaths=2,
        missing=5,
        injured=None,
    )
    decision = decide_specificity(row, STUDY_START, STUDY_END)
    assert decision.specificity_ok == 1
    assert decision.specificity_reason == 'event_specific_followup'
    assert decision.updated_class is None


def test_setopati_specific_long_running_road_closure_is_retained() -> None:
    row = build_row(
        source='setopati',
        title='जाजरकोटमा पहिरोले १२ दिनदेखि यातायात अवरुद्ध',
        text='जाजरकोटमा पहिरोले १२ दिनदेखि यातायात अवरुद्ध हुँदा स्थानीयलाई सास्ती भएको छ।',
        district='Jajarkot',
        municipality='Bheri Municipality',
        event_date_ad='2017-09-07',
        deaths=None,
        missing=None,
        injured=None,
    )
    decision = decide_specificity(row, STUDY_START, STUDY_END)
    assert decision.specificity_ok == 1
    assert decision.specificity_reason == 'event_specific'
    assert decision.updated_class is None


def test_setopati_ministry_briefing_is_context_only() -> None:
    row = build_row(
        source='setopati',
        title='गृहले भन्यो- बाढी पहिरोमा परी एक सातामा ४७ जनाको मृत्यु, १० बेपत्ता',
        text='गृहले भन्यो- बाढी पहिरोमा परी एक सातामा ४७ जनाको मृत्यु भएको छ र १० जना बेपत्ता छन्।',
        district='Banke',
        municipality=None,
        event_date_ad='2018-07-09',
        deaths=47,
        missing=10,
        injured=None,
    )
    decision = decide_specificity(row, STUDY_START, STUDY_END)
    assert decision.specificity_ok == 0
    assert decision.specificity_reason == 'roundup'
    assert decision.updated_class == 2
