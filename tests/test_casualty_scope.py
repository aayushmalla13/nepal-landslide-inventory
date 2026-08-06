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
