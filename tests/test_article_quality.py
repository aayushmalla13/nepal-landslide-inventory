"""Tests for non-article detection in raw_articles.

The case that motivated this: 615 himalayan-times rows whose entire body is
"You have exceeded the rate limit. Please try again later." were stored as
articles and fed through the pipeline.
"""

from __future__ import annotations

import pytest

from landslide_inventory.validation.article_quality import (
    classify_raw_article,
    is_ingestible_article,
    summarize,
)

GOOD_URL = 'https://thehimalayantimes.com/nepal/2024/07/16/landslide-kills-three-in-sindhupalchok'
GOOD_BODY = (
    'SINDHUPALCHOK, JULY 16\n\nThree people were killed when a landslide swept away '
    'two houses in Sindhupalchok district early on Tuesday morning, police said. '
    'The deceased have been identified as members of a single family. Rescue teams '
    'from the Nepal Police and Armed Police Force reached the site and recovered '
    'all three bodies by noon. Officials said continuous rainfall had saturated the '
    'slope above the settlement over the preceding week.'
)


def test_rate_limit_page_is_not_an_article() -> None:
    verdict = classify_raw_article(
        url=GOOD_URL, title='', text='You have exceeded the rate limit. Please try again later.',
        http_status=429, parse_success=0,
    )
    assert verdict.is_article is False
    assert verdict.reason == 'http_429'


def test_rate_limit_body_caught_even_when_status_is_missing() -> None:
    """Some rows lost their status. The body still gives it away."""

    verdict = classify_raw_article(
        url=GOOD_URL, title='Something', text='You have exceeded the rate limit. Please try again later.',
        http_status=None, parse_success=None,
    )
    assert verdict.is_article is False
    assert verdict.reason == 'error_page_body'


def test_section_landing_page_is_not_an_article() -> None:
    verdict = classify_raw_article(
        url='https://kathmandupost.com/national/province-no-2',
        title='Madhesh Province - The Kathmandu Post',
        text='x' * 2000, http_status=200, parse_success=1,
    )
    assert verdict.is_article is False
    assert verdict.reason == 'section_title'


def test_section_url_without_a_dated_path_is_not_an_article() -> None:
    verdict = classify_raw_article(
        url='https://kathmandupost.com/food/recipes', title='Some heading',
        text='x' * 2000, http_status=200, parse_success=1,
    )
    assert verdict.is_article is False
    assert verdict.reason == 'section_url'


def test_dated_article_url_is_not_mistaken_for_a_section() -> None:
    """A real story under /money/ or /health/ must survive the section check."""

    verdict = classify_raw_article(
        url='https://kathmandupost.com/money/2026/03/24/gold-price-continues-to-tumble',
        title='Gold price continues to tumble', text=GOOD_BODY,
        http_status=200, parse_success=1,
    )
    assert verdict.is_article is True


def test_genuine_article_passes() -> None:
    verdict = classify_raw_article(
        url=GOOD_URL, title='Landslide kills three in Sindhupalchok',
        text=GOOD_BODY, http_status=200, parse_success=1,
    )
    assert verdict.is_article is True
    assert verdict.reason == 'ok'


def test_untitled_row_is_rejected() -> None:
    verdict = classify_raw_article(
        url=GOOD_URL, title='   ', text=GOOD_BODY, http_status=200, parse_success=1,
    )
    assert verdict.is_article is False
    assert verdict.reason == 'no_title'


def test_body_too_short_is_flagged() -> None:
    """Not junk, but too thin to extract an event from responsibly.

    50 class-1 events currently rest on himalayan-times rows like this, i.e.
    they were classified from the title alone.
    """

    verdict = classify_raw_article(
        url=GOOD_URL, title='1 killed, 2 injured in Okhaldhunga landslide',
        text='OKHALDHUNGA, JUNE 26\n\nOne person was killed and two others were injured.',
        http_status=200, parse_success=1,
    )
    assert verdict.is_article is False
    assert verdict.reason == 'body_too_short'


@pytest.mark.parametrize('status', [403, 404, 429, 500, 503])
def test_any_non_200_status_is_rejected(status: int) -> None:
    assert is_ingestible_article(GOOD_URL, 'Title', GOOD_BODY, status) is False


def test_quoting_an_error_string_mid_article_does_not_trip_the_check() -> None:
    """Markers are matched against the head of the body, not the whole thing."""

    body = GOOD_BODY + '\n\nThe site returned "you have exceeded the rate limit" to researchers.'
    assert is_ingestible_article(GOOD_URL, 'Landslide kills three', body, 200) is True


def test_summarize_groups_by_source_and_reason() -> None:
    records = [
        {'source': 'himalayan-times', 'verdict': 'not_article', 'reason': 'http_429'},
        {'source': 'himalayan-times', 'verdict': 'not_article', 'reason': 'http_429'},
        {'source': 'himalayan-times', 'verdict': 'article', 'reason': 'ok'},
        {'source': 'setopati', 'verdict': 'article', 'reason': 'ok'},
    ]
    summary = summarize(records)
    assert summary['total'] == 4
    assert summary['not_article'] == 2
    assert summary['by_reason']['http_429'] == 2
    assert summary['by_source']['himalayan-times']['not_article'] == 2
    assert summary['by_source']['setopati']['not_article'] == 0
