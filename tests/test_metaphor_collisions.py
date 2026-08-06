"""Regression tests for political/financial metaphor detection.

These exist because ``METAPHOR_PATTERNS`` once contained the bare substring
``'by landslide'``. It was meant to catch "won by landslide". It also matched
"buried by landslide" and "swept away by landslide", and excluded 175 articles
of which 128 were real Nepal landslide events with casualties -- the single
largest source of false negatives in the pipeline
(docs/TECHNICAL_REVIEW.md section 2.1).

The physical-phrasing cases below are drawn from real titles in the corpus.
If one of them starts failing, a pattern has been added that collides with
ordinary landslide reporting, and it will silently delete events from the
inventory. Do not relax these tests to make a new pattern pass.
"""

from __future__ import annotations

from datetime import date

import pytest

from landslide_inventory.unify.event_specificity import (
    METAPHOR_PATTERNS,
    SpecificityRow,
    _has_metaphor_signal,
    decide_specificity,
    metaphor_exclude_terms,
)

STUDY_START = date(2015, 1, 1)
STUDY_END = date(2026, 12, 31)

# Verbatim or near-verbatim titles of real landslide events in the corpus that
# the old 'by landslide' substring excluded.
PHYSICAL_LANDSLIDE_TEXTS = [
    '11 people missing in Sankhuwasabha as eight houses are swept away by landslide',
    '10 families displaced by landslide, 20 at high risk in Sindhupalchowk',
    'Three killed after a house was buried by landslide in Dolakha',
    'Eight swept away by landslide in Myagdi, two bodies recovered',
    'Vehicles swept away by landslide on Narayangadh-Muglin road',
    '150 families abandon village in Dolakha due to landslides',
    'Landslide buries moving bus in Kakani',
    # 'Bijay' is a common Nepali given name; the old 'विजय' pattern excluded 28
    # articles containing it.
    'सिन्धुपाल्चोकमा पहिरोमा परी विजय तामाङको मृत्यु',
    'पहिरोले घर पुरिँदा तीन जनाको मृत्यु, खोजी जारी',
]

POLITICAL_METAPHOR_TEXTS = [
    'RSP wins the seat by a landslide, sweeping all constituencies',
    'Congress won by landslide in the parliamentary elections',
    'Oli swept to power by a landslide victory',
    'Landslide victory for the ruling coalition',
    'Mayor elected by a landslide in the local polls',
    'निर्वाचनमा नेपाली कांग्रेसको विजय, बहुमत नजिक',
    'मतगणना जारी, अग्रता कायमै राख्दै उम्मेदवार निर्वाचित',
]


@pytest.mark.parametrize('text', PHYSICAL_LANDSLIDE_TEXTS)
def test_physical_landslide_reports_are_not_metaphors(text: str) -> None:
    assert _has_metaphor_signal(text.casefold()) is False, (
        f'Physical landslide report misclassified as metaphor: {text!r}. '
        'A metaphor pattern is colliding with ordinary landslide reporting.'
    )


@pytest.mark.parametrize('text', POLITICAL_METAPHOR_TEXTS)
def test_political_metaphors_are_detected(text: str) -> None:
    assert _has_metaphor_signal(text.casefold()) is True, (
        f'Political metaphor not detected: {text!r}'
    )


def test_no_metaphor_pattern_matches_a_plain_landslide_report() -> None:
    """No single literal pattern may fire on ordinary landslide prose.

    Catches the collision class directly rather than via the combined signal,
    so a newly added bad pattern is named in the failure message.
    """

    baseline = 'A landslide buried three houses in Sindhupalchok and swept away a jeep.'
    baseline_cf = baseline.casefold()
    offenders = [p for p in METAPHOR_PATTERNS if p.casefold() in baseline_cf]
    assert offenders == [], (
        f'These METAPHOR_PATTERNS entries match ordinary landslide prose: {offenders}. '
        'Replace them with a context-requiring regex in METAPHOR_ELECTORAL_PATTERN.'
    )


def test_swept_away_is_physical_but_swept_to_power_is_metaphor() -> None:
    """The distinction that the 'swept' branch exists to make."""

    assert _has_metaphor_signal('eight swept away by landslide in myagdi'.casefold()) is False
    assert _has_metaphor_signal('swept to power by a landslide'.casefold()) is True


def test_config_exclude_terms_are_applied() -> None:
    """keywords.exclude used to be dead config; it must now reach the filter."""

    stock_story = 'सेयर बजारमा ६५ अंकको पहिरो, लगानीकर्ता चिन्तित'.casefold()
    assert _has_metaphor_signal(stock_story) is False, 'precondition: not caught by defaults'
    assert _has_metaphor_signal(stock_story, ('सेयर बजार',)) is True


def test_metaphor_exclude_terms_reads_nested_config() -> None:
    class _Config:
        raw = {'keywords': {'exclude': {'np': ['सेयर बजार'], 'en': ['stock slide']}}}

    terms = metaphor_exclude_terms(_Config())
    assert 'stock slide' in terms
    assert 'सेयर बजार' in terms


def test_metaphor_exclude_terms_tolerates_missing_config() -> None:
    class _Config:
        raw: dict = {}

    assert metaphor_exclude_terms(_Config()) == ()


def test_real_event_with_swept_away_phrasing_survives_the_stage() -> None:
    """End-to-end through decide_specificity, not just the signal helper."""

    row = SpecificityRow(
        url='https://example.com/sankhuwasabha',
        source='myrepublica',
        title='Eight houses swept away by landslide in Sankhuwasabha, 11 missing',
        text=(
            'A landslide swept away eight houses in Sankhuwasabha district on Tuesday. '
            'Eleven people are missing and rescue teams have recovered two bodies.'
        ),
        published_date_ad='2024-07-16',
        route_lang='en',
        mixed_flag=False,
        devanagari_ratio=0.0,
        event_class=1,
        event_date_ad='2024-07-16',
        district='Sankhuwasabha',
        municipality=None,
        deaths=None,
        missing=11,
        injured=None,
    )
    decision = decide_specificity(row, STUDY_START, STUDY_END)
    assert decision.specificity_reason != 'metaphor'
    assert decision.specificity_ok == 1
