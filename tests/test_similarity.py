"""Tests for language-neutral similarity (review section 8.2).

The property under test: an ekantipur report and a Kathmandu Post report of the
same landslide must be recognisable as the same event. token_set_ratio scores
them ~0 because Devanagari and Latin share no tokens, which is why 1,031 of
1,112 clusters were singletons.
"""

from __future__ import annotations

import pytest

from landslide_inventory.unify.similarity import (
    DEFAULT_WEIGHTS,
    MERGE_THRESHOLD,
    CasualtyVector,
    TfidfIndex,
    casualty_agreement,
    merge_rate_by_language_pair,
    normalize_for_matching,
    structured_similarity,
    transliterate_devanagari,
)


# --- transliteration ---------------------------------------------------------

@pytest.mark.parametrize('devanagari,latin', [
    ('सिन्धुपाल्चोक', 'Sindhupalchok'),
    ('धादिङ', 'Dhading'),
    ('बागलुङ', 'Baglung'),
    ('अर्घाखाँची', 'Arghakhanchi'),
    ('रोल्पा', 'Rolpa'),
    ('नुवाकोट', 'Nuwakot'),
])
def test_transliteration_brings_place_names_close(devanagari: str, latin: str) -> None:
    from rapidfuzz import fuzz

    score = fuzz.token_sort_ratio(transliterate_devanagari(devanagari), latin.casefold())
    assert score >= 80, (
        f'{devanagari} -> {transliterate_devanagari(devanagari)!r} is too far from '
        f'{latin!r} (ratio {score}); cross-script place matching will fail.'
    )


def test_transliteration_is_deterministic() -> None:
    """The pipeline's reproducibility guarantee extends here."""

    assert transliterate_devanagari('सिन्धुपाल्चोक') == transliterate_devanagari('सिन्धुपाल्चोक')


def test_latin_text_passes_through_unchanged() -> None:
    assert transliterate_devanagari('Sindhupalchok') == 'sindhupalchok'


def test_devanagari_digits_are_normalised() -> None:
    """'३ जनाको मृत्यु' and '3 dead' should share the numeric token."""

    assert '3' in transliterate_devanagari('३ जनाको मृत्यु')
    assert '12' in normalize_for_matching('१२ बेपत्ता')


def test_empty_input_is_safe() -> None:
    assert transliterate_devanagari(None) == ''
    assert normalize_for_matching(None) == ''


# --- casualty agreement ------------------------------------------------------

def test_matching_casualties_agree() -> None:
    assert casualty_agreement(CasualtyVector(3, 0, 1), CasualtyVector(3, 0, 1)) == 1.0


def test_conflicting_casualties_disagree() -> None:
    assert casualty_agreement(CasualtyVector(deaths=3), CasualtyVector(deaths=9)) == 0.0


def test_absent_casualties_are_uninformative_not_disagreement() -> None:
    """Roughly half the corpus has no casualty count.

    Scoring "nobody reported a number" as disagreement would suppress genuine
    merges across the whole low-severity end of the inventory.
    """

    assert casualty_agreement(CasualtyVector(), CasualtyVector()) is None
    assert casualty_agreement(CasualtyVector(deaths=3), CasualtyVector()) is None


def test_partial_overlap_is_scored_on_comparable_fields_only() -> None:
    left = CasualtyVector(deaths=3, missing=None, injured=2)
    right = CasualtyVector(deaths=3, missing=5, injured=9)
    assert casualty_agreement(left, right) == 0.5  # deaths agree, injured do not


# --- TF-IDF ------------------------------------------------------------------

def test_idf_downweights_boilerplate() -> None:
    """Monsoon boilerplate must not make unrelated reports look alike.

    This is the failure mode of token_set_ratio on 2,000 characters of news
    body: it ignores order and duplicates, so shared filler clears a 0.88
    threshold easily.
    """

    corpus = [
        'police said rescue teams reached the district monsoon rainfall',
        'police said rescue teams reached the district monsoon rainfall',
        'police said rescue teams reached the district monsoon rainfall',
        'police said rescue teams reached the district monsoon rainfall sindhupalchok jure',
    ]
    index = TfidfIndex(corpus)
    assert index.idf('sindhupalchok') > index.idf('police')


def test_cosine_is_high_for_near_identical_text() -> None:
    index = TfidfIndex(['landslide sindhupalchok three killed', 'flood saptari displaced'])
    assert index.cosine('landslide sindhupalchok three killed',
                        'landslide sindhupalchok three killed') > 0.99


def test_cosine_is_zero_across_scripts() -> None:
    """Not a bug -- it is the reason the structured path exists."""

    index = TfidfIndex(['landslide killed three', 'पहिरोमा परी तीनको मृत्यु'])
    assert index.cosine('landslide killed three', 'पहिरोमा परी तीनको मृत्यु') == 0.0


def test_empty_documents_do_not_crash() -> None:
    index = TfidfIndex(['', 'landslide'])
    assert index.cosine('', 'landslide') == 0.0


# --- structured similarity ---------------------------------------------------

def _score(**overrides):
    base = dict(
        left_municipality=None, right_municipality=None,
        left_ward=None, right_ward=None,
        left_casualties=CasualtyVector(), right_casualties=CasualtyVector(),
        left_trigger=None, right_trigger=None,
        left_place=None, right_place=None,
        left_text=None, right_text=None,
        left_lang='en', right_lang='np',
    )
    base.update(overrides)
    return structured_similarity(**base)


def test_cross_language_duplicate_is_recognised() -> None:
    """The real case: Arghakhanchi 2023-07-04, three deaths, two languages.

    'Three dead in Arghakhanchi landslide' (myRepublica, en) and
    'अर्घाखाँचीमा घरमाथि पहिरो खस्दा ३ जनाको मृत्यु' (Online Khabar, np).
    """

    result = _score(
        left_municipality='Sitganga Municipality', right_municipality='Sitganga Municipality',
        left_casualties=CasualtyVector(deaths=3), right_casualties=CasualtyVector(deaths=3),
        left_place='Arghakhanchi', right_place='अर्घाखाँची',
    )
    assert result.cross_language is True
    assert result.should_merge is True, result.explain()


def test_conflicting_municipality_vetoes_the_merge() -> None:
    result = _score(
        left_municipality='Sitganga Municipality', right_municipality='Malarani Rural Municipality',
        left_casualties=CasualtyVector(deaths=3), right_casualties=CasualtyVector(deaths=3),
    )
    assert result.conflict == 'municipality'
    assert result.should_merge is False


def test_conflicting_casualties_veto_the_merge() -> None:
    result = _score(
        left_municipality='Sitganga Municipality', right_municipality='Sitganga Municipality',
        left_casualties=CasualtyVector(deaths=3), right_casualties=CasualtyVector(deaths=11),
    )
    assert result.conflict == 'casualties'
    assert result.should_merge is False


def test_missing_evidence_never_penalises() -> None:
    """Weight is redistributed, so a pair is penalised for contradiction only."""

    with_ward = _score(
        left_municipality='X Municipality', right_municipality='X Municipality',
        left_ward='3', right_ward='3',
        left_casualties=CasualtyVector(deaths=2), right_casualties=CasualtyVector(deaths=2),
    )
    without_ward = _score(
        left_municipality='X Municipality', right_municipality='X Municipality',
        left_casualties=CasualtyVector(deaths=2), right_casualties=CasualtyVector(deaths=2),
    )
    assert without_ward.score == pytest.approx(with_ward.score, abs=0.01)


def test_weak_evidence_alone_does_not_merge() -> None:
    """No municipality, no casualties, only a fuzzy place name."""

    result = _score(left_place='Dhading', right_place='धादिङ')
    assert result.should_merge is False, result.explain()


def test_text_is_ignored_across_scripts() -> None:
    """Including a structurally-zero signal would sink every cross-language pair."""

    index = TfidfIndex(['landslide killed three in dhading'])
    result = _score(
        left_municipality='X Municipality', right_municipality='X Municipality',
        left_casualties=CasualtyVector(deaths=3), right_casualties=CasualtyVector(deaths=3),
        left_text='landslide killed three in dhading', right_text='धादिङमा तीनको मृत्यु',
        tfidf=index,
    )
    assert result.text == 0.0
    assert result.should_merge is True, 'zero text similarity must not veto a cross-script match'


def test_breakdown_is_auditable() -> None:
    result = _score(
        left_municipality='X Municipality', right_municipality='X Municipality',
        left_casualties=CasualtyVector(deaths=3), right_casualties=CasualtyVector(deaths=3),
    )
    assert 'muni=1.00' in result.explain()
    assert 'score=' in result.explain()


def test_weights_are_documented_and_sum_sensibly() -> None:
    assert set(DEFAULT_WEIGHTS) == {
        'municipality', 'ward', 'casualties', 'trigger', 'place_translit', 'text'
    }
    assert sum(DEFAULT_WEIGHTS.values()) == pytest.approx(1.0)


# --- acceptance reporting ----------------------------------------------------

def test_merge_rate_by_language_pair() -> None:
    stats = merge_rate_by_language_pair([
        ('en', 'np', True), ('en', 'np', False), ('np', 'en', True), ('en', 'en', False),
    ])
    assert stats['en-np'] == {'candidates': 3, 'merged': 2}
    assert stats['en-en'] == {'candidates': 1, 'merged': 0}


def test_place_name_alone_is_not_enough_even_at_a_high_score() -> None:
    """Guards the renormalisation trap directly.

    With only one signal available, renormalisation makes that signal the whole
    score. A fuzzy place-name match then reaches 0.92 on its own -- but since
    district and date are already the blocking key, two genuinely distinct
    Dhading landslides a day apart would both look like that.
    """

    result = _score(left_place='Dhading', right_place='धादिङ')
    assert result.score > MERGE_THRESHOLD, 'precondition: the raw score is high'
    assert result.has_strong_evidence is False
    assert result.should_merge is False


def test_strong_evidence_requires_agreement_not_merely_presence() -> None:
    disagreeing_ward = _score(
        left_ward='3', right_ward='7',
        left_place='Dhading', right_place='धादिङ',
    )
    assert disagreeing_ward.has_strong_evidence is False
    assert disagreeing_ward.should_merge is False
