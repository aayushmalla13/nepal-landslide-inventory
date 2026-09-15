"""Tests for Nepali number words and the explicit-zero guards.

The project's standing rule is that an unknown casualty value is never replaced
by zero. Most of what follows therefore tests the *refusal* to emit a zero:
every guard here corresponds to a labelled article in
``data/outputs/casualty_development_casualty_v1.csv`` where the naive rule
produced a zero that the article does not support.
"""

from __future__ import annotations

import pytest

from landslide_inventory.nlp_counts import (
    NEPALI_NUMBER_WORDS,
    ROUNDUP_MARKER,
    explicit_zero_is_safe,
    parse_nepali_number,
)


@pytest.mark.parametrize(
    ("word", "expected"),
    [
        ("एक", 1),
        ("दुई", 2),
        ("तीन", 3),
        ("पाँच", 5),
        ("छ", 6),
        ("दश", 10),
        ("दस", 10),
        ("बीस", 20),
        ("पहिरो", None),
        ("", None),
    ],
)
def test_number_words_parse(word: str, expected: int | None) -> None:
    assert parse_nepali_number(word) == expected


def test_number_table_covers_one_to_twenty_without_gaps() -> None:
    assert set(NEPALI_NUMBER_WORDS.values()) == set(range(1, 21))


def test_roundup_marker_is_not_triggered_by_a_substring() -> None:
    """`कुल` sits inside `स्कुल` (school) and inside the name `कुलमान`.

    Devanagari has no ``\\b``, so a bare alternation vetoed legitimate zeros in
    articles that merely mentioned a school.
    """

    assert ROUNDUP_MARKER.search("विद्यालय स्कुल बन्द भएको छ") is None
    assert ROUNDUP_MARKER.search("कुलमान घिसिङले भने") is None
    assert ROUNDUP_MARKER.search("कुल १०० जनाको मृत्यु") is not None
    assert ROUNDUP_MARKER.search("अहिलेसम्म २७ जनाको शव") is not None


NP_CLEAN_ZERO = (
    "कर्णाली राजमार्गको कालिकोट खण्डमा पहिरो जाँदा सयौँ सवारीसाधन अलपत्र परेका "
    "छन्। पहिरोबाट मानवीय क्षति भएको छैन।"
)
EN_CLEAN_ZERO = (
    "A house has been destroyed due to a landslide in Subhang of Panchthar "
    "district on Wednesday. No human casualty has been reported, informed police."
)


def test_a_clean_no_casualty_article_may_record_zero() -> None:
    assert explicit_zero_is_safe(NP_CLEAN_ZERO, "np", extracted_any_count=False) is True
    assert explicit_zero_is_safe(EN_CLEAN_ZERO, "en", extracted_any_count=False) is True


def test_a_count_extracted_anywhere_blocks_the_zero() -> None:
    """The roundup case: one district reports no losses while others count dead."""

    assert explicit_zero_is_safe(NP_CLEAN_ZERO, "np", extracted_any_count=True) is False


def test_death_vocabulary_anywhere_blocks_the_zero() -> None:
    """The no-loss phrase covered one settlement; a body was found in the next."""

    text = NP_CLEAN_ZERO + " त्यसैगरी अर्को स्थानमा एक जनाको शव फेला परेको छ।"
    assert explicit_zero_is_safe(text, "np", extracted_any_count=False) is False

    english = EN_CLEAN_ZERO + " Elsewhere, two people died in a separate landslide."
    assert explicit_zero_is_safe(english, "en", extracted_any_count=False) is False


def test_a_roundup_blocks_the_zero() -> None:
    text = "गण्डकीमा मानवीय क्षति भएको छैन। कुल ४८ जना प्रभावित छन्।"
    assert explicit_zero_is_safe(text, "np", extracted_any_count=False) is False


def test_a_contradicted_claim_blocks_the_zero() -> None:
    """"No loss from the flood -- but there WAS loss from the landslide in Ilam."

    `क्षति` means loss or damage generally and is not death vocabulary, so this
    article passed every other guard and produced a zero for an event that
    caused losses.
    """

    text = (
        "मन्त्री घिसिङले बाढीको कारणले मानवीय क्षति भएको छैन भने। "
        "तर पहिरो गएर इलाममा भने क्षति भएको उनले बताए।"
    )
    assert explicit_zero_is_safe(text, "np", extracted_any_count=False) is False


def test_silence_about_casualties_is_never_a_zero() -> None:
    """The rule that matters most: no phrase, no zero."""

    text = "पहिरोका कारण सडक अवरुद्ध भएको छ। सवारी साधन जाममा परेका छन्।"
    assert explicit_zero_is_safe(text, "np", extracted_any_count=False) is False
    assert (
        explicit_zero_is_safe(
            "A landslide blocked the highway on Sunday.", "en", extracted_any_count=False
        )
        is False
    )


def test_not_yet_known_is_not_a_zero() -> None:
    """"The toll is not yet established" must stay unknown, not become zero."""

    for text, language in (
        ("पहिरोमा कति जना परे भन्ने यकिन हुन सकेको छैन।", "np"),
        ("The exact number of casualties is yet to be ascertained.", "en"),
    ):
        assert explicit_zero_is_safe(text, language, extracted_any_count=False) is False


def test_livestock_deaths_do_not_block_a_human_zero() -> None:
    """"No human loss, but three buffalo died" is a genuine human zero."""

    text = (
        "पहिरोमा कुनै मानवीय क्षति नभएको तर बले धामीका तीन भैँसी, तीन गोरु र "
        "सात बाख्रा मरेका छन्।"
    )
    assert explicit_zero_is_safe(text, "np", extracted_any_count=False) is True


def test_decomposed_devanagari_still_matches() -> None:
    """`नभएकाे` and `नभएको` render identically but are different byte sequences."""

    decomposed = "पहिरोमा कुनै मानवीय क्षति नभएकाे जनाइएको छ।"
    assert explicit_zero_is_safe(decomposed, "np", extracted_any_count=False) is True
