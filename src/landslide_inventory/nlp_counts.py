"""Nepali number words, and the phrases that assert nobody was harmed.

Two small vocabularies that both extractors need, kept here so English and
Nepali cannot drift apart.

Why number words matter
-----------------------
The Nepali casualty patterns matched ``\\d+`` only. Nepali disaster reporting
writes small tolls as words far more often than as digits:

    तीन जनाको मृत्यु भएको छ            three people died
    एक बालकको मृत्यु भएको छ            a boy died
    पाँच जनाको शव भेटिएको छ            five bodies were found

An audit of the corpus found 933 class-1 articles carrying death vocabulary but
no extracted count, 703 of them Nepali. Word-form numerals are the single
largest cause.

Why zero is a separate, guarded concept
---------------------------------------
The project rule is that an unknown casualty value is never replaced by zero. A
zero may therefore be written **only** when the article says in so many words
that nobody was harmed -- "पहिरोबाट मानवीय क्षति भएको छैन", "No human casualty
has been reported". That is a real observation and is worth recording, because
"a landslide happened and hurt nobody" is different information from "we do not
know".

The danger is scope. In a roundup, the same phrase is routinely attached to one
district while others are counting the dead:

    गण्डकीमा मानवीय क्षति भएको छैन।  (…in an article reporting 48 deaths)

so the phrase alone is never sufficient. ``explicit_zero_is_safe`` carries the
guards that make it sufficient.
"""

from __future__ import annotations

import re
import unicodedata

# Cardinals up to twenty, with the spelling variants that appear in the corpus.
# Deliberately stops at twenty: beyond that Nepali reporting uses digits, and a
# longer table would add ambiguity without adding recall.
NEPALI_NUMBER_WORDS: dict[str, int] = {
    'एक': 1, 'एउटा': 1, 'एकै': 1,
    'दुई': 2, 'दुइ': 2, 'दुवै': 2,
    'तीन': 3, 'तिन': 3,
    'चार': 4,
    'पाँच': 5, 'पांच': 5, 'पाच': 5, 'पँाच': 5,
    'छ': 6,
    'सात': 7,
    'आठ': 8,
    'नौ': 9,
    'दश': 10, 'दस': 10,
    'एघार': 11, 'एघाह्र': 11,
    'बाह्र': 12, 'बाहृ': 12,
    'तेह्र': 13,
    'चौध': 14,
    'पन्ध्र': 15, 'पन्धृ': 15,
    'सोह्र': 16,
    'सत्र': 17,
    'अठार': 18,
    'उन्नाइस': 19, 'उन्नाईस': 19,
    'बीस': 20, 'बिस': 20,
}

# Longest first so that "एघार" is not matched as "एक" would be by a shorter
# alternative appearing earlier in the alternation.
NEPALI_NUMBER_ALTERNATION = '|'.join(
    re.escape(word) for word in sorted(NEPALI_NUMBER_WORDS, key=len, reverse=True)
)

# `छ` is the ordinary Nepali verb "is" as well as the numeral six, so it is by
# far the most dangerous entry in the table. It is admitted only where a
# counting classifier follows it, which the calling patterns enforce by
# requiring जना / जनाको or a person noun immediately after the numeral.
AMBIGUOUS_NUMBER_WORDS = frozenset({'छ'})

# Person classifiers and nouns that a count attaches to. A numeral followed by
# one of these is a count of people; a bare numeral is not.
NEPALI_PERSON_NOUNS = (
    'जना', 'जनाको', 'जनाकाे', 'जनाले', 'जनाका', 'जन',
    'व्यक्ति', 'व्यक्तिको', 'महिला', 'महिलाको', 'पुरुष', 'पुरुषको',
    'बालक', 'बालकको', 'बालिका', 'बालिकाको', 'बालबालिका',
    'युवक', 'युवकको', 'युवती', 'युवतीको', 'किशोर', 'किशोरी',
    'वृद्ध', 'वृद्धको', 'वृद्धा', 'वृद्धाको', 'यात्रु', 'यात्रुको',
    'सदस्य', 'सदस्यको', 'नागरिक', 'श्रमिक', 'मजदुर', 'चालक', 'विद्यार्थी',
)
NEPALI_PERSON_NOUN_ALTERNATION = '|'.join(
    re.escape(noun) for noun in sorted(NEPALI_PERSON_NOUNS, key=len, reverse=True)
)

# "शव फेला परेको" -- a body was found -- is the standard Nepali way of
# confirming a death, and none of its words is a death term, so a toll written
# this way was invisible to the casualty patterns.
NEPALI_BODY_RECOVERY_VERBS = ('फेला', 'भेटिए', 'भेटियो', 'भेटिएको', 'निकालि', 'निकाले', 'उद्धार')

EXPLICIT_NO_CASUALTY = {
    'np': re.compile(
        r'(?:(?:मानवीय|मानविय)\s*क्षति\s*(?:भने\s*)?(?:भएको\s*छैन|गरेको\s*छैन|नभएको|छैन|भएन)'
        r'|कुनै\s*(?:प्रकारको\s*)?(?:(?:मानवीय|मानविय)\s*)?क्षति\s*(?:भने\s*)?(?:भएको\s*छैन|गरेको\s*छैन|नभएको|छैन|भएन)'
        r'|हताहत\s*(?:भएको\s*छैन|नभएको|छैन)'
        r'|कोही\s*(?:पनि\s*)?(?:हताहत|घाइते)\s*(?:भएको\s*छैन|छैन)'
        r'|कसैको\s*ज्यान\s*(?:गएको\s*छैन|गएन)'
        r'|ज्यानको\s*क्षति\s*(?:भएको\s*छैन|छैन)'
        r'|(?:कारका\s*)?(?:चालक|यात्रु|कामदार|श्रमिक|स्थानीय)(?:हरू)?'
        r'(?:\s*र\s*(?:चालक|यात्रु|कामदार|श्रमिक|स्थानीय)(?:हरू)?)?'
        r'\s*(?:भने\s*)?(?:सबै\s*)?सकुशल\s*(?:छन्|रहेका\s*छन्)?)'
    ),
    'en': re.compile(
        r'(?:no\s+(?:human\s+)?(?:casualt\w*|loss\s+of\s+life|deaths?|fatalit\w*)'
        r'|no\s+one\s+(?:was|were|has\s+been)\s+(?:hurt|injured|killed)'
        r'|nobody\s+was\s+(?:hurt|injured|killed)'
        r'|there\s+(?:was|were)\s+no\s+(?:human\s+)?(?:loss\w*|casualt\w*)'
        r'|caused\s+no\s+human\s+casualt\w*'
        r'|escaped\s+unhurt'
        r'|rescued\s+alive)',
        re.IGNORECASE,
    ),
}

# A preliminary "no loss" report is not an observed zero when the same article
# explicitly says that casualty status is still unknown or cannot be verified.
UNCERTAIN_CASUALTY_STATUS = {
    'np': re.compile(
        r'(?:मानवीय|मानविय)\s*क्षति[^।\n]{0,80}'
        r'(?:भए\s*नभएको|भएको\s*नभएको|भन्न\s*नसकिने|यकिन\s*गर्न\s*नसकिने)'
        r'|क्षतिको\s*विवरण\s*(?:आउन|प्राप्त\s*हुन)\s*बाँकी'
    ),
    'en': re.compile(
        r'(?:casualty|casualties|loss\s+of\s+life)[^.\n]{0,80}'
        r'(?:unknown|unclear|not\s+yet\s+known|could\s+not\s+be\s+confirmed)',
        re.IGNORECASE,
    ),
}

# Vocabulary that shows the article is reporting a death somewhere, whatever the
# no-casualty phrase says. Its presence blocks a zero.
DEATH_EVIDENCE = {
    'np': re.compile(r'(?:मृत्यु|मृतक|निधन|ज्यान\s*गुम|ज्यान\s*गए|शव|मारिए)'),
    'en': re.compile(
        r'\b(?:died|dead|deaths?|killed|deceased|fatalit\w*|bodies|body\s+of)\b', re.IGNORECASE
    ),
}

# Roundup and running-total markers. A no-casualty phrase inside one of these is
# almost always scoped to a single district within a wider tally.
#
# Devanagari has no word boundary that ``\b`` understands, and short markers are
# substrings of ordinary words: `कुल` sits inside `स्कुल` (school), which vetoed
# a legitimate zero in an article about closed schools. Each Devanagari marker
# is therefore fenced by explicit "not a Devanagari letter" look-arounds.
_NP_EDGE = '(?<![ऀ-ॿ])(?:{})(?![ऀ-ॿ])'
_NP_ROUNDUP_WORDS = (
    'देशभर', 'देशैभरि', 'देशभरि', 'अहिलेसम्म', 'हालसम्म', 'कुल', 'जम्मा', 'प्रदेशमा',
)
ROUNDUP_MARKER = re.compile(
    r'nationwide|across the country|country-?wide|so far|death toll|in total|altogether'
    + '|' + _NP_EDGE.format('|'.join(_NP_ROUNDUP_WORDS))
    + r'|मृत्यु\s*हुनेको\s*(?:सङ्ख्या|संख्या)',
    re.IGNORECASE,
)


# A no-casualty claim that is immediately contradicted is scoped, not global:
#
#     बाढीको कारणले मानवीय क्षति भएको छैन। तर पहिरो गएर इलाममा भने क्षति भएको
#     (no human loss from the flood. But there WAS loss from the landslide in Ilam)
#
# `क्षति` means loss or damage generally and is not death vocabulary, so this
# article passed every other guard and produced a zero for an event that caused
# losses. English needs no equivalent: `DEATH_EVIDENCE` already catches "but two
# died", because English states deaths with words that are death words.
NP_CONTRASTED_LOSS = re.compile(r'(?:तर|यद्यपि)[^।]{0,150}क्षति\s*भएको(?!\s*छैन)')


# Legacy Nepali fonts and some CMS exports write a single vowel sign as two
# marks: "नभएकाे" is आ-sign + े-sign where "नभएको" is the single ो-sign. The two
# render identically and a reader cannot tell them apart, but they are different
# byte sequences and Unicode does NOT canonically compose them -- NFC leaves
# both unchanged -- so a pattern written the ordinary way silently fails on the
# decomposed form. One such article was recorded as unknown when it plainly
# stated that nobody was hurt.
_DEVANAGARI_VOWEL_FOLD = {
    '\u093e\u0947': '\u094b',   # ा + े  -> ो
    '\u093e\u0948': '\u094c',   # ा + ै  -> ौ
    '\u093e\u0945': '\u0949',   # ा + ॅ  -> ॉ
    '\u093e\u0946': '\u094a',   # ा + ॆ  -> ॊ
}


def fold_devanagari_vowel_signs(text: str) -> str:
    """Rewrite two-mark vowel spellings to their single-sign equivalents."""

    folded = unicodedata.normalize('NFC', text)
    for source, target in _DEVANAGARI_VOWEL_FOLD.items():
        if source in folded:
            folded = folded.replace(source, target)
    return folded


def parse_nepali_number(token: str) -> int | None:
    """Return the integer a Nepali numeral word denotes, or ``None``."""

    return NEPALI_NUMBER_WORDS.get(token.strip())


def explicit_zero_is_safe(
    text: str,
    language: str,
    *,
    extracted_any_count: bool,
) -> bool:
    """Whether this article may record an explicit zero human toll.

    Three conditions must all hold. Each corresponds to a labelled failure in
    ``data/outputs/casualty_development_casualty_v1.csv``:

    1. **A no-casualty phrase is present.** Necessary, never sufficient.
    2. **No casualty count was extracted anywhere in the article.** Blocks the
       roundup in which one district reports no losses while the article's own
       headline toll is 48, and the story where a second landslide hurt nobody
       but the first killed two.
    3. **No death vocabulary appears anywhere in the article.** Blocks the piece
       whose no-loss sentence covers one settlement while a body is recovered in
       the next paragraph.

    Livestock deaths are intentionally *not* death vocabulary: "पहिरोमा कुनै
    मानवीय क्षति नभएको तर ... तीन भैँसी ... मरेका" is a genuine human zero.
    """

    key = language if language in EXPLICIT_NO_CASUALTY else 'en'
    text = fold_devanagari_vowel_signs(text)
    if not EXPLICIT_NO_CASUALTY[key].search(text):
        return False
    if UNCERTAIN_CASUALTY_STATUS[key].search(text):
        return False
    if extracted_any_count:
        return False
    if DEATH_EVIDENCE[key].search(text):
        return False
    if ROUNDUP_MARKER.search(text):
        return False
    if key == 'np' and NP_CONTRASTED_LOSS.search(text):
        return False
    return True
