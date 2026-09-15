"""The Nepali anthropogenic trigger: earthworks as cause, not as aftermath.

The analysis drops `anthropogenic` and `earthquake` events, so whatever the
trigger classifier calls anthropogenic leaves the study. The English route has
always required two things -- a configured term *and* a phrase placing the
earthworks at the failure. The Nepali route required only the term, and its
three configured terms were `सडक विस्तार`, `डोजर` and `निर्माण`.

Two of those are aftermath words. A `डोजर` is the machine that clears a
landslide; `निर्माण` appears in every "निर्माणाधीन सडक", and a road under
construction is where landslides happen rather than a reason the slope moved.
Between them they tagged 452 canonical events anthropogenic -- 416 of them
Nepali-route -- and the great majority were ordinary rainfall-triggered
landslides that the analysis then threw away.

Meanwhile the actual anthropogenic burials, by *placed* earth, used none of
those three words and arrived as `unknown`.

These tests pin both directions, because a fix to one that regressed the other
would leave the classifier no better than before.
"""

from __future__ import annotations

import pytest

from landslide_inventory.nlp_np.extract import (
    NP_ANTHROPOGENIC_CONTEXT,
    _extract_trigger,
    _has_anthropogenic_trigger_np,
)

# The configured Nepali vocabulary, matching config.yaml after the audit.
TERMS = [
    'सडक विस्तार', 'डोजर', 'निर्माण',
    'ढिस्को', 'ढिस्का', 'प्लटिङ', 'क्रसर', 'उत्खनन', 'खन्ने', 'खन्दै',
]
TRIGGER_TERMS = {
    'earthquake': ['भूकम्प', 'कम्पन'],
    'road_construction': TERMS,
    'rainfall': ['वर्षा', 'पानी', 'झरी'],
}


# ---------------------------------------------------------------------------
# A real landslide must not be thrown away because a dozer turned up
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        # The dozer is what CLEARS the landslide.
        'अविरल वर्षाका कारण पहिरो खस्दा सडक अवरुद्ध भयो, डोजर लगाएर पहिरो पन्छाइँदै छ ।',
        # "Road under construction" is where landslides happen, not why.
        'निर्माणाधीन सडकमा वर्षाका कारण पहिरो खस्दा यातायात ठप्प भएको छ ।',
        # Reconstruction after the fact.
        'पहिरोले क्षति पुर्‍याएपछि सडकको पुनर्निर्माण गर्नुपर्ने भएको छ ।',
    ],
)
def test_earthworks_in_the_aftermath_do_not_make_a_landslide_anthropogenic(text):
    assert _has_anthropogenic_trigger_np(text, TERMS) is False


def test_a_rainfall_landslide_mentioning_a_dozer_is_still_rainfall_triggered():
    """The end-to-end consequence. Under the old rule this event left the
    analysis entirely."""

    text = 'कालीखोलामा अविरल वर्षाका कारण पहिरो खस्यो, मुग्लिन सडक अवरुद्ध, डोजर परिचालन'
    trigger, _ = _extract_trigger(text, TRIGGER_TERMS)
    assert trigger == 'rainfall'


def test_an_undated_road_blockage_with_construction_context_stays_unknown():
    """`unknown` keeps the event in the analysis, which is right: not knowing
    the trigger is not evidence that a machine caused it."""

    text = 'निर्माणाधीन सडकखण्डमा पहिरो खस्दा यातायात अवरुद्ध भएको छ ।'
    trigger, _ = _extract_trigger(text, TRIGGER_TERMS)
    assert trigger == 'unknown'


# ---------------------------------------------------------------------------
# A burial by placed earth must be caught
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        'दाङमा माटोको ढिस्कोले पुरिएर महिलाको मृत्यु भएको छ ।',
        'बालुवाको ढिस्कोमा पुरिएर एकको मृत्यु, दुई घाइते ।',
        'नैकापमा जग्गा प्लटिङ गरेको ठाउँमा पर्खाल लगाउँदा माटोको ढिस्कोले पुरेर दुई जनाको मृत्यु ।',
        'माटो खन्ने क्रममा ढिस्कोले पुरिएर एक जनाको मृत्यु ।',
        'काभ्रेको ढुंगाखानीमा क्रसर नजिकै ढिस्कोले पुरिएर एक जनाको मृत्यु ।',
    ],
)
def test_a_burial_by_placed_earth_is_anthropogenic(text):
    assert _has_anthropogenic_trigger_np(text, TERMS) is True
    trigger, confidence = _extract_trigger(text, TRIGGER_TERMS)
    assert trigger == 'anthropogenic'
    assert confidence > 0.8


def test_placed_earth_beats_a_rainfall_mention():
    """Trigger extraction is ordered, and anthropogenic is tested before
    rainfall on purpose: a spoil heap that collapses in the monsoon is still a
    spoil heap."""

    text = 'वर्षाका बीच माटोको ढिस्कोले पुरिएर एक जनाको मृत्यु भएको छ ।'
    trigger, _ = _extract_trigger(text, TRIGGER_TERMS)
    assert trigger == 'anthropogenic'


# ---------------------------------------------------------------------------
# Both halves are load-bearing
# ---------------------------------------------------------------------------


def test_the_context_phrase_alone_is_not_enough():
    """Without a configured term the gate never opens, which keeps the
    vocabulary in config rather than buried in code."""

    assert _has_anthropogenic_trigger_np('माटोको ढिस्को देखियो', []) is False


def test_the_term_alone_is_not_enough():
    assert _has_anthropogenic_trigger_np('डोजर परिचालन गरियो', TERMS) is False


def test_labourers_are_not_treated_as_evidence_of_a_cause():
    """Deliberately absent from the context list. Labourers are killed by real
    landslides too, and their presence says nothing about what moved the
    slope."""

    assert not any('मजदुर' in phrase for phrase in NP_ANTHROPOGENIC_CONTEXT)
    assert not any('कामदार' in phrase for phrase in NP_ANTHROPOGENIC_CONTEXT)
    text = 'पहिरोमा पुरिएर निर्माण मजदुरको मृत्यु भएको छ ।'
    assert _has_anthropogenic_trigger_np(text, TERMS) is False


def test_earthquake_still_wins_over_everything():
    text = 'भूकम्पका कारण माटोको ढिस्कोले पुरिएर मृत्यु भएको छ ।'
    trigger, _ = _extract_trigger(text, TRIGGER_TERMS)
    assert trigger == 'earthquake'


def test_the_two_language_routes_now_have_the_same_shape():
    """The defect was structural, not lexical: one route required a confirming
    phrase and the other did not. If the Nepali gate is ever reduced back to a
    bare term match this fails."""

    from landslide_inventory.nlp_en.extract import _has_anthropogenic_trigger

    en_text = 'a landslide during road expansion and excavation buried the workers'
    en_terms = ['road expansion', 'excavator', 'construction']
    assert _has_anthropogenic_trigger(en_text, en_terms) is True
    assert _has_anthropogenic_trigger('an excavator cleared the landslide', en_terms) is False
    assert _has_anthropogenic_trigger_np('डोजरले पहिरो पन्छायो', TERMS) is False
