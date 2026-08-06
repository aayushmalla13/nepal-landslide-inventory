"""Event typing: what kind of thing each retained row actually is.

Two orthogonal labels, both decided by the operator and recorded here so the
methods section can state them rather than leaving them implicit in a pattern
list.

``event_type``
--------------
Review section 4.2: 224 of 1,071 canonical events (21%) have road or highway in
the representative title, and Chitwan reached #2 in the district table almost
entirely on Narayangadh-Muglin road-obstruction articles. A single corridor
generating recurrent minor blockages was being counted as dozens of distinct
landslide events, and the corridor straddles the Chitwan-Tanahu boundary so even
the district attribution is unstable.

Worse, the exclusion was *inconsistent*: some road articles were dropped by the
FOLLOWUP patterns (``सञ्चालनमा``, ``खुल्यो``, ``खुलेको`` -- 165 suspected real
events between them, per ``--stage pattern_audit``) while others survived into
``canonical_events``. Same class of article, two different fates, decided by
which Nepali verb the sub-editor happened to use.

**Decision: keep them, typed.** ``event_type = 'road_obstruction'`` marks a
slope failure reported only through its effect on a road, with no casualties and
no settlement impact. They stay in the dataset -- they are real slope failures
and excluding them silently would be its own bias -- but they are excluded from
headline counts and from the BIPAD comparison, where the unit of analysis does
not match.

``extraction_basis``
--------------------
50 class-1 events rest on a himalayan-times row with under 200 characters of
body, i.e. they were classified from the title alone with no verifiable detail.
Several are plainly real ("1 killed, 2 injured in Okhaldhunga landslide"), so
dropping them loses true events; trusting them equally overstates what the
pipeline actually saw.

**Decision: keep them, flagged** as ``extraction_basis = 'title_only'`` with
reduced confidence, so any analysis needing body-level detail (casualty counts,
trigger attribution, municipality resolution) can exclude them explicitly.

Many of these bodies are thin because of the same rate-limiting that produced
615 outright HTTP 429 rows (see ``validation/article_quality.py``). Re-fetching
that outlet should convert a large share of ``title_only`` rows into full ones.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import re
from typing import Any

LOGGER = logging.getLogger(__name__)

EVENT_TYPE_LANDSLIDE = 'landslide'
EVENT_TYPE_ROAD_OBSTRUCTION = 'road_obstruction'

EXTRACTION_BASIS_FULL = 'full_text'
EXTRACTION_BASIS_TITLE_ONLY = 'title_only'

# Bodies at or below this are too thin to have supported extraction. Matches
# MIN_BODY_CHARS in validation/article_quality.py -- keep them in step.
TITLE_ONLY_BODY_CHARS = 200

# Road/highway infrastructure vocabulary, EN and NP.
ROAD_TERMS_PATTERN = re.compile(
    r'\b(?:highway|high\s*way|road|roadway|road\s*section|carriageway|track)\b'
    r'|सडक|राजमार्ग|मार्ग|बाटो|सडकखण्ड|खण्ड',
    re.IGNORECASE,
)

# Obstruction/clearance vocabulary -- what happens to a road, not to people.
OBSTRUCTION_TERMS_PATTERN = re.compile(
    # Inflections matter: headlines use the present tense ("Landslide blocks
    # Prithvi Highway") far more than the past. Matching only 'blocked' missed
    # the commonest form entirely.
    r'\b(?:block|blocks|blocked|blocking|obstruct|obstructs|obstructed|'
    r'disrupt|disrupts|disrupted|disruption|close|closes|closed|shut|shuts|'
    r'halt|halts|halted|strand|strands|stranded|clear|clears|cleared|clearing|'
    r'reopen|reopens|reopened|resume|resumes|resumed|one-way|traffic)\b'
    r'|अवरुद्ध|अवरूद्ध|अवरोध|ठप्प|बन्द|हटाइयो|पन्छाइयो|पन्छाएपछि|सुचारु|'
    r'सञ्चालनमा|खुल्यो|खुलेको|खुलेन|एकतर्फी|यातायात',
    re.IGNORECASE,
)

# Human/settlement impact. Any of these means it is not merely a road story,
# regardless of how much road vocabulary surrounds it.
HUMAN_IMPACT_PATTERN = re.compile(
    r'\b(?:killed|dead|death|died|deceased|body|bodies|missing|injured|hurt|'
    r'buried|swept\s+away|displaced|homeless|rescued|trapped|casualt)\w*\b'
    r'|मृत्यु|मृतक|शव|बेपत्ता|घाइते|पुरिए|पुरिँदा|बगायो|बेघर|विस्थापित|उद्धार|घाइ',
    re.IGNORECASE,
)

# Damage to dwellings/land also disqualifies road_obstruction: the event had
# impact beyond the carriageway even if nobody was hurt.
SETTLEMENT_IMPACT_PATTERN = re.compile(
    r'\b(?:house|houses|home|homes|household|households|village|settlement|'
    r'school|shed|cowshed|farmland|cattle)\b'
    r'|घर|घरहरू|बस्ती|गाउँ|विद्यालय|गोठ|खेत|पशु',
    re.IGNORECASE,
)


@dataclass(frozen=True)
class EventTyping:
    event_type: str
    extraction_basis: str
    reason: str

    @property
    def in_headline_counts(self) -> bool:
        """Whether this row belongs in the paper's headline event count."""

        return self.event_type == EVENT_TYPE_LANDSLIDE

    @property
    def eligible_for_bipad(self) -> bool:
        """Road obstructions have no counterpart unit in BIPAD."""

        return self.event_type == EVENT_TYPE_LANDSLIDE


def classify_event_type(
    title: str | None,
    text: str | None,
    deaths: int | None = None,
    missing: int | None = None,
    injured: int | None = None,
) -> EventTyping:
    """Type a retained event as a landslide or a road obstruction.

    Conservative by design: anything with a casualty count, a casualty word, or
    damage to houses/land stays ``landslide``. A row is only downgraded to
    ``road_obstruction`` when the *sole* reported consequence is to a road.
    """

    heading = (title or '').strip()
    body = (text or '').strip()
    combined = f'{heading}\n{body}'

    basis = (
        EXTRACTION_BASIS_TITLE_ONLY
        if len(body) < TITLE_ONLY_BODY_CHARS
        else EXTRACTION_BASIS_FULL
    )

    if any(value for value in (deaths, missing, injured) if value):
        return EventTyping(EVENT_TYPE_LANDSLIDE, basis, 'casualties_recorded')
    if HUMAN_IMPACT_PATTERN.search(combined):
        return EventTyping(EVENT_TYPE_LANDSLIDE, basis, 'human_impact_language')
    if SETTLEMENT_IMPACT_PATTERN.search(combined):
        return EventTyping(EVENT_TYPE_LANDSLIDE, basis, 'settlement_impact_language')

    # No human or settlement impact anywhere. Is the road the whole story?
    # Require both signals in the TITLE: a body that merely mentions a highway
    # in passing is not a road-obstruction report.
    if ROAD_TERMS_PATTERN.search(heading) and OBSTRUCTION_TERMS_PATTERN.search(heading):
        return EventTyping(EVENT_TYPE_ROAD_OBSTRUCTION, basis, 'road_obstruction_title')
    if ROAD_TERMS_PATTERN.search(combined) and OBSTRUCTION_TERMS_PATTERN.search(combined):
        return EventTyping(EVENT_TYPE_ROAD_OBSTRUCTION, basis, 'road_obstruction_body')

    return EventTyping(EVENT_TYPE_LANDSLIDE, basis, 'default_landslide')


def confidence_penalty(basis: str) -> float:
    """Multiplier applied to extraction confidences for title-only rows.

    A title-derived event is a real observation, but a weaker one: the body
    carried no municipality, no ward, no trigger and no corroborating detail.
    0.6 keeps such rows clearly rankable below full-text rows without pretending
    they are worthless.
    """

    return 0.6 if basis == EXTRACTION_BASIS_TITLE_ONLY else 1.0


def summarize_typing(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Counts for the methods-section disclosure."""

    types: dict[str, int] = {}
    bases: dict[str, int] = {}
    for record in records:
        types[record['event_type']] = types.get(record['event_type'], 0) + 1
        bases[record['extraction_basis']] = bases.get(record['extraction_basis'], 0) + 1
    total = len(records)
    headline = types.get(EVENT_TYPE_LANDSLIDE, 0)
    return {
        'total': total,
        'headline_events': headline,
        'road_obstruction': types.get(EVENT_TYPE_ROAD_OBSTRUCTION, 0),
        'by_event_type': dict(sorted(types.items(), key=lambda kv: -kv[1])),
        'by_extraction_basis': dict(sorted(bases.items(), key=lambda kv: -kv[1])),
    }
