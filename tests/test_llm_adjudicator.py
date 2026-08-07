"""Tests for LLM adjudication — all run without an API key.

The point of these is that the LLM path is testable, cacheable and optional.
A stage that only works with a network connection cannot be part of a pipeline
claiming reproducibility.
"""

from __future__ import annotations

import json

import pytest

from landslide_inventory.unify.llm_adjudicator import (
    DEFAULT_MODEL,
    Adjudication,
    ResponseCache,
    adjudicate,
    anthropic_caller,
    needs_adjudication,
    parse_response,
)

GOOD = json.dumps({
    'is_landslide_event': 'yes', 'hazard_type': 'landslide',
    'event_granularity': 'single', 'article_role': 'first_report',
    'confidence': 0.9, 'reason': 'Three killed in a located landslide.',
})


def test_missing_api_key_degrades_to_rules() -> None:
    """The LLM must never be a hard dependency."""

    assert anthropic_caller(api_key='') is None


def test_no_caller_and_no_cache_returns_none(tmp_path) -> None:
    cache = ResponseCache(tmp_path / 'c.json')
    assert adjudicate('t', 'x', cache=cache, call_model=None) is None


def test_cache_makes_a_rerun_network_free(tmp_path) -> None:
    """Archiving the cache is what makes an LLM run reproducible."""

    calls = []

    def caller(system: str, user: str) -> str:
        calls.append(user)
        return GOOD

    cache = ResponseCache(tmp_path / 'c.json')
    first = adjudicate('Landslide kills three', 'body', cache=cache, call_model=caller)
    assert first is not None and first.from_cache is False
    cache.save()

    reloaded = ResponseCache(tmp_path / 'c.json')
    second = adjudicate('Landslide kills three', 'body', cache=reloaded, call_model=None)
    assert second is not None, 'a cached run must work with no caller at all'
    assert second.from_cache is True
    assert len(calls) == 1


def test_cache_key_separates_models_and_articles(tmp_path) -> None:
    cache = ResponseCache(tmp_path / 'c.json')
    a = cache.key('model-a', 'title', 'text')
    assert a != cache.key('model-b', 'title', 'text')
    assert a != cache.key('model-a', 'title', 'other text')
    assert a == cache.key('model-a', 'title', 'text'), 'must be deterministic'


def test_out_of_vocabulary_response_is_rejected_not_coerced() -> None:
    """Silently mapping a bad label to a plausible one produced 'unkown'."""

    bad = json.dumps({'is_landslide_event': 'probably', 'hazard_type': 'landslide',
                      'event_granularity': 'single', 'article_role': 'first_report'})
    assert parse_response(bad) is None


def test_unparseable_response_is_rejected() -> None:
    assert parse_response('I think this is a landslide!') is None
    assert parse_response('') is None


def test_code_fenced_json_is_tolerated() -> None:
    assert parse_response(f'```json\n{GOOD}\n```') is not None


def test_headline_definition_matches_the_scorer() -> None:
    def make(**kw):
        base = dict(is_landslide_event='yes', hazard_type='landslide',
                    event_granularity='single', article_role='first_report',
                    confidence=0.9, reason='', model=DEFAULT_MODEL, prompt_version='v1')
        base.update(kw)
        return Adjudication(**base)

    assert make().is_headline_event is True
    assert make(hazard_type='avalanche').is_headline_event is False
    assert make(event_granularity='roundup').is_headline_event is False
    assert make(is_landslide_event='no').is_headline_event is False


@pytest.mark.parametrize('reason,expected', [
    ('followup', True), ('context_only', True), ('risk_only', True),
    ('roundup', True), ('event_specific', True),
    ('out_of_country', False), ('no_location_signal', False),
])
def test_only_judgement_calls_are_sent(reason: str, expected: bool) -> None:
    """Rows the rules handle reliably must not cost a network call.

    event_specific IS included: 20 of 24 false positives were rows the rules
    confidently kept, so confidence and correctness come apart at both ends.
    """

    assert needs_adjudication(reason, 0.7) is expected
