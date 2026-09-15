"""Tests for home-address (person attribution) detection.

The behaviour under test is what keeps a victim's home district from being read
as the event district. See ``src/landslide_inventory/nlp_attribution.py`` for
the worked examples these cases are drawn from.
"""

from __future__ import annotations

import pytest

from landslide_inventory.nlp_attribution import (
    ATTRIBUTION_WINDOW,
    is_person_attribution,
)


def span_of(text: str, needle: str) -> tuple[int, int]:
    start = text.index(needle)
    return start, start + len(needle)


NP_HOME = (
    "गुप्चेखोला नजिकै बाटो खन्दै गरेको बेला सिन्धुपाल्चोक जिल्लाको मेलम्ची "
    "घर भएका चालक रमेश तामाङसहित स्काभेटरलाई पुरेको हो ।"
)
NP_EVENT = "गोरखाको सिरानचोक गाउँपालिका–१ केराबारीमा शुक्रबार बिहान पहिरो गयो ।"
EN_HOME = (
    "A pilgrim died after being buried by a landslide. The deceased has been "
    "identified as Namrata Karki of Chandrpur Municipality-1, Rautahat."
)
EN_EVENT = "A landslide swept away five houses at Nagam Bazar of Tilagufa Municipality-1."


def test_nepali_home_address_is_detected() -> None:
    start, end = span_of(NP_HOME, "सिन्धुपाल्चोक")
    assert is_person_attribution(NP_HOME, start, end, "np") is True


def test_nepali_event_location_is_not_attributed() -> None:
    start, end = span_of(NP_EVENT, "सिरानचोक गाउँपालिका")
    assert is_person_attribution(NP_EVENT, start, end, "np") is False


def test_english_home_address_is_detected() -> None:
    start, end = span_of(EN_HOME, "Chandrpur Municipality-1")
    assert is_person_attribution(EN_HOME, start, end, "en") is True


def test_english_event_location_is_not_attributed() -> None:
    start, end = span_of(EN_EVENT, "Tilagufa Municipality-1")
    assert is_person_attribution(EN_EVENT, start, end, "en") is False


def test_a_cue_in_the_previous_sentence_does_not_reach_across_the_boundary() -> None:
    """An attribution cannot span a full stop, or every later name is suppressed."""

    text = (
        "The deceased has been identified as Ram Bahadur. "
        "A landslide struck Tilagufa Municipality on Sunday."
    )
    start, end = span_of(text, "Tilagufa Municipality")
    assert is_person_attribution(text, start, end, "en") is False


def test_a_danda_blocks_a_nepali_closing_cue() -> None:
    text = "जुगल गाउँपालिकामा पहिरो खस्यो । उद्धारकर्मीको काठमाडौं घर भएका थिए ।"
    start, end = span_of(text, "जुगल गाउँपालिका")
    assert is_person_attribution(text, start, end, "np") is False


def test_a_cue_beyond_the_window_does_not_attribute() -> None:
    filler = "x" * (ATTRIBUTION_WINDOW + 20)
    text = f"identified as Ram Bahadur {filler} Tilagufa Municipality"
    start, end = span_of(text, "Tilagufa Municipality")
    assert is_person_attribution(text, start, end, "en") is False


@pytest.mark.parametrize("bad_span", [(-1, 5), (0, 10_000), (5, 5), (7, 3)])
def test_out_of_range_spans_are_rejected_rather_than_raising(bad_span) -> None:
    assert is_person_attribution(EN_HOME, bad_span[0], bad_span[1], "en") is False


def test_unknown_language_checks_both_cue_sets() -> None:
    """Mixed-language articles must not lose the guard."""

    start, end = span_of(NP_HOME, "सिन्धुपाल्चोक")
    assert is_person_attribution(NP_HOME, start, end, "mixed") is True
    start, end = span_of(EN_HOME, "Chandrpur Municipality-1")
    assert is_person_attribution(EN_HOME, start, end, "mixed") is True
