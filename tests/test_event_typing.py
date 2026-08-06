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
    assert typing.in_headline_counts is False
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


def test_summarize_separates_headline_from_road() -> None:
    records = [
        {'event_type': EVENT_TYPE_LANDSLIDE, 'extraction_basis': EXTRACTION_BASIS_FULL},
        {'event_type': EVENT_TYPE_LANDSLIDE, 'extraction_basis': EXTRACTION_BASIS_TITLE_ONLY},
        {'event_type': EVENT_TYPE_ROAD_OBSTRUCTION, 'extraction_basis': EXTRACTION_BASIS_FULL},
    ]
    summary = summarize_typing(records)
    assert summary['total'] == 3
    assert summary['headline_events'] == 2
    assert summary['road_obstruction'] == 1
    assert summary['by_extraction_basis'][EXTRACTION_BASIS_TITLE_ONLY] == 1
