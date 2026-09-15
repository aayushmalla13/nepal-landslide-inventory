"""Tests for municipality and ward backfill from article text."""

from __future__ import annotations

import pytest

from landslide_inventory.unify.place_backfill import (
    backfill_place,
    find_municipality_mentions,
    find_ward_mentions,
    snippet,
    to_int,
)

NP_ARTICLE = (
    "२९ साउन, काठमाडौं । तनहुँको म्याग्दे गाउँपालिका वडा नम्बर ६ मौरी बजारमा "
    "पहिरो खसेपछि पृथ्वी राजमार्ग अवरुद्ध भएको छ ।"
)
EN_ARTICLE = (
    "KATHMANDU, Aug 5: A landslide struck Ichhakamana Rural Municipality ward no. 6 "
    "of Chitwan district on Tuesday, blocking the Muglin road."
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("५", 5), ("१२", 12), ("7", 7), ("34", 34), ("", None), ("abc", None), ("५x", None)],
)
def test_to_int_handles_devanagari_and_rejects_junk(raw: str, expected: int | None) -> None:
    assert to_int(raw) == expected


def test_snippet_is_single_line_and_bounded() -> None:
    text = "a" * 200 + "TARGET" + "b" * 200
    result = snippet(text, 200, 206, radius=10)
    assert "TARGET" in result
    assert "\n" not in result
    assert len(result) <= 6 + 20


def test_finds_nepali_municipality_and_ward() -> None:
    mentions = find_municipality_mentions(NP_ARTICLE, "np")
    assert [m.canonical for m in mentions] == ["Myagde Rural Municipality"]
    assert mentions[0].districts == ("Tanahu",)
    wards = find_ward_mentions(NP_ARTICLE)
    assert [w.ward for w in wards] == [6]


def test_finds_english_municipality_and_ward() -> None:
    mentions = find_municipality_mentions(EN_ARTICLE, "en")
    assert "Ichchhyakamana Rural Municipality" in {m.canonical for m in mentions}
    assert [w.ward for w in find_ward_mentions(EN_ARTICLE)] == [6]


@pytest.mark.parametrize(
    "form",
    [
        "वडा नं. ६",
        "वडा नं ६",
        "वडा नम्बर ६",
        "वडानम्बर-६",
        "वडा ६",
        "Ward No. 6",
        "ward-6",
        "WARD 6",
    ],
)
def test_ward_spelling_variants_are_all_recognised(form: str) -> None:
    """The previous pattern accepted only `वडा नं.`, which is why ward was empty."""

    assert [w.ward for w in find_ward_mentions(f"पहिरो {form} मा खस्यो")] == [6]


def test_ward_numbers_outside_the_plausible_range_are_rejected() -> None:
    assert find_ward_mentions("ward no. 99") == []
    assert find_ward_mentions("वडा नं. ०") == []


def test_backfill_fills_both_fields_for_a_nepali_article() -> None:
    result = backfill_place(NP_ARTICLE, language="np", district="Tanahu")
    assert result.municipality == "Myagde Rural Municipality"
    assert result.ward == 6
    assert "म्याग्दे" in result.municipality_evidence
    assert "adjacent" in result.ward_reason


def test_backfill_never_overwrites_an_existing_value() -> None:
    result = backfill_place(
        NP_ARTICLE,
        language="np",
        district="Tanahu",
        municipality="Already Set",
        ward=3,
    )
    assert result.is_empty
    partial = backfill_place(NP_ARTICLE, language="np", district="Tanahu", municipality="Set")
    assert partial.municipality is None
    assert partial.ward == 6


def test_backfill_requires_district_agreement() -> None:
    """A municipality from another district must not be imported."""

    result = backfill_place(NP_ARTICLE, language="np", district="Kathmandu")
    assert result.is_empty


def test_backfill_returns_nothing_without_a_district() -> None:
    assert backfill_place(NP_ARTICLE, language="np", district="").is_empty


def test_ambiguous_names_resolve_only_through_the_district() -> None:
    """Godawari Municipality exists in both Lalitpur and Kailali."""

    text = "A landslide hit Godawari Municipality on Sunday."
    lalitpur = backfill_place(text, language="en", district="Lalitpur")
    kailali = backfill_place(text, language="en", district="Kailali")
    elsewhere = backfill_place(text, language="en", district="Kaski")
    assert lalitpur.municipality == "Godawari Municipality"
    assert lalitpur.municipality_ambiguous is True
    assert "shared across districts" in lalitpur.municipality_reason
    assert kailali.municipality == "Godawari Municipality"
    assert elsewhere.is_empty


def test_distant_ward_number_is_not_attached() -> None:
    """A ward chairperson quoted far from the location must not become the ward."""

    text = (
        "तनहुँको म्याग्दे गाउँपालिकामा पहिरो खस्यो । "
        + "यो घटना निकै भयावह थियो । " * 12
        + "वडा नं. ९ का वडाध्यक्षले जानकारी दिए ।"
    )
    result = backfill_place(text, language="np", district="Tanahu")
    assert result.municipality == "Myagde Rural Municipality"
    assert result.ward is None


def test_hyphenated_municipality_ward_form_is_recognised() -> None:
    text = "संखुवासभाको खाँदबारी नगरपालिका–४ सेकाहामा पहिरोले चार घर विस्थापित भए ।"
    result = backfill_place(text, language="np", district="Sankhuwasabha")
    assert result.municipality == "Khandbari Municipality"
    assert result.ward == 4


def test_no_municipality_means_no_ward_even_when_a_ward_is_present() -> None:
    text = "वडा नं. ५ मा पहिरो खस्यो ।"
    assert backfill_place(text, language="np", district="Tanahu").is_empty


def test_earliest_consistent_mention_wins() -> None:
    text = (
        "तनहुँको म्याग्दे गाउँपालिकामा पहिरो खस्यो । "
        "पछि ऋषिङ गाउँपालिकामा पनि सानो पहिरो खस्यो ।"
    )
    result = backfill_place(text, language="np", district="Tanahu")
    assert result.municipality == "Myagde Rural Municipality"


def test_suffixed_ward_must_touch_the_municipality_span() -> None:
    """A number after an unrelated hyphen must not be read as a ward."""

    attached = "सिन्धुपाल्चोकको जुगल गाउँपालिका-२ लिडीमा पहिरो खस्यो ।"
    result = backfill_place(attached, language="np", district="Sindhupalchok")
    assert result.municipality == "Jugal Rural Municipality"
    assert result.ward == 2

    detached = "सिन्धुपाल्चोकको जुगल गाउँपालिकामा पहिरो खस्यो । कोभिड-१९ का कारण उद्धार ढिलो भयो ।"
    other = backfill_place(detached, language="np", district="Sindhupalchok")
    assert other.municipality == "Jugal Rural Municipality"
    assert other.ward is None


def test_english_suffixed_ward_form() -> None:
    text = "A landslide hit Kalinchowk Rural Municipality-5 of Dolakha on Sunday."
    result = backfill_place(text, language="en", district="Dolakha")
    assert result.municipality == "Kalinchok Rural Municipality"
    assert result.ward == 5


def test_multi_digit_boundary_is_respected() -> None:
    """`Municipality-123` is not a ward; the guard must reject it."""

    text = "Landslide at Jugal Rural Municipality-123 was reported."
    result = backfill_place(text, language="en", district="Sindhupalchok")
    assert result.ward is None
