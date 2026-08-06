"""A dateline records where a story was filed, not where the event happened.

_find_explicit_district used to fall back to the dateline when no other
district could be found. The Kathmandu veto in that function was therefore
cosmetic: the dateline still decided the answer in precisely the case where it
is least trustworthy -- an article with no place in it at all.

Measured before the fix: 27 class-1 English rows had a district only because of
that fallback, and all 27 were Kathmandu. They are nationwide roundups,
government relief announcements and share-market metaphors.
"""

from __future__ import annotations

from landslide_inventory.nlp_en.extract import (
    _find_explicit_district,
    _normalize_district_en,
    find_dateline_district,
)

ROUNDUP = (
    'Resize Text Size Small Medium Large Listen By Republica\n'
    'KATHMANDU, September 5: At least 134 people have died in floods and '
    'landslides since the onset of the monsoon this year, according to the '
    'National Disaster Risk Reduction and Management Authority.\n'
    'The authority said damage has been reported from several parts of the country.'
)

REAL_EVENT = (
    'KATHMANDU, July 12: A landslide swept away three houses in Sindhupalchok '
    'district early on Tuesday, police said.'
)


def test_dateline_alone_does_not_produce_a_district() -> None:
    assert _find_explicit_district(ROUNDUP, _normalize_district_en) is None, (
        'A nationwide roundup filed from Kathmandu must not be assigned to '
        'Kathmandu district. Null is honest; wrong is invisible and fatal.'
    )


def test_a_real_district_still_beats_the_dateline() -> None:
    assert _find_explicit_district(REAL_EVENT, _normalize_district_en) == 'Sindhupalchok'


def test_dateline_is_still_recoverable_for_provenance() -> None:
    """Removed from the answer, not thrown away."""

    assert find_dateline_district(ROUNDUP, _normalize_district_en) == 'Kathmandu'


def test_find_dateline_returns_none_when_absent() -> None:
    assert find_dateline_district('A landslide occurred.', _normalize_district_en) is None
