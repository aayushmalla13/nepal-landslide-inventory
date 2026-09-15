"""Recover municipality and ward values that are present in the text but unextracted.

Why this exists
---------------
An audit of the 3,380 event-bearing articles found two large, purely mechanical
gaps:

* **Municipality** was recorded for 40.9 per cent of articles, yet 75.9 per cent
  of them name a local unit. The binding constraint was the gazetteer, which
  listed 142 of Nepal's 753 local units, not the extraction patterns.
* **Ward** was recorded for 3 articles out of 3,380, while 12.2 per cent contain
  an explicit ward number. The existing pattern only accepted ``वडा नं.`` and the
  ward was discarded whenever a district candidate outranked it.

Design rules
------------
This module is deliberately conservative, because a wrong municipality is worse
than a missing one:

* **Additive only.** A value that already exists is never overwritten. The
  functions return a fill only when the current value is blank.
* **District agreement is required.** A municipality is accepted only when the
  gazetteer places it in the article's already-resolved district. Fifteen local
  unit names are shared across districts; those resolve only when one of their
  districts matches.
* **Wards must be anchored.** A ward number is accepted only when it sits
  immediately after an accepted municipality mention, or is written in the
  ``municipality-ward`` hyphen form. A bare ward number elsewhere in the article
  frequently belongs to a quoted ward chairperson from somewhere else.
* **Evidence is always carried.** Every fill records the matched span and a text
  snippet so a human can check it without opening the source article.
* **Nothing is imputed.** Absence of a match yields no value, never a default.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from ..gazetteer_municipality import municipality_districts, normalize_municipality
from ..nlp_attribution import is_person_attribution

NEPALI_DIGITS = {
    "०": "0",
    "१": "1",
    "२": "2",
    "३": "3",
    "४": "4",
    "५": "5",
    "६": "6",
    "७": "7",
    "८": "8",
    "९": "9",
}

NP_ADMIN_SUFFIX = r"(?:महानगरपालिका|उपमहानगरपालिका|नगरपालिका|गाउँपालिका)"
EN_ADMIN_SUFFIX = r"(?:Rural Municipality|Sub-?Metropolitan City|Metropolitan City|Municipality)"

MUNICIPALITY_NP = re.compile(rf"([ऀ-ॿ]+(?:\s+[ऀ-ॿ]+){{0,3}})\s*({NP_ADMIN_SUFFIX})")
MUNICIPALITY_EN = re.compile(
    rf"\b([A-Z][A-Za-z'.\-]*(?:\s+[A-Z][A-Za-z'.\-]*){{0,3}})\s+({EN_ADMIN_SUFFIX})\b"
)

# "वडा नं. ५", "वडा नम्बर ६", "वडानम्बर-६", "वडा ५", "Ward No. 5", "ward-5".
WARD_ANY = re.compile(
    r"(?:वडा\s*(?:नं\.?|नम्बर|नम्वर|न\.)?\s*[-–—]?\s*([०-९0-9]{1,2})"
    r"|\bward\s*(?:no\.?|number|#)?\s*[-–—]?\s*(\d{1,2})\b)",
    re.IGNORECASE,
)
# "Jugal Rural Municipality-2" or "शिवपुरी गाउँपालिका–३": the ward number is
# glued directly onto the end of the municipality name. This is the commonest
# form in both languages, and it is anchored to the municipality span rather
# than searched for loosely, so an unrelated "word-number" elsewhere in the
# article cannot be mistaken for a ward.
WARD_SUFFIX = re.compile(r"^\s*[-–—]\s*([०-९0-9]{1,2})(?![०-९0-9])")

# A ward is attached to a municipality only inside this character window after
# the municipality mention ends. Nepali datelines write them adjacently.
WARD_ATTACH_WINDOW = 80
MAX_WARD_NUMBER = 35
SNIPPET_RADIUS = 70

Language = Literal["en", "np"]


def to_int(value: str) -> int | None:
    """Parse an ASCII or Devanagari integer, returning ``None`` when malformed."""

    converted = "".join(NEPALI_DIGITS.get(char, char) for char in value or "")
    if not converted.isdigit():
        return None
    return int(converted)


def snippet(text: str, start: int, end: int, radius: int = SNIPPET_RADIUS) -> str:
    """Return a single-line evidence snippet around a matched span."""

    left = max(0, start - radius)
    right = min(len(text), end + radius)
    return " ".join(text[left:right].split())


@dataclass(frozen=True)
class MunicipalityMention:
    """A gazetteer-resolved municipality mention and where it occurred."""

    canonical: str
    raw: str
    start: int
    end: int
    language: Language
    districts: tuple[str, ...]

    @property
    def is_ambiguous(self) -> bool:
        return len(self.districts) > 1


@dataclass(frozen=True)
class WardMention:
    """A ward number and where it occurred."""

    ward: int
    raw: str
    start: int
    end: int
    form: str


@dataclass(frozen=True)
class BackfillResult:
    """What, if anything, can be filled for one article."""

    municipality: str | None = None
    municipality_evidence: str = ""
    municipality_reason: str = ""
    municipality_ambiguous: bool = False
    ward: int | None = None
    ward_evidence: str = ""
    ward_reason: str = ""

    @property
    def is_empty(self) -> bool:
        return self.municipality is None and self.ward is None


def find_municipality_mentions(text: str, language: Language) -> list[MunicipalityMention]:
    """Find every gazetteer-resolvable municipality mention, in order.

    English patterns are always applied because Nepali articles routinely carry
    English place names in quotes and datelines.
    """

    mentions: list[MunicipalityMention] = []
    patterns: list[tuple[re.Pattern[str], Language]] = [(MUNICIPALITY_EN, "en")]
    if language == "np":
        patterns.insert(0, (MUNICIPALITY_NP, "np"))
    for pattern, pattern_language in patterns:
        for match in pattern.finditer(text or ""):
            canonical = normalize_municipality(match.group(0), pattern_language)
            if canonical is None:
                continue
            # A place name attached to a PERSON is not the event location.
            #
            # This guard already governs district and municipality extraction in
            # nlp_en and nlp_np; the backfill was written without it and
            # inherited exactly the failure it prevents. On the 72-row labelled
            # review pack, 9 of the 14 rejected proposals were rejected for this
            # reason -- "the deceased person's residence", "the victim's
            # destination", "the local speaker's address" -- making it the
            # single largest source of wrong fills rather than an edge case.
            if is_person_attribution(text or "", match.start(), match.end(), pattern_language):
                continue
            mentions.append(
                MunicipalityMention(
                    canonical=canonical,
                    raw=match.group(0).strip(),
                    start=match.start(),
                    end=match.end(),
                    language=pattern_language,
                    districts=municipality_districts(canonical),
                )
            )
    return sorted(mentions, key=lambda mention: mention.start)


def find_ward_mentions(text: str) -> list[WardMention]:
    """Find every explicit ward number, in order."""

    mentions: list[WardMention] = []
    for match in WARD_ANY.finditer(text or ""):
        value = to_int(match.group(1) or match.group(2) or "")
        if value is None or not 1 <= value <= MAX_WARD_NUMBER:
            continue
        mentions.append(
            WardMention(
                ward=value,
                raw=match.group(0).strip(),
                start=match.start(),
                end=match.end(),
                form="explicit",
            )
        )
    return sorted(mentions, key=lambda mention: mention.start)


def _consistent(
    mentions: list[MunicipalityMention], district: str
) -> list[MunicipalityMention]:
    """Keep only mentions the gazetteer places in the article's district."""

    return [mention for mention in mentions if district and district in mention.districts]


def _hyphen_ward_for(text: str, mention: MunicipalityMention) -> WardMention | None:
    """Match the ``Jugal Rural Municipality-2`` form.

    Only the few characters immediately following the municipality span are
    examined, so the number is unambiguously that municipality's ward.
    """

    match = WARD_SUFFIX.match(text[mention.end : mention.end + 8])
    if match is None:
        return None
    value = to_int(match.group(1))
    if value is None or not 1 <= value <= MAX_WARD_NUMBER:
        return None
    return WardMention(
        ward=value,
        raw=f"{mention.raw}{match.group(0).rstrip()}",
        start=mention.start,
        end=mention.end + match.end(),
        form="suffixed",
    )


def backfill_place(
    text: str,
    *,
    language: Language,
    district: str,
    municipality: str | None = None,
    ward: str | int | None = None,
) -> BackfillResult:
    """Return the municipality and ward that can be safely recovered from text.

    Both values are filled only when currently blank and only when the evidence
    is district-consistent. Returns an empty result when nothing qualifies.
    """

    has_municipality = str(municipality or "").strip() not in ("", "None", "unknown")
    has_ward = str(ward or "").strip() not in ("", "None", "unknown")
    if has_municipality and has_ward:
        return BackfillResult()

    mentions = find_municipality_mentions(text, language)
    consistent = _consistent(mentions, district)
    if not consistent:
        return BackfillResult()

    # Prefer the mention that is both district-consistent and earliest; Nepali
    # reports place the event location in the opening sentence.
    chosen = consistent[0]

    filled_municipality = None
    municipality_evidence = ""
    municipality_reason = ""
    if not has_municipality:
        filled_municipality = chosen.canonical
        municipality_evidence = snippet(text, chosen.start, chosen.end)
        municipality_reason = (
            "gazetteer match in the article district"
            if not chosen.is_ambiguous
            else "gazetteer match; name is shared across districts, resolved by district agreement"
        )

    filled_ward = None
    ward_evidence = ""
    ward_reason = ""
    if not has_ward:
        wards = find_ward_mentions(text)
        for mention in consistent:
            attached = next(
                (
                    candidate
                    for candidate in wards
                    if -5 <= candidate.start - mention.end <= WARD_ATTACH_WINDOW
                ),
                None,
            )
            if attached is None:
                attached = _hyphen_ward_for(text, mention)
            if attached is not None:
                filled_ward = attached.ward
                ward_evidence = snippet(text, mention.start, max(mention.end, attached.end))
                ward_reason = f"ward {attached.form} and adjacent to {mention.canonical}"
                if filled_municipality is None and not has_municipality:
                    filled_municipality = mention.canonical
                break

    return BackfillResult(
        municipality=filled_municipality,
        municipality_evidence=municipality_evidence,
        municipality_reason=municipality_reason,
        municipality_ambiguous=chosen.is_ambiguous,
        ward=filled_ward,
        ward_evidence=ward_evidence,
        ward_reason=ward_reason,
    )
