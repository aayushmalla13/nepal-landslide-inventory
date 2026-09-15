"""Detect place names that belong to a *person*, not to the event.

Why this module exists
----------------------
Nepali disaster reporting names two kinds of place in the same lead paragraph:

1. where the landslide happened, and
2. where the people involved are *from*.

Both are written as ordinary district and municipality names, and the second is
frequently a district far from the event:

    गोरखाको सिरानचोक गाउँपालिका–१ केराबारीमा ... पहिरोले ... सिन्धुपाल्चोक
    जिल्लाको मेलम्ची घर भएका चालक रमेश तामाङ ...
    (the landslide was in Gorkha; the driver's *home* is Melamchi,
     Sindhupalchok)

    RASUWA, Aug 3: A pilgrim ... died ... The deceased has been identified as
    Namrata Karki of Chandrpur Municipality-1, Rautahat.
    (the landslide was in Rasuwa; Chandrapur is the victim's home)

Reading the second kind as the event location silently relocates the event to
another district. Because the resulting record is internally consistent -- the
municipality really is in that district -- the error is invisible to every
consistency check the pipeline has. It surfaced when the municipality gazetteer
grew from 142 to 753 local units and many more home addresses began to resolve.

What this module does *not* do
------------------------------
It does not attempt to parse Nepali or English sentences. It recognises a small,
explicit set of attribution phrases that surround a home address, and reports
whether a character span sits inside one. That is deliberately conservative:
a missed cue leaves behaviour exactly as before, and a false cue can only cause
a place to be ignored, never invented. Every cue is a fixed phrase attested in
the corpus, not a guess.

The cue lists are deliberately narrow. Terms such as "resident" alone
("residents were evacuated") are excluded because they describe people affected
at the event site rather than an address elsewhere.
"""

from __future__ import annotations

import re

# Phrases that introduce or close a home address. A district or municipality
# name written within `ATTRIBUTION_WINDOW` characters after an opening cue, or
# before a closing cue, is treated as the address of a person.
#
# Nepali:
#   घर भएका / घर भएको      "whose home is"
#   निवासी / बासिन्दा       "resident of" (used for home villages in bios)
#   स्थायी ठेगाना            "permanent address"
#   का हुन् / की हुन्         "is from" in identification sentences
# English:
#   "identified as", "hailed from", "a resident of", "native of",
#   "permanent resident of", "of ... , who lived in"
NP_CLOSING_CUES: tuple[str, ...] = (
    'घर भएका',
    'घर भएको',
    'घर भएकी',
    'स्थायी ठेगाना',
    'स्थायी बसोबास',
)
NP_OPENING_CUES: tuple[str, ...] = (
    'निवासी',
    'बासिन्दा',
    'स्थायी ठेगाना',
)
EN_OPENING_CUES: tuple[str, ...] = (
    'identified as',
    'a resident of',
    'permanent resident of',
    'residents of',
    'native of',
    'hails from',
    'hailed from',
    'originally from',
    'who lived in',
)

# How far a name may sit from its cue and still be read as part of the address.
# Long enough to cover "identified as Namrata Karki of Chandrpur
# Municipality-1, Rautahat", short enough not to swallow the next sentence.
ATTRIBUTION_WINDOW = 90

_SENTENCE_BREAK = re.compile(r'[।\.\n]')


def _blocked_by_sentence_break(text: str) -> bool:
    """True when a sentence boundary separates the cue from the candidate.

    An attribution cannot reach across a full stop or a Devanagari danda, so a
    cue in the previous sentence must not suppress a name in this one.
    """

    return _SENTENCE_BREAK.search(text) is not None


def is_person_attribution(text: str, start: int, end: int, language: str) -> bool:
    """True when the span ``text[start:end]`` sits inside a home-address phrase.

    ``start``/``end`` are character offsets of a district or municipality
    mention. The span is judged attributed when either

    * an opening cue ("identified as", "निवासी") appears shortly before it with
      no sentence break in between, or
    * a closing cue ("घर भएका") appears shortly after it, again within the same
      sentence.

    Unknown languages fall back to checking both cue sets, which is the
    conservative direction for mixed-language articles.
    """

    if start < 0 or end > len(text) or start >= end:
        return False

    opening = list(EN_OPENING_CUES) if language == 'en' else list(NP_OPENING_CUES)
    closing: list[str] = [] if language == 'en' else list(NP_CLOSING_CUES)
    if language not in ('en', 'np'):
        opening = list(EN_OPENING_CUES) + list(NP_OPENING_CUES)
        closing = list(NP_CLOSING_CUES)

    before = text[max(0, start - ATTRIBUTION_WINDOW) : start]
    after = text[end : end + ATTRIBUTION_WINDOW]

    lowered_before = before.casefold()
    for cue in opening:
        position = lowered_before.rfind(cue.casefold())
        if position == -1:
            continue
        if not _blocked_by_sentence_break(before[position + len(cue) :]):
            return True

    for cue in closing:
        position = after.find(cue)
        if position == -1:
            continue
        if not _blocked_by_sentence_break(after[:position]):
            return True

    return False
