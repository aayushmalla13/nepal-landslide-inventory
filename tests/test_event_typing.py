"""Tests for event typing (road_obstruction / title_only).

These encode operator decisions, not just behaviour. If one starts failing,
check docs/log.md before changing it -- the choice may have been deliberate.
"""

from __future__ import annotations

import pytest

from landslide_inventory.unify.event_typing import (
    EVENT_TYPE_LANDSLIDE,
    EVENT_TYPE_ROAD_OBSTRUCTION,
    EXTRACTION_BASIS_FULL,
    EXTRACTION_BASIS_TITLE_ONLY,
    GRANULARITY_MULTI,
    GRANULARITY_ROUNDUP,
    GRANULARITY_SINGLE,
    ROLE_FOLLOW_UP,
    ROLE_FORECAST_OR_RISK,
    classify_event_type,
    confidence_penalty,
    summarize_typing,
)

LONG_BODY = 'The road was blocked by debris. ' * 20


def test_casualty_count_always_wins() -> None:
    """A fatal event on a highway is a landslide, not a traffic story."""

    typing = classify_event_type(
        title='Landslide blocks Narayangadh-Muglin road, two killed',
        text=LONG_BODY, deaths=2,
    )
    assert typing.event_type == EVENT_TYPE_LANDSLIDE
    assert typing.reason == 'casualties_recorded'


def test_casualty_language_without_a_count_still_wins() -> None:
    typing = classify_event_type(
        title='Highway obstructed after landslide, one missing',
        text=LONG_BODY, deaths=None, missing=None,
    )
    assert typing.event_type == EVENT_TYPE_LANDSLIDE
    assert typing.reason == 'human_impact_language'


def test_house_damage_disqualifies_road_obstruction() -> None:
    """Impact beyond the carriageway means it is not merely a road story."""

    typing = classify_event_type(
        title='Landslide blocks road in Dhading',
        text='The landslide blocked the highway and damaged two houses. ' + LONG_BODY,
    )
    assert typing.event_type == EVENT_TYPE_LANDSLIDE
    assert typing.reason == 'settlement_impact_language'


@pytest.mark.parametrize('title', [
    'Landslide disrupts Narayangadh-Muglin section',
    'Vehicles stranded for hours due to delay in clearing landslide debris',
    'नारायणगढ–मुग्लिन सडकखण्ड एकतर्फी सञ्चालनमा',
    'मुग्लिन-नारायणगढ खण्डमा पहिरो, सडक अवरूद्ध',
    'Prithvi Highway blocked by landslide, traffic halted',
])
def test_pure_road_stories_are_typed_road_obstruction(title: str) -> None:
    typing = classify_event_type(title=title, text=LONG_BODY)
    assert typing.event_type == EVENT_TYPE_ROAD_OBSTRUCTION
    if typing.hazard_type == 'landslide':
        assert typing.in_headline_counts is True
    assert typing.eligible_for_bipad is False


def test_road_obstruction_is_retained_not_deleted() -> None:
    """The decision was to keep and flag, not to exclude."""

    typing = classify_event_type(title='Landslide blocks Prithvi Highway', text=LONG_BODY)
    assert typing.event_type == EVENT_TYPE_ROAD_OBSTRUCTION
    assert typing.reason  # still carries a recorded reason


def test_ordinary_landslide_is_not_typed_as_road() -> None:
    typing = classify_event_type(
        title='Landslide buries three houses in Sindhupalchok',
        text='Three houses were buried when a landslide struck the village. ' + LONG_BODY,
    )
    assert typing.event_type == EVENT_TYPE_LANDSLIDE


def test_passing_mention_of_a_highway_is_not_a_road_obstruction() -> None:
    """Both road AND obstruction vocabulary are required, not either."""

    typing = classify_event_type(
        title='Landslide reported near Prithvi Highway',
        text='A slope failure was reported in the area. ' * 20,
    )
    assert typing.event_type == EVENT_TYPE_LANDSLIDE


def test_thin_body_is_marked_title_only() -> None:
    typing = classify_event_type(
        title='1 killed, 2 injured in Okhaldhunga landslide',
        text='OKHALDHUNGA, JUNE 26\n\nOne person was killed.', deaths=1,
    )
    assert typing.extraction_basis == EXTRACTION_BASIS_TITLE_ONLY
    assert typing.event_type == EVENT_TYPE_LANDSLIDE, 'still a real event, just weakly evidenced'


def test_full_body_is_marked_full_text() -> None:
    typing = classify_event_type(title='Landslide kills three', text=LONG_BODY, deaths=3)
    assert typing.extraction_basis == EXTRACTION_BASIS_FULL


def test_title_only_rows_are_penalised_but_not_zeroed() -> None:
    assert confidence_penalty(EXTRACTION_BASIS_TITLE_ONLY) == 0.6
    assert confidence_penalty(EXTRACTION_BASIS_FULL) == 1.0


def test_event_type_and_extraction_basis_are_independent() -> None:
    """A road story can be title-only; the two labels must not interact."""

    typing = classify_event_type(title='Landslide blocks Prithvi Highway', text='Short.')
    assert typing.event_type == EVENT_TYPE_ROAD_OBSTRUCTION
    assert typing.extraction_basis == EXTRACTION_BASIS_TITLE_ONLY


def test_granularity_distinguishes_multi_roundup_and_single_road_event() -> None:
    multi = classify_event_type(
        title='Landslides obstruct roads at several places across Nepal',
        text=LONG_BODY,
    )
    roundup = classify_event_type(
        title='Floods and landslides killed 90 people so far this monsoon',
        text=LONG_BODY,
    )
    single = classify_event_type(
        title='Landslide blocks Prithvi Highway in Chitwan',
        text=LONG_BODY,
    )
    assert multi.event_granularity == GRANULARITY_MULTI
    assert multi.in_headline_counts is False
    assert roundup.event_granularity == GRANULARITY_ROUNDUP
    assert roundup.in_headline_counts is False
    assert single.event_granularity == GRANULARITY_SINGLE
    assert single.in_headline_counts is True


def test_article_role_keeps_specific_followup_but_excludes_pure_forecast() -> None:
    followup = classify_event_type(
        title='Death toll reaches 29 in Lidi landslide',
        text='The single Lidi landslide buried homes on Friday. ' + LONG_BODY,
        deaths=29,
    )
    forecast = classify_event_type(
        title="Landslide monitoring will prevent Narayangadh road obstruction",
        text='Officials discussed preparedness before the monsoon.',
    )
    assert followup.article_role == ROLE_FOLLOW_UP
    assert followup.event_granularity == GRANULARITY_SINGLE
    assert followup.in_headline_counts is True
    assert forecast.article_role == ROLE_FORECAST_OR_RISK
    assert forecast.in_headline_counts is False


def test_summarize_keeps_road_as_a_subtype_of_headline_landslide() -> None:
    records = [
        {'event_type': EVENT_TYPE_LANDSLIDE, 'extraction_basis': EXTRACTION_BASIS_FULL},
        {'event_type': EVENT_TYPE_LANDSLIDE, 'extraction_basis': EXTRACTION_BASIS_TITLE_ONLY},
        {'event_type': EVENT_TYPE_ROAD_OBSTRUCTION, 'extraction_basis': EXTRACTION_BASIS_FULL},
    ]
    summary = summarize_typing(records)
    assert summary['total'] == 3
    assert summary['headline_events'] == 3
    assert summary['road_obstruction'] == 1
    assert summary['by_extraction_basis'][EXTRACTION_BASIS_TITLE_ONLY] == 1


# --- hazard typing -----------------------------------------------------------
# Avalanche is हिमपहिरो / हिउँपहिरो in Nepali -- literally "snow-landslide". It
# CONTAINS पहिरो, the collection keyword, so avalanches are collected as
# landslides by construction and any landslide-first check misclassifies all of
# them. 25 headline events were avalanches, Everest and Manaslu included.

from landslide_inventory.unify.event_typing import (  # noqa: E402
    HAZARD_AVALANCHE,
    HAZARD_DEBRIS_FLOW,
    HAZARD_FLOOD,
    HAZARD_LANDSLIDE,
    HAZARD_ROCKFALL,
    classify_hazard_type,
)


@pytest.mark.parametrize('title', [
    'सगरमाथाको हिमपहिरो',
    'डोल्पामा हिउँपहिरोमा परी तीन बेपत्ता',
    'मनास्लुमा हिउँ पहिरो, १० जनाभन्दा बढी घाइते',
    'बझाङमा हिम पहिरोमा परी एक महिलाको मृत्यु',
    'दार्चुलामा हिमपहिरो: यार्सा टिप्न गएका कम्तीमा ८ जना पुरिएको आशंका',
    "हिउँको ढिस्को खस्दा पर्वतारोही पुरिए",
    'Avalanches disrupt efforts to rescue bodies from landslide-hit Langtang',
])
def test_avalanches_are_not_landslides(title: str) -> None:
    assert classify_hazard_type(title, '') == HAZARD_AVALANCHE, (
        f'{title!r} is an avalanche. Nepali हिमपहिरो contains पहिरो, so a '
        'landslide-first check silently swallows every avalanche in the corpus.'
    )


@pytest.mark.parametrize('title,expected', [
    ('Landslide kills three in Sindhupalchok', HAZARD_LANDSLIDE),
    ('सिन्धुपाल्चोकमा पहिरो खस्दा दुईको मृत्यु', HAZARD_LANDSLIDE),
    ('भूस्खलनका कारण घर पुरियो', HAZARD_LANDSLIDE),
    ('Mudslide buries houses in Kaski', HAZARD_DEBRIS_FLOW),
    ('Rockfall blocks Prithvi Highway', HAZARD_ROCKFALL),
    ('Floods displace 200 families in Saptari', HAZARD_FLOOD),
])
def test_other_hazards_are_separated(title: str, expected: str) -> None:
    assert classify_hazard_type(title, '') == expected


def test_avalanche_is_excluded_from_headline_counts() -> None:
    typing = classify_event_type(
        title='सगरमाथाको हिमपहिरोमा परी तीन जनाको मृत्यु',
        text='हिमपहिरोमा परी तीन जनाको मृत्यु भयो। ' * 20, deaths=3,
    )
    assert typing.hazard_type == HAZARD_AVALANCHE
    assert typing.in_headline_counts is False
    assert typing.eligible_for_bipad is False
    assert typing.event_type == EVENT_TYPE_LANDSLIDE, 'still retained, just not headline'


def test_ordinary_landslide_stays_in_headline_counts() -> None:
    typing = classify_event_type(
        title='Landslide kills three in Sindhupalchok',
        text='A landslide buried two houses. ' * 20, deaths=3,
    )
    assert typing.hazard_type == HAZARD_LANDSLIDE
    assert typing.in_headline_counts is True


def test_title_hazard_beats_body_background_mentions() -> None:
    """Bodies routinely mention several hazards in background paragraphs."""

    typing = classify_event_type(
        title='Landslide kills two in Myagdi',
        text='Officials warned of avalanche risk in the high Himalaya. ' * 10,
        deaths=2,
    )
    assert typing.hazard_type == HAZARD_LANDSLIDE


def test_summarize_counts_non_landslide_hazards() -> None:
    records = [
        {'event_type': EVENT_TYPE_LANDSLIDE, 'extraction_basis': EXTRACTION_BASIS_FULL,
         'hazard_type': HAZARD_LANDSLIDE},
        {'event_type': EVENT_TYPE_LANDSLIDE, 'extraction_basis': EXTRACTION_BASIS_FULL,
         'hazard_type': HAZARD_AVALANCHE},
        {'event_type': EVENT_TYPE_ROAD_OBSTRUCTION, 'extraction_basis': EXTRACTION_BASIS_FULL,
         'hazard_type': HAZARD_LANDSLIDE},
    ]
    summary = summarize_typing(records)
    assert summary['headline_events'] == 2
    assert summary['non_landslide_hazard'] == 1
    assert summary['by_hazard_type'][HAZARD_AVALANCHE] == 1


# --- aggregate reports -------------------------------------------------------
# Articles stating a running total rather than an event. Before this filter the
# inventory recorded 6,242 landslide deaths (25.6/fatal event) against a real
# national toll of ~100-150/yr. "Floods, landslides claim 1000 plus lives in
# five years" contributed 480 deaths -- to Bardiya, a Terai district.

from landslide_inventory.unify.event_typing import (  # noqa: E402
    EVENT_TYPE_AGGREGATE_REPORT,
    is_aggregate_report,
)


@pytest.mark.parametrize('title', [
    'Floods, landslides claim 1000 plus lives in five years',
    '134 people dead in floods, landslides since monsoon rain',
    '90 killed in floods, landslides so far, DPM informs House',
    'At least 148 are dead in floods and landslides in Nepal',
    'गृहको समीक्षा : समन्वयमा चुक्यौं',
    'बाढी—पहिरोबाट उत्पन्न परिस्थितिबारे छलफल गर्न प्रचण्डले बोलाए',
])
def test_running_totals_are_typed_aggregate(title: str) -> None:
    assert is_aggregate_report(title) is True, f'{title!r} is a running total, not an event'


@pytest.mark.parametrize('title', [
    'Landslide kills three in Sindhupalchok',
    'सिन्धुपाल्चोकमा पहिरो खस्दा दुईको मृत्यु',
    'Eight houses swept away by landslide in Sankhuwasabha, 11 missing',
    'इलाममा पहिरोमा पुरिएर १७ जनाको मृत्यु',
    'Jhyaple Khola landslides: All 35 dead identified',
    'Landslide buries moving bus in Kakani',
])
def test_specific_incidents_are_not_aggregates(title: str) -> None:
    assert is_aggregate_report(title) is False, (
        f'{title!r} is a specific incident; typing it as an aggregate removes a '
        'real event from the inventory'
    )


def test_aggregate_beats_the_casualty_branch() -> None:
    """Order matters: an aggregate always HAS a casualty count."""

    typing = classify_event_type(
        title='Floods, landslides claim 1000 plus lives in five years',
        text='x' * 500, deaths=1000,
    )
    assert typing.event_type == EVENT_TYPE_AGGREGATE_REPORT
    assert typing.in_headline_counts is False
    assert typing.eligible_for_bipad is False


def test_a_minister_visiting_a_real_event_is_still_an_event() -> None:
    typing = classify_event_type(
        title='Minister visits Sindhupalchok where landslide killed three',
        text='x' * 500, deaths=3,
    )
    assert typing.event_type != EVENT_TYPE_AGGREGATE_REPORT
