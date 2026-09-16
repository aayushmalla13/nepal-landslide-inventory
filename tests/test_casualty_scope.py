"""Casualty extraction must report THIS event's toll, not the running total.

The bug: _extract_casualties kept the largest matching number anywhere in the
article. News bodies carry two very different numbers -- the event's toll in the
headline and lead, the season-to-date national total further down as context.
Taking the maximum systematically returned the second.

Measured before the fix: 6,242 landslide deaths across 862 events (25.6 per
fatal event) against a real national toll of ~100-150 per year. After: 1,363
deaths, 6.5 per fatal event, ~124 per year.
"""

from __future__ import annotations

from landslide_inventory.nlp_en.extract import extract_en
from landslide_inventory.nlp_np.extract import extract_np

# Same nesting as the existing extractor tests: casualty_terms[field][lang].
KEYWORDS = {
    'terms': {'en': ['landslide', 'mudslide'], 'np': ['पहिरो', 'भूस्खलन']},
    'trigger_terms': {'rainfall': {'en': ['rain', 'monsoon'], 'np': ['वर्षा']}},
    'casualty_terms': {
        'deaths': {'en': ['killed', 'dead', 'deaths'], 'np': ['मृत्यु']},
        'missing': {'en': ['missing', 'disappeared'], 'np': ['बेपत्ता']},
        'injured': {'en': ['injured', 'hurt'], 'np': ['घाइते']},
    },
}


def test_english_event_toll_beats_the_national_running_total() -> None:
    """The exact shape that produced deaths=249 for a three-death landslide."""

    result = extract_en(
        'At least three killed as landslide sweeps village in Sindhupalchok',
        'SINDHUPALCHOK, Aug 14: At least three people were killed when a landslide '
        'swept away two houses in Sindhupalchok district on Friday morning.\n\n'
        'Police said rescue work is ongoing. Nationwide, 249 people have died in '
        'floods and landslides since the monsoon began this year.',
        '2020-08-14', None, KEYWORDS, published_year_hint=2020,
    )
    assert result['deaths'] == 3, (
        f"got {result['deaths']}; the national running total leaked into the "
        'event toll again'
    )


def test_nepali_event_toll_beats_the_national_running_total() -> None:
    """The shape that gave a one-woman death 90 deaths (Morang, Letang)."""

    result = extract_np(
        'मोरङको लेटाङमा पहिरोले घर पुरिँदा एक महिलाको मृत्यु',
        'मोरङको लेटाङमा पहिरोले घर पुरिँदा एक महिलाको मृत्यु भएको छ।\n\n'
        'देशभर यो मनसुनमा बाढीपहिरोबाट ९० जनाको मृत्यु भइसकेको छ।',
        '2017-08-12', None, KEYWORDS, published_year_hint=2017,
    )
    assert result['deaths'] in (1, None), f"got {result['deaths']}; expected the event toll, not 90"


def test_a_legitimately_late_figure_is_still_found() -> None:
    """Not every late number is context.

    'Vice-chairperson shared that 15 people were injured in the landslide' is
    this event's figure, just reported in paragraph three. The lead is searched
    first, but the body remains a fallback per field.
    """

    result = extract_en(
        'Landslide hits Lidi',
        'KATHMANDU, Aug 14: A landslide at Lidi in Sindhupalchowk killed four '
        'people on Friday.\n\nThirty-four others are missing.\n\n'
        'The Vice-chairperson of Jugal Rural Municipality said 15 people were '
        'injured in the landslide.',
        '2020-08-14', None, KEYWORDS, published_year_hint=2020,
    )
    assert result['deaths'] == 4
    assert result['injured'] == 15


def test_first_match_not_largest_within_the_lead() -> None:
    result = extract_en(
        'Two killed in Baglung landslide',
        'BAGLUNG, Jul 3: Two people were killed in a landslide. Officials said 45 '
        'people have died in landslides across the country so far this year.',
        '2021-07-03', None, KEYWORDS, published_year_hint=2021,
    )
    assert result['deaths'] == 2


# --- Age veto (second failure mode, found 2026-08-08) ------------------------
#
# The aggregate-context veto handles "90 died nationwide since the monsoon
# began". It does nothing about the OTHER number that sits next to a death verb:
# the victim's age. Of the 60 deadliest events in the 2026-08-08 rebuild, 38
# carried a deaths value that appears nowhere in their own title, and ages were
# the single largest cause -- including the two largest figures in the inventory.


def test_english_age_apposition_is_not_a_death_count() -> None:
    """myRepublica, 2015-07-30 Kaski. Recorded 65 deaths; the title says 20.

    The victims are listed with their ages, and "... Nanda Kali Parajuli, 65
    were killed" reads as a count unless ages are vetoed.
    """

    result = extract_en(
        'Death toll in Kaski landslides climbs to 20',
        'POKHARA, Jul 30: Tikaram BK, 65, Ramu Kumari BK, 55, Gauri Parajuli, 31, '
        'Karan Parajuli, 7, and Nanda Kali Parajuli, 65 were killed in Bhadaure '
        'when a landslide swept their houses, police said.',
        '2015-07-30', None, KEYWORDS, published_year_hint=2015,
    )
    assert result['deaths'] != 65, "a victim's age was read as the death toll"


def test_english_explicit_age_forms_are_not_death_counts() -> None:
    for body in (
        'A 72-year-old woman was killed when a landslide buried her house.',
        'A woman aged 72 was killed when a landslide buried her house.',
        'A woman, 72 years old, was killed when a landslide buried her house.',
    ):
        result = extract_en(
            'Woman killed in landslide',
            'DHADING, Jul 3: ' + body,
            '2021-07-03', None, KEYWORDS, published_year_hint=2021,
        )
        assert result['deaths'] != 72, f'age leaked as a toll in: {body}'


def test_english_appositive_veto_does_not_eat_real_counts() -> None:
    """The veto keys on a CAPITALISED name before the comma.

    A lowercase appositive is ordinary prose and must still be counted.
    """

    result = extract_en(
        'Three killed in Baglung landslide',
        'BAGLUNG, Jul 3: At least 3, including 2 children, were killed when a '
        'landslide swept a house away on Friday.',
        '2021-07-03', None, KEYWORDS, published_year_hint=2021,
    )
    assert result['deaths'] == 3


def test_nepali_age_suffix_is_not_a_death_count() -> None:
    """Setopati, 2017-08-12 Morang. Recorded 90 deaths -- the largest figure in
    the inventory -- for an article reporting one woman's death.

    "मृतककी ९० वर्षीया सासू" is the deceased's 90-year-old mother-in-law, who
    survived. The loose reverse pattern reads any digit within eight characters
    of मृत as a toll.
    """

    result = extract_np(
        'मोरङको लेटाङमा पहिरोले घर पुरिँदा महिलाको मृत्यु',
        'दुई दिनदेखि लगातार परेको वर्षापछि पहिराले घर पुरिँदा ४० वर्षीया गोपीमाया '
        'तामाङको मृत्यु भएको सो वडाका कार्यालय सचिव धनमान तामाङले जानकारी दिए ।\n\n'
        'मृतककी ९० वर्षीया सासू टुलकीमाया, ५० वर्षीय श्रीमान् टंक र १० वर्षीय '
        'छोरालाई भने स्थानीयवासीले उद्धार गरेर बचाएका छन् ।',
        '2017-08-12', None, KEYWORDS, published_year_hint=2017,
    )
    assert result['deaths'] not in (90, 40, 50), (
        f"got {result['deaths']}; a Nepali age (NN वर्षीय) was read as a toll"
    )


def test_nepali_real_toll_still_extracted() -> None:
    """The age veto must not suppress a genuine जनाको मृत्यु count."""

    result = extract_np(
        'पहिरोले घर भत्किँदा ४ जनाको मृत्यु',
        'बागलुङ, असार २० गते । पहिरोले घर भत्किँदा ४ जनाको मृत्यु भएको छ ।',
        '2021-07-04', None, KEYWORDS, published_year_hint=2021,
    )
    assert result['deaths'] == 4


def test_english_dateline_before_a_count_is_not_an_age() -> None:
    """The apposition veto must not eat "in Gulmi, 4 dead".

    myRepublica, 2024-08-05. A capitalised token then a comma then a digit is
    also what a place name looks like. Only a run of complete "Name, NN,"
    appositions is an age list.
    """

    result = extract_en(
        'Landslide buries two houses in Gulmi, 4 dead',
        'GULMI, Aug 5: A landslide buried two houses in Gulmi, 4 dead, police said.',
        '2024-08-05', None, KEYWORDS, published_year_hint=2024,
    )
    assert result['deaths'] == 4


def test_uncertain_casualty_status_blocks_explicit_zero() -> None:
    result = extract_np(
        'सिन्धुपाल्चोकमा पहिरो',
        'प्रहरीले मानवीय क्षति भएको छैन भनेको छ तर मानवीय क्षति भए नभएको '
        'अहिले यकिन गर्न नसकिने स्थानीय संवाददाताले बताए ।',
        '2021-07-30', None, KEYWORDS, published_year_hint=2021,
    )
    assert result['deaths'] is None
