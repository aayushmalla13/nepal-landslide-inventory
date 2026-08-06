"""Language-neutral similarity for cross-script event deduplication.

The problem
-----------
``dedup_stage.compute_similarity`` scores a candidate pair with
``rapidfuzz.token_set_ratio`` over raw title and body text. Devanagari and Latin
share no tokens, so an ekantipur report and a Kathmandu Post report of the same
landslide score ~0 and can never merge. The only cross-language path in the
existing code (district + date + deaths) is gated *behind* that string check and
is therefore unreachable (review section 4.3).

Measured on the current inventory: 1,031 of 1,112 clusters are singletons, and
there are 211 cross-language candidate pairs (same district, dates within a day)
that the string check cannot see. Eight of them have matching casualty counts
and are unmistakably one event counted twice -- Baglung 2024-08-06 with six
deaths appears three times, once per outlet.

**The bias has a direction.** Every one of those confirmed duplicates is a fatal
event with 2-6 deaths. Bilingual coverage tracks severity, so large events are
double-counted relative to small ones. This inflates the fatal-event rate
specifically, not the event count uniformly, and it distorts the spatial
distribution wherever coverage is uneven.

The approach
------------
Stop trying to compare scripts and compare *facts* instead. Most of the signal
needed here is already language-neutral and simply was not being used:

``municipality`` / ``ward`` / ``district``
    Already gazetteer-normalised to a canonical English form on both sides, so
    they compare directly regardless of the article's language. This is the
    strongest available evidence and the existing code only ever used it as a
    veto, never as positive evidence.

``deaths`` / ``missing`` / ``injured``
    Integers. "३ जनाको मृत्यु" and "three dead" both extract to 3.

Devanagari digits
    ०-९ normalise to 0-9, which makes numeric tokens comparable across scripts
    before any text similarity is attempted.

Transliteration
    Only needed for place names *not* in the gazetteer -- villages, tols,
    settlement names. A fixed, deterministic table, never a learned model, so
    the pipeline stays reproducible.

TF-IDF cosine, within-language only
    Replaces ``token_set_ratio`` on 2,000 characters of news body.
    ``token_set_ratio`` ignores order and duplicates, so two unrelated monsoon
    reports easily clear a 0.88 threshold -- the existing scheme manages to
    over-merge and under-merge simultaneously, in different regimes. IDF
    down-weights the monsoon boilerplate that makes unrelated reports look
    alike.

On the weights
--------------
They are fixed and deliberately conservative, NOT fitted. Fitting them requires
a dev set, and the locked test set is not yet labelled. Per review section 8.2
the weights should be fit on dev and reported on test; until then these encode
a defensible prior (agreeing municipality and casualties are strong evidence;
text similarity alone is not) and should be treated as provisional.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import re
import unicodedata
from collections import Counter
from typing import Iterable, Mapping, Sequence

from rapidfuzz import fuzz

# --- Devanagari digits -------------------------------------------------------
# "३ जनाको मृत्यु" and "3 dead" describe the same casualty count. Normalising
# the digits is the cheapest cross-script signal available and nothing in the
# pipeline was doing it.
DEVANAGARI_DIGITS = str.maketrans('०१२३४५६७८९', '0123456789')

# --- Transliteration ---------------------------------------------------------
# Deliberately a fixed table rather than a library or a learned model: the
# pipeline's determinism guarantee (utils.stable_hash, sorted iteration, seeded
# sampling) extends to this. Ordered longest-first so conjuncts and aspirated
# consonants are consumed before their prefixes -- 'ध' must not be matched as
# 'द' + vowel sign.
_TRANSLITERATION_PAIRS: tuple[tuple[str, str], ...] = (
    ('क्ष', 'ksh'), ('त्र', 'tra'), ('ज्ञ', 'gya'), ('श्र', 'shra'),
    ('ख', 'kh'), ('घ', 'gh'), ('छ', 'ch'), ('झ', 'jh'), ('ठ', 'th'),
    ('ढ', 'dh'), ('थ', 'th'), ('ध', 'dh'), ('फ', 'ph'), ('भ', 'bh'),
    ('क', 'k'), ('ग', 'g'), ('ङ', 'n'), ('च', 'c'), ('ज', 'j'), ('ञ', 'n'),
    ('ट', 't'), ('ड', 'd'), ('ण', 'n'), ('त', 't'), ('द', 'd'), ('न', 'n'),
    ('प', 'p'), ('ब', 'b'), ('म', 'm'), ('य', 'y'), ('र', 'r'), ('ल', 'l'),
    ('व', 'w'), ('श', 'sh'), ('ष', 'sh'), ('स', 's'), ('ह', 'h'),
    ('ा', 'a'), ('ि', 'i'), ('ी', 'i'), ('ु', 'u'), ('ू', 'u'),
    ('े', 'e'), ('ै', 'ai'), ('ो', 'o'), ('ौ', 'au'), ('ृ', 'ri'),
    ('अ', 'a'), ('आ', 'a'), ('इ', 'i'), ('ई', 'i'), ('उ', 'u'), ('ऊ', 'u'),
    ('ए', 'e'), ('ऐ', 'ai'), ('ओ', 'o'), ('औ', 'au'),
    ('ं', 'n'), ('ँ', 'n'), ('ः', 'h'), ('्', ''), ('़', ''), ('ऽ', ''),
)


def transliterate_devanagari(text: str | None) -> str:
    """Map Devanagari to a rough Latin form for fuzzy place-name comparison.

    Not a faithful romanisation and not trying to be. The only requirement is
    that the same place name written in either script lands close enough for
    rapidfuzz to recognise -- सिन्धुपाल्चोक against Sindhupalchok. Anything more
    faithful would add dependencies and non-determinism for no gain, since
    district and municipality names already resolve through the gazetteer.
    """

    if not text:
        return ''
    result = text.translate(DEVANAGARI_DIGITS)
    for source, target in _TRANSLITERATION_PAIRS:
        result = result.replace(source, target)
    # Strip any Devanagari that survived, then fold case and collapse runs.
    result = ''.join(ch for ch in result if not ('ऀ' <= ch <= 'ॿ'))
    result = unicodedata.normalize('NFKD', result)
    result = ''.join(ch for ch in result if not unicodedata.combining(ch))
    return re.sub(r'\s+', ' ', result).strip().casefold()


def normalize_for_matching(text: str | None) -> str:
    """Case-fold, normalise digits, and strip punctuation for token comparison."""

    if not text:
        return ''
    folded = text.translate(DEVANAGARI_DIGITS).casefold()
    return re.sub(r'\s+', ' ', re.sub(r'[^\w\sऀ-ॿ]+', ' ', folded)).strip()


# --- Casualty vector ---------------------------------------------------------

@dataclass(frozen=True)
class CasualtyVector:
    """Language-neutral casualty counts."""

    deaths: int | None = None
    missing: int | None = None
    injured: int | None = None

    @property
    def is_empty(self) -> bool:
        return all(v is None for v in (self.deaths, self.missing, self.injured))


def casualty_agreement(left: CasualtyVector, right: CasualtyVector, tolerance: int = 0) -> float | None:
    """Agreement in [0, 1] between two casualty vectors, or None if uninformative.

    Returns ``None`` rather than 0.0 when neither side reports anything, so an
    absence of data is never mistaken for disagreement -- roughly half the
    corpus has no casualty count at all, and scoring those as "disagree" would
    suppress genuine merges.

    A *conflict* (both sides report, and they differ beyond tolerance) is
    strong evidence against a merge and returns 0.0.
    """

    comparable = 0
    agreeing = 0
    for attribute in ('deaths', 'missing', 'injured'):
        lhs, rhs = getattr(left, attribute), getattr(right, attribute)
        if lhs is None or rhs is None:
            continue
        comparable += 1
        if abs(int(lhs) - int(rhs)) <= tolerance:
            agreeing += 1
    if comparable == 0:
        return None
    return agreeing / comparable


# --- TF-IDF ------------------------------------------------------------------

class TfidfIndex:
    """Minimal deterministic TF-IDF cosine over the corpus.

    Hand-rolled rather than pulled from scikit-learn: the project's dependency
    set is small and pinned, and this needs to be reproducible byte-for-byte.
    Roughly forty lines, no training, no state beyond document frequencies.

    Why this replaces token_set_ratio for bodies: token_set_ratio ignores order
    and duplicates, so two unrelated monsoon reports sharing boilerplate
    ("rescue teams", "police said", "monsoon", "district") clear a 0.88
    threshold easily. IDF down-weights exactly those terms.
    """

    def __init__(self, documents: Iterable[str], min_token_length: int = 2) -> None:
        self.min_token_length = min_token_length
        self._document_frequency: Counter[str] = Counter()
        self._document_count = 0
        for document in documents:
            self._document_count += 1
            self._document_frequency.update(set(self.tokenize(document)))

    def tokenize(self, text: str | None) -> list[str]:
        normalized = normalize_for_matching(text)
        return [t for t in normalized.split() if len(t) >= self.min_token_length]

    def idf(self, token: str) -> float:
        # Smoothed IDF; +1 everywhere so an unseen token is finite rather than
        # infinitely informative.
        return math.log((self._document_count + 1) / (self._document_frequency.get(token, 0) + 1)) + 1.0

    def vector(self, text: str | None) -> dict[str, float]:
        tokens = self.tokenize(text)
        if not tokens:
            return {}
        counts = Counter(tokens)
        total = float(len(tokens))
        return {token: (count / total) * self.idf(token) for token, count in counts.items()}

    def cosine(self, left: str | None, right: str | None) -> float:
        a, b = self.vector(left), self.vector(right)
        if not a or not b:
            return 0.0
        shared = set(a) & set(b)
        if not shared:
            return 0.0
        dot = sum(a[t] * b[t] for t in shared)
        norm_a = math.sqrt(sum(v * v for v in a.values()))
        norm_b = math.sqrt(sum(v * v for v in b.values()))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return dot / (norm_a * norm_b)


# --- Combined score ----------------------------------------------------------

# Provisional, NOT fitted. See the module docstring. Ordered by how much each
# signal is trusted: an agreeing municipality is near-decisive, text similarity
# alone is not.
DEFAULT_WEIGHTS: Mapping[str, float] = {
    'municipality': 0.35,
    'ward': 0.10,
    'casualties': 0.25,
    'trigger': 0.05,
    'place_translit': 0.10,
    'text': 0.15,
}

MERGE_THRESHOLD = 0.55


@dataclass(frozen=True)
class SimilarityBreakdown:
    """Per-signal scores, kept separable so a merge decision is auditable."""

    municipality: float | None
    ward: float | None
    casualties: float | None
    trigger: float | None
    place_translit: float
    text: float
    score: float
    cross_language: bool
    conflict: str | None = None

    @property
    def has_strong_evidence(self) -> bool:
        """At least one agreeing administrative or casualty signal.

        Without this gate, renormalisation lets a *single* weak signal become
        the whole score: a pair with nothing but a fuzzy place-name match scores
        0.92 and merges. Since district and date are already the blocking key,
        "same district, similar-looking place name" is not evidence of anything
        -- two genuinely distinct Dhading landslides a day apart would both
        match. A merge must be supported by an agreeing municipality, ward, or
        casualty count.
        """

        return any(
            value is not None and value > 0.0
            for value in (self.municipality, self.ward, self.casualties)
        )

    @property
    def should_merge(self) -> bool:
        return (
            self.conflict is None
            and self.has_strong_evidence
            and self.score >= MERGE_THRESHOLD
        )

    def explain(self) -> str:
        parts = [f'{k}={v:.2f}' for k, v in (
            ('muni', self.municipality), ('ward', self.ward),
            ('cas', self.casualties), ('trig', self.trigger),
            ('translit', self.place_translit), ('text', self.text),
        ) if v is not None]
        suffix = f' CONFLICT:{self.conflict}' if self.conflict else ''
        return f'score={self.score:.3f} [{" ".join(parts)}]{suffix}'


def _exact_agreement(left: str | None, right: str | None) -> float | None:
    """1.0 / 0.0 when both sides have a value, None when either is missing.

    None means "no evidence", which the score renormalises around. The previous
    implementation defaulted a missing municipality to *agreement*, which made
    the guard vacuous for the 60% of events with no municipality.
    """

    if not left or not right:
        return None
    return 1.0 if str(left).strip().casefold() == str(right).strip().casefold() else 0.0


def structured_similarity(
    *,
    left_municipality: str | None,
    right_municipality: str | None,
    left_ward: str | None,
    right_ward: str | None,
    left_casualties: CasualtyVector,
    right_casualties: CasualtyVector,
    left_trigger: str | None,
    right_trigger: str | None,
    left_place: str | None,
    right_place: str | None,
    left_text: str | None,
    right_text: str | None,
    left_lang: str | None,
    right_lang: str | None,
    tfidf: TfidfIndex | None = None,
    weights: Mapping[str, float] = DEFAULT_WEIGHTS,
    casualty_tolerance: int = 1,
) -> SimilarityBreakdown:
    """Score a candidate pair from language-neutral evidence.

    Signals that are unavailable contribute nothing and their weight is
    redistributed, so a pair is never penalised for missing data -- only for
    contradicting data.
    """

    cross_language = bool(left_lang and right_lang and left_lang != right_lang)

    municipality = _exact_agreement(left_municipality, right_municipality)
    ward = _exact_agreement(left_ward, right_ward)
    # Tolerance, not exact match. Death tolls are revised between editions and
    # between outlets -- the Baglung 2024-08-06 landslide was reported as 6 by
    # myRepublica and 7 by setopati on the same day, same municipality. Treating
    # that as a conflict vetoed an obviously-correct merge. Mirrors
    # dedup.guard_deaths_delta in config.yaml.
    casualties = casualty_agreement(left_casualties, right_casualties, casualty_tolerance)
    trigger = _exact_agreement(left_trigger, right_trigger)

    # Hard vetoes. Contradicting administrative units or casualty counts mean
    # these are different events no matter how similar the prose is.
    conflict: str | None = None
    if municipality == 0.0:
        conflict = 'municipality'
    elif casualties == 0.0:
        conflict = 'casualties'

    # Transliterated place-name similarity, for names outside the gazetteer.
    left_translit = transliterate_devanagari(left_place) if left_place else ''
    right_translit = transliterate_devanagari(right_place) if right_place else ''
    if left_place and right_place:
        # A Latin-script name passes through transliteration unchanged, so this
        # works for en-en, np-np and en-np alike.
        lhs = left_translit or normalize_for_matching(left_place)
        rhs = right_translit or normalize_for_matching(right_place)
        place_translit = fuzz.token_sort_ratio(lhs, rhs) / 100.0
    else:
        place_translit = 0.0

    # Text similarity is only meaningful within a language. Across scripts it is
    # structurally zero, so including it would drag every cross-language pair
    # below threshold -- which is precisely the bug being fixed.
    if cross_language:
        text = 0.0
        text_weight = 0.0
    else:
        text = tfidf.cosine(left_text, right_text) if tfidf else 0.0
        text_weight = weights['text']

    contributions: list[tuple[float, float]] = []
    for key, value in (
        ('municipality', municipality), ('ward', ward),
        ('casualties', casualties), ('trigger', trigger),
    ):
        if value is not None:
            contributions.append((weights[key], value))
    if left_place and right_place:
        contributions.append((weights['place_translit'], place_translit))
    if text_weight:
        contributions.append((text_weight, text))

    total_weight = sum(w for w, _ in contributions)
    score = (sum(w * v for w, v in contributions) / total_weight) if total_weight else 0.0

    return SimilarityBreakdown(
        municipality=municipality, ward=ward, casualties=casualties, trigger=trigger,
        place_translit=place_translit, text=text, score=round(score, 4),
        cross_language=cross_language, conflict=conflict,
    )


def merge_rate_by_language_pair(pairs: Sequence[tuple[str, str, bool]]) -> dict[str, dict[str, int]]:
    """Merge counts by language pair. This is the acceptance test for section 8.2.

    Review: "If en-np merges stay near zero after the fix, the fix did not
    work." Reported by the dedup stage so that check is automatic rather than
    something someone remembers to run.
    """

    stats: dict[str, dict[str, int]] = {}
    for left_lang, right_lang, merged in pairs:
        key = '-'.join(sorted((left_lang or '?', right_lang or '?')))
        bucket = stats.setdefault(key, {'candidates': 0, 'merged': 0})
        bucket['candidates'] += 1
        bucket['merged'] += int(merged)
    return dict(sorted(stats.items()))
