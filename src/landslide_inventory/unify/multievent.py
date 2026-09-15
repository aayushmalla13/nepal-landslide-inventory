"""Emit additional district-day records from articles reporting several failures.

Why this module exists
----------------------
The pipeline emits one record per article. 29.3% of the articles it keeps as
class-1 events report more than one landslide failure, so those articles are
under-counted. See ``docs/MULTIEVENT_EXTRACTION.md`` for the full design and the
measurement that gated it.

The single most important fact shaping this code: a full read of all 47
human-labelled ``multi`` articles found that resolving every district the
existing place extractor already surfaces would emit 42 additional
district-days, of which **at most 15 are defensible**. Most district names in
these articles are not failure locations -- they are datelines, the home
districts of the dead, the far end of a blocked road, where stranded vehicles
were headed, or the publisher's own footer address.

So this module is deliberately asymmetric. A missed recovery costs one
district-day out of a projected two hundred. A false recovery puts a fabricated
landslide into the canonical inventory, spatially correlated with rainfall,
where nothing downstream can distinguish it from a real one. **Every ambiguous
case is dropped.**

The rule
--------
A district earns an additional record only when one sentence jointly carries a
failure term, a location resolving to that district, and an occurrence
predicate -- and no trap pattern matches. The date comes only from an anchor in
that same sentence; if there is none, no record is emitted. The article's
primary date is never reused for a secondary record, because the district-rich
articles are status bulletins that mix today's failures with last week's.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import re
import unicodedata

from ..gazetteer import all_districts, normalize_district
from ..gazetteer_municipality import (
    _normalize_key,
    is_ambiguous_municipality,
    load_municipality_gazetteers,
    municipality_to_district,
)
from ..preprocess.dates import BS_MONTH_MAP, bs_to_ad

# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------

NP_FAILURE_TERMS = ('पहिरो', 'पहिरा', 'पहिराले', 'भूस्खलन', 'लेदो')
EN_FAILURE_TERMS = ('landslide', 'landslip', 'mudslide', 'debris flow', 'rockfall', 'rock fall')

NP_OCCURRENCE_TERMS = (
    'खस', 'गएको', 'गयो', 'जाँदा', 'गएका', 'पुरि', 'पुरे', 'पुर्‍यो', 'बगा', 'बगे',
    'भत्कि', 'अवरुद्ध', 'मृत्यु', 'ज्यान', 'घाइते', 'क्षति', 'विस्थापित',
)
EN_OCCURRENCE_TERMS = (
    'occurred', 'buried', 'swept', 'hit', 'struck', 'blocked', 'obstructed',
    'killed', 'died', 'damaged', 'destroyed', 'displaced', 'injured', 'affected',
    'took place', 'caved', 'claimed',
)

# Predicates that describe a hazard *not happening* -- a warning, a prevention
# works story, or a road being put back into service. A sentence carrying only
# these is not evidence of an occurrence, and the audit found these are exactly
# what the retrospective police bulletins are full of.
NP_NEGATIVE_PREDICATES = (
    'जोखिम', 'सुचारु', 'सुचारू', 'खुल्यो', 'खुलेको', 'खुल्या', 'पन्छा', 'हटाउ', 'हटाइ',
    'रोकथाम', 'सतर्क', 'सावधान', 'निर्माण', 'मर्मत', 'अनुमान', 'उच्च जोखिम', 'सम्भावना',
    'सञ्चालन', 'एकतर्फी', 'वैकल्पिक',
)
EN_NEGATIVE_PREDICATES = (
    'at risk', 'risk of', 'at high risk', 'under threat', 'prevention', 'prevent',
    'reopened', 're-opened', 'resumed', 'restored', 'cleared', 'clearing',
    'warning', 'warned', 'likely', 'could', 'may ', 'anchoring', 'repair',
)

# ---------------------------------------------------------------------------
# Trap patterns -- each one observed in the 47-article audit
# ---------------------------------------------------------------------------

# A person identified by where they were from, not where they died.
EN_VICTIM_CUES = (
    'identified as', 'deceased', 'the dead', 'resident of', 'residents of',
    'of the same', 'aged', 'years old',
)
# Deliberately specific. An earlier draft used bare case particles such as
# 'की', which appear in almost every Nepali sentence and silently suppressed
# most recoveries.
NP_VICTIM_CUES = (
    'निवासी', 'बस्ने', 'घर भएका', 'स्थायी ठेगाना', 'मृतकको नाम', 'पहिचान भएको',
    'शव', 'मृतकहरू',
)

# "around 85 kilometres northeast of Kathmandu" locates the event by reference
# to somewhere it did not happen.
EN_DISTANCE_PATTERN = re.compile(
    r'\b\d+\s*(?:km|kilometres?|kilometers?|miles?)\b[^.]{0,40}?\bof\s+(?P<district>[A-Z][\w.\'-]+)'
)
NP_DISTANCE_PATTERN = re.compile(
    r'(?P<district>[ऀ-ॿ]+)\s*(?:देखि|बाट)\s*[^।]{0,20}?'
    r'(?:किलोमिटर|कोस)'
)

EN_VICTIM_HOME_PATTERN = re.compile(
    r'\bof\s+[A-Z][\w.\'-]*(?:[\s-]+[\w.\'-]+){0,4}\s*,?\s*(?:in\s+)?'
    r'(?P<district>[A-Z][\w.\'-]+)\s+district\b'
)
NP_VICTIM_HOME_PATTERN = re.compile(
    r'(?P<district>[ऀ-ॿ]+)\s*(?:जिल्ला)?\s*(?:को|का|की)\s*[^।]{0,40}?'
    r'(?:निवासी|बस्ने|घर भएका)'
)

# The far end of a corridor: "road connecting Mustang", "X जाने सडक".
EN_ROUTE_PATTERN = re.compile(
    r'\b(?:road|highway|route|stretch|section)\b[^.]{0,60}?\b(?:connect(?:s|ing)?|links?|linking|to|towards?)\s+'
    r'(?P<district>[A-Z][\w.\'-]+)'
)
NP_ROUTE_PATTERN = re.compile(
    r'(?P<district>[ऀ-ॿ]+)\s*(?:जिल्ला)?\s*(?:जाने|जोड्ने|तर्फ|सम्म)\s*[^।]{0,20}?'
    r'(?:सडक|राजमार्ग|मार्ग|बाटो)'
)

# Where stranded vehicles or people were headed.
EN_STRANDED_PATTERN = re.compile(
    r'\b(?:headed|bound|en route|heading|travelling|traveling|going)\s+(?:to|for|towards?)\s+'
    r'(?P<tail>[^.]{0,120})'
)
NP_STRANDED_PATTERN = re.compile(r'(?P<tail>[^।]{0,120}?)\s*(?:जाने|आउने)\s*सवारी')

# A district named as where traffic was coming from or going to. This was the
# largest residual error on a corpus run: Kathmandu was the most-recovered
# district in the country, entirely through sentences like "vehicles coming from
# Kathmandu were halted" and "the road connecting Dolakha with Kathmandu".
# Distinct from `road_destination`, which is about the name of a corridor, and
# from `stranded_destination`, which needs an explicit "headed to".
EN_MOVEMENT_WORDS = (
    'road', 'highway', 'route', 'traffic', 'transport', 'vehicle', 'bus', 'truck',
    'jeep', 'passenger', 'travel', 'section', 'stretch', 'connect', 'link',
)
EN_TRAVEL_PREPOSITIONS = ('to ', 'from ', 'with ', 'towards ', 'toward ', 'for ')
NP_DIRECTIONAL_SUFFIXES = ('बाट', 'तर्फ', 'सम्म', 'देखि', 'तिर')
NP_MOVEMENT_WORDS = (
    'आउने', 'जाने', 'आउँदा', 'जाँदा', 'आउँदै', 'जाँदै', 'जोड्ने', 'हुँदै', 'गाडी',
    'सवारी', 'बस', 'यात्रु', 'ओहोरदोहोर', 'आवतजावत', 'पुग्ने', 'छुट्ने', 'रोकिएका',
    'अलपत्र',
)
# Widened from 30 after a corpus read: "काठमाडौँ चितवनलगायतका सहरमा छुट्ने
# सवारी साधन" puts the movement word 32 characters past the district.
NP_MOVEMENT_WINDOW = 45

# A district name used as part of a corridor's label rather than as a place
# where something fell: "the Jumla road section", "the Hetauda-Kathmandu
# highway", "the Kanti Highway connecting Kathmandu to Hetauda". On a corpus
# run this made Jumla the sixth most-recovered district, on sentences whose
# failures were all in Kalikot and Dailekh.
EN_ROAD_WORDS = ('road', 'highway', 'route', 'section', 'stretch', 'corridor')
NP_ROAD_WORDS = ('सडक', 'राजमार्ग', 'मार्ग', 'लोकमार्ग', 'सडकखण्ड', 'राजपथ', 'खण्ड')

# A single article almost never reports failures more than a year apart, and a
# BS date carries no year of its own -- it is inferred from the publication
# date. A 2026 feature recalling a 2021 displacement therefore produced a
# recovered record five years adrift, same month and day. This bounds that.
MAX_DAYS_FROM_PRIMARY = 400

# A district alias can also be a smaller named feature elsewhere. "Kavre Bhir"
# is a cliff on the Myagdi-Mustang road, not Kavrepalanchok district.
NP_LOCAL_FEATURE_SUFFIXES = ('भिर', 'भीर')

# A sentence naming this many districts is enumerating them -- a national toll,
# a list of affected hill districts -- not reporting a located failure.
MAX_DISTRICTS_PER_SENTENCE = 2

EN_HOSPITAL_CUES = ('hospital', 'referred', 'taken to', 'health post', 'treatment')
NP_HOSPITAL_CUES = ('अस्पताल', 'उपचार', 'स्वास्थ्य', 'रिफर', 'पठाइ')

EN_ADJACENCY_CUES = ('border with', 'close to the border', 'bordering', 'near the border')
NP_ADJACENCY_CUES = ('सिमाना', 'सिमानास्थित', 'सीमा')

# "a team went to Taplejung, Panchthar and Sankhuwasabha to assess the damage":
# the districts are the team's itinerary. The sentence carries a failure term
# and a damage word, so it passes the occurrence test on its own terms, and the
# districts it lists are real -- but the event it reports is a visit.
EN_ASSESSMENT_CUES = (
    'assessment team', 'assess the damage', 'to assess', 'team visited', 'delegation',
    'monitoring team', 'inspection team', 'field visit', 'survey team',
)
NP_ASSESSMENT_CUES = (
    'मूल्याङ्कन', 'मुल्याङ्कन', 'मूल्यांकन', 'मुल्यांकन', 'अनुगमन', 'निरीक्षण',
    'टोली', 'प्रतिवेदन', 'अध्ययन',
)

# "landslides fell at various places in districts including Palpa, Syangja and
# Gulmi": an aggregate over an unstated set of failures, which is what the
# granularity rubric calls a roundup. It locates nothing.
NP_AGGREGATE_CUES = ('लगायतका जिल्ला', 'लगायत जिल्ला', 'जिल्लाभित्र', 'सबैभन्दा बढी', 'विभिन्न जिल्ला')
EN_AGGREGATE_CUES = ('districts including', 'various districts', 'several districts', 'across the country')

NP_FLOOD_TERMS = ('बाढी', 'डुबान')
EN_FLOOD_TERMS = ('flood', 'inundat')

# Publisher footers and page chrome, after which nothing is article content.
FOOTER_MARKERS = (
    'प्रकाशित:', 'नेपाल रिपब्लिक मिडिया', 'Copyright', 'सम्पादक:', 'दर्ता नम्बर',
    'Subscribe to Onlinekhabar', 'The English Edition of', 'विज्ञापनका लागि',
    'Email:', 'इमेल:', 'FDI commitment', 'Nepal records highest LPG',
)

# Datelines come in three shapes across these outlets, and all three must be
# removed before anything else reads the text -- not only because the filing
# city is not the event location, but because the dateline carries its own date
# ("Surkhet, April 7") which would otherwise count as a second date anchor and
# make a single-occasion article look like a multi-day bulletin.
_MONTH_ABBR = r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?'
EN_DATELINE_PATTERN = re.compile(
    r'^\s*'
    r'(?:Resize Text Size Small Medium Large Listen\s+)?'
    r'(?:By\s+[A-Z][A-Za-z .\'’-]{1,60}?\s+)?(?:'
    rf'(?P<place>[A-Z][A-Za-z .\'()-]{{1,40}}?)\s*,\s*{_MONTH_ABBR}\s+\d{{1,2}}\s*:?'
    r'|(?P<upper>[A-Z][A-Z\s()]{2,40})\s*:'
    r')'
)
NP_DATELINE_PATTERN = re.compile(r'^\s*(?P<place>[ऀ-ॿ\s]{2,30}?)\s*[।\-–:]')

# ---------------------------------------------------------------------------
# Date anchors
# ---------------------------------------------------------------------------

EN_WEEKDAYS = {
    'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
    'friday': 4, 'saturday': 5, 'sunday': 6,
}
NP_WEEKDAYS = {
    'सोमबार': 0, 'मंगलबार': 1, 'मङ्गलबार': 1, 'बुधबार': 2, 'बिहीबार': 3,
    'बिहिबार': 3, 'शुक्रबार': 4, 'शनिबार': 5, 'आइतबार': 6,
}
NP_TODAY_CUES = ('आज', 'आजै')
NP_LAST_NIGHT_CUES = ('गएराति', 'गए राति', 'हिजो', 'गतराति', 'गत राति', 'रातिदेखि')
EN_TODAY_CUES = ('today', 'this morning', 'this afternoon', 'this evening')
EN_LAST_NIGHT_CUES = ('last night', 'yesterday', 'overnight', 'wee hours')

NP_BS_DAY_MONTH = re.compile(
    r'(?<![\d०-९])([\d०-९]{1,2})\s*'
    r'(बैशाख|वैशाख|जेठ|असार|साउन|भदौ|असोज|कात्तिक|कार्तिक|मंसिर|पुष|पुस|माघ|फागुन|चैत)'
)
# "९ असार २०७४" -- day, month, explicit BS year.
NP_BS_FULL_DATE = re.compile(
    r'(?<!\d)(\d{1,2})\s*(बैशाख|वैशाख|जेठ|असार|साउन|भदौ|असोज|कात्तिक|कार्तिक|मंसिर|पुष|पुस|माघ|फागुन|चैत)\s*(20[5-9]\d)'
)
NP_MONTH_BS_DAY = re.compile(
    r'(बैशाख|वैशाख|जेठ|असार|साउन|भदौ|असोज|कात्तिक|कार्तिक|मंसिर|पुष|पुस|माघ|फागुन|चैत)\s*'
    r'([\d०-९]{1,2})\s*गते'
)
DEVANAGARI_DIGITS = str.maketrans('०१२३४५६७८९', '0123456789')


@dataclass(frozen=True)
class SecondaryFailure:
    """One additional district-day recovered from an article.

    ``sentence`` and ``date_basis`` are carried so every recovered record stays
    auditable and any later analysis can exclude them wholesale.
    """

    district: str
    event_date_ad: str
    sentence: str
    date_basis: str
    confidence: float

    def to_record(self) -> dict[str, object]:
        """Return the fields a recovered district-day may carry.

        Every impact field is explicitly ``None``, and that is the point rather
        than an omission. An article about a fatal landslide in Dailekh that
        also mentions a blockage in Kalikot reports one death toll, one
        municipality, one trigger -- all belonging to Dailekh. Letting the
        recovered Kalikot record inherit them would invent nine deaths in a
        district that reported none, and would do it in the direction that
        makes the inventory look more complete, which is the direction least
        likely to be questioned.

        The recovered record asserts exactly one thing: a landslide occurred in
        this district on this day. Anything more has to come from an article
        that is actually about it.
        """

        return {
            'district': self.district,
            'event_date_ad': self.event_date_ad,
            'extraction_basis': 'secondary_failure',
            'evidence_sentence': self.sentence[:400],
            'date_basis': self.date_basis,
            'conf_date': self.confidence,
            'deaths': None,
            'missing': None,
            'injured': None,
            'municipality': None,
            'ward': None,
            'trigger': None,
        }


# Only a calendar date written in the same evidence sentence is admissible.
# The spent precision census showed that weekday and relative cues frequently
# belonged to rain, funerals, reopening, or the article's primary event.
FIRM_DATE_BASES = ('explicit_bs_date', 'explicit_ad_date')


def extract_secondary_failures(
    title: str | None,
    text: str,
    *,
    lang: str,
    published_date_ad: str | date | None,
    primary_district: str | None,
    primary_date: str | None,
    primary_municipality: str | None = None,
    municipality_to_district_map: dict[str, str] | None = None,
) -> list[SecondaryFailure]:
    """Return additional ``(district, date)`` records supported by the article.

    Never returns the primary record, never returns a record whose date was not
    anchored, and never returns a district that appears only in the dateline.

    ``primary_municipality`` gates same-district recoveries. Without it, a
    corpus run produced 134 same-district records sitting exactly one day from
    their article's primary date -- the signature of one landslide being
    redescribed by weekday rather than of a second occasion.
    """

    published = _coerce_date(published_date_ad)
    body = _strip_footer(_prepare(title, text))
    dateline_districts = _dateline_districts(body, lang)
    # Datelines are stripped before anything else reads the sentences. A
    # dateline carries its own date ("Surkhet, April 7"), which would otherwise
    # count as a second anchor and make every single-occasion article look like
    # a bulletin.
    sentences = [
        _drop_dateline(sentence, lang) if _looks_like_dateline(sentence, lang) else sentence
        for sentence in _split_sentences(body, lang)
    ]

    published_iso = published.isoformat() if published else None
    found: dict[tuple[str, str], SecondaryFailure] = {}
    for sentence in sentences:
        if not _reports_an_occurrence(sentence, lang):
            continue

        anchors = [
            anchor for anchor in _sentence_date_anchors(sentence, lang, published)
            if anchor[1] in FIRM_DATE_BASES
        ]
        distinct = {anchor[0] for anchor in anchors}
        if len(distinct) > 1:
            # Several dates in one sentence: a police status bulletin listing
            # blockages from different days. Nothing here can be attributed.
            continue
        if not anchors:
            continue
        anchor = anchors[0]
        event_date, basis, confidence = anchor
        # A BS date carries no year; the year is inferred from the publication
        # date. A 2026 feature recalling a 2021 displacement therefore produced
        # a record five years adrift on the same month and day. A single
        # article does not report failures a year apart.
        if primary_date and abs(_days_between(event_date, primary_date)) > MAX_DAYS_FROM_PRIMARY:
            continue

        named_here = _districts_in(sentence, lang, municipality_to_district_map)
        if len(named_here) > MAX_DISTRICTS_PER_SENTENCE:
            # A sentence naming three or more districts is enumerating them --
            # a national toll, a list of affected hill districts, a run of
            # stranded-traffic origins. None of those locate a failure, and on
            # a corpus run they were the second-largest source of bad records.
            continue
        districts = [
            district
            for district in named_here
            if not _is_trapped(sentence, district, lang)
            and district not in dateline_districts
        ]
        # A sentence that names a firm date and an occurrence but no district at
        # all still describes a distinct occasion. Attribute it to the article's
        # own district, but only when the article names no other district -- so
        # a corridor story spanning two districts never guesses which one.
        if not districts and basis in FIRM_DATE_BASES and primary_district:
            named = _districts_in(body, lang, municipality_to_district_map)
            if set(named) - dateline_districts <= {primary_district}:
                districts = [primary_district]

        for district in districts:
            if district == primary_district:
                # A same-district record is a claim that the article reports a
                # second occasion. Only a firm anchor can support that; a
                # relative cue is just how the main event was described.
                if basis not in FIRM_DATE_BASES or event_date == primary_date:
                    continue
                # An article published on day D, describing a failure on day D
                # in the district it is already about, is describing its own
                # subject -- typically an ongoing blockage that keeps recurring.
                if event_date == published_iso:
                    continue
                # And it must point somewhere else within the district. A
                # sentence that re-dates the article's own event by naming its
                # weekday is not a second landslide, and on a corpus run that
                # was the single largest source of spurious records. Requiring
                # a different named municipality is the same standard dedup
                # already applies when deciding whether two reports are one
                # event.
                if not _names_a_different_municipality(
                    sentence, lang, primary_municipality, municipality_to_district_map
                ):
                    continue
            key = (district, event_date)
            if key in found:
                continue
            found[key] = SecondaryFailure(
                district=district,
                event_date_ad=event_date,
                sentence=sentence.strip(),
                date_basis=basis,
                confidence=confidence,
            )
    return [found[key] for key in sorted(found)]


def _names_a_different_municipality(
    sentence: str,
    lang: str,
    primary_municipality: str | None,
    municipality_to_district_map: dict[str, str] | None,
) -> bool:
    """Whether this sentence points at a local unit other than the primary one.

    Deliberately strict in two directions. A sentence naming no municipality
    fails, because the article's own event is the default reading of an
    unlocated failure. A sentence naming only the primary municipality fails,
    because a follow-up reporting the same slope on a corrected date is the
    commonest shape in the corpus -- and, when the primary date is the one in
    error, emitting the corrected date creates a duplicate district-day rather
    than a new event.
    """

    for spans in _municipality_phrases(sentence, lang):
        for phrase in spans:
            canonical = _exact_municipality(phrase, lang)
            if canonical is None and lang == 'np':
                canonical = _exact_municipality(phrase, 'en')
            if canonical is None:
                continue
            if primary_municipality is None or canonical != primary_municipality:
                return True
            break
    _ = municipality_to_district_map
    return False


def _dateline_districts(body: str, lang: str) -> frozenset[str]:
    """Return districts that appear as a filing location anywhere in the lead.

    Datelines do not reliably sit in the first sentence: syndicated pages carry
    navigation chrome ahead of them. A district named only as a dateline is
    excluded from secondary emission entirely -- if it genuinely had a failure
    it will normally be the article's primary district already.
    """

    found: set[str] = set()
    head = body[:1500]
    patterns = (
        re.compile(rf'(?:^|\n|\s)([A-Z][A-Za-z .\'()-]{{1,40}}?)\s*,\s*{_MONTH_ABBR}\s+\d{{1,2}}\b'),
        # Wire copy filed jointly carries both bureaux: "CHITWAN/KATHMANDU:".
        # Not anchored to a line start, because syndicated pages run navigation
        # chrome straight into the dateline on one line. Over-detecting here is
        # safe: a dateline district is only ever *excluded* from recovery, and
        # the primary extractor is untouched.
        re.compile(r'(?:^|\n|\s)([A-Z][A-Z\s()/]{2,40}?)\s*:'),
        re.compile(r'(?:^|\n)\s*([ऀ-ॿ\s]{2,30}?)\s*[।\-–]'),
    )
    for pattern in patterns:
        for match in pattern.finditer(head):
            candidate = match.group(1).strip()
            if candidate.startswith('(') and candidate.endswith(')'):
                candidate = candidate[1:-1]
            for piece in re.split(r'[()/]', candidate):
                piece = piece.strip()
                if not piece:
                    continue
                district = normalize_district(piece, lang) or normalize_district(
                    piece, 'en' if lang == 'np' else 'np'
                )
                if district:
                    found.add(district)
    return frozenset(found)


# ---------------------------------------------------------------------------
# Occurrence test
# ---------------------------------------------------------------------------


def _reports_an_occurrence(sentence: str, lang: str) -> bool:
    """A sentence must assert that a landslide happened, not that one might."""

    lowered = sentence.casefold()
    failure_terms = NP_FAILURE_TERMS if lang == 'np' else EN_FAILURE_TERMS
    occurrence_terms = NP_OCCURRENCE_TERMS if lang == 'np' else EN_OCCURRENCE_TERMS
    negatives = NP_NEGATIVE_PREDICATES if lang == 'np' else EN_NEGATIVE_PREDICATES
    flood_terms = NP_FLOOD_TERMS if lang == 'np' else EN_FLOOD_TERMS

    haystack = sentence if lang == 'np' else lowered
    if not any(term in haystack for term in failure_terms):
        return False
    if not any(term in haystack for term in occurrence_terms):
        return False
    # A flood sentence with no landslide verb of its own is a flood.
    if any(term in haystack for term in flood_terms) and not any(
        term in haystack for term in failure_terms
    ):
        return False
    # Reopening and prevention sentences name districts but report no failure.
    negative_hits = sum(1 for term in negatives if term in haystack)
    positive_hits = sum(1 for term in occurrence_terms if term in haystack)
    return positive_hits > negative_hits


# ---------------------------------------------------------------------------
# District resolution
# ---------------------------------------------------------------------------


def _districts_in(
    sentence: str,
    lang: str,
    municipality_to_district_map: dict[str, str] | None,
) -> list[str]:
    """Return districts named or implied by municipalities in this sentence."""

    canonical = set(all_districts())
    found: list[str] = []

    # Explicit district names.
    for token in _candidate_place_tokens(sentence, lang):
        district = normalize_district(token, lang)
        if district is None:
            district = normalize_district(token, 'en' if lang == 'np' else 'np')
        if district and district in canonical and district not in found:
            found.append(district)

    # Municipalities, but only where the text actually says "municipality".
    # Scanning bare tokens instead reads people and highways as places: the
    # given name Ramprasad is a rural municipality in Bhojpur, and the Koshi
    # Highway shares its name with a rural municipality in Sunsari.
    for spans in _municipality_phrases(sentence, lang):
        for phrase in spans:
            district = _district_from_municipality(phrase, lang, municipality_to_district_map)
            if district is None:
                continue
            # Longest span wins and the rest of this mention is abandoned:
            # falling through would also credit the shorter "Tamakoshi Rural
            # Municipality" in Dolakha to a Likhu Tamakoshi event in Ramechhap.
            if district in canonical and district not in found:
                found.append(district)
            break
    return found


# The whole phrase is matched, marker included, and spans are built by dropping
# leading words from it. An earlier version captured only the name before the
# marker, which a greedy quantifier then mis-split: "Gangajamuna Rural
# Municipality" yielded the name "Gangajamuna Rural", and the gazetteer -- quite
# correctly -- had never heard of it.
EN_MUNICIPALITY_PHRASE = re.compile(
    r"(?:[A-Z][A-Za-z'’-]+\s+){1,3}"
    r"(?:Rural\s+|Sub-?[Mm]etropolitan\s+|Metropolitan\s+)?[Mm]unicipality"
)
NP_MUNICIPALITY_PHRASE = re.compile(
    r'(?:[ऀ-ॿ]+\s+){0,2}[ऀ-ॿ]+\s*'
    r'(?:गाउँपालिका|नगरपालिका|महानगरपालिका|उपमहानगरपालिका)'
)


def _municipality_phrases(sentence: str, lang: str) -> list[list[str]]:
    """Return, per municipality mention, its candidate spans longest first.

    Grouped by mention rather than flattened, so a caller can take the longest
    span that resolves and then stop. "Likhu Tamakoshi Rural Municipality" is in
    Ramechhap while "Tamakoshi Rural Municipality" alone is in Dolakha, so a
    flat list would credit one mention to two districts.
    """

    pattern = NP_MUNICIPALITY_PHRASE if lang == 'np' else EN_MUNICIPALITY_PHRASE
    mentions: list[list[str]] = []
    for match in pattern.finditer(sentence):
        words = match.group(0).split()
        if lang == 'en':
            # No span-dropping in English. Every word the pattern matched
            # begins with a capital, so each is part of the proper name, and
            # dropping one *constructs* a different real municipality rather
            # than recovering the intended one: "Shubh Kalika Rural
            # Municipality" (Kalikot) becomes "Kalika Rural Municipality"
            # (Rasuwa), which then matches exactly and defeats the guard
            # against fuzzy matching.
            spans = [' '.join(words)]
        else:
            # Devanagari carries no capitalisation, so the pattern picks up
            # whatever adverbs precede the name ("सोमबार मात्रै गजुरी
            # गाउँपालिका"). Dropping leading words is the only way to reach the
            # name, and the exact-match requirement is what keeps it honest.
            spans = [' '.join(words[start:]) for start in range(len(words))]
        spans = [span for span in spans if span]
        if spans:
            mentions.append(spans)
    return mentions


def _district_from_municipality(
    token: str,
    lang: str,
    municipality_to_district_map: dict[str, str] | None,
) -> str | None:
    """Resolve a municipality name to its district, refusing fuzzy matches.

    The shared gazetteer falls back to fuzzy matching, which is right for the
    primary extractor -- a slightly wrong municipality still usually implies the
    right district -- and wrong here. "Shubh Kalika Rural Municipality" of
    Kalikot fuzzy-matches "Kalika Rural Municipality" of **Rasuwa**, which would
    fabricate a landslide four hundred kilometres away. So a match is accepted
    only when every significant token of the input survives into the canonical
    name.
    """

    canonical_name = _exact_municipality(token, lang)
    if canonical_name is None and lang == 'np':
        canonical_name = _exact_municipality(token, 'en')
    if canonical_name is None:
        return None
    if is_ambiguous_municipality(canonical_name):
        return None

    if municipality_to_district_map and canonical_name in municipality_to_district_map:
        return municipality_to_district_map[canonical_name]
    return municipality_to_district(canonical_name)


def _exact_municipality(token: str, lang: str) -> str | None:
    """Resolve a municipality name by its own key, and by nothing else.

    The shared gazetteer is reached through neither of its two forgiving paths,
    and both exclusions are load-bearing.

    ``normalize_municipality`` ends in a 90%-similarity fuzzy match. Right for
    the primary extractor, where the input is already believed to be a
    municipality; wrong here, where the input is an arbitrary phrase lifted
    from a sentence.

    ``_lookup_keys`` is the subtler one. It also tries the trailing 2-, 3-, 4-
    and 5-token suffixes of the input, so that "Ward 5 Dullu Municipality"
    still resolves. Applied to "Shubh Kalika Rural Municipality" -- a real
    local unit of **Kalikot** -- the 3-token suffix "Kalika Rural Municipality"
    is a real local unit of **Rasuwa**, and matches *exactly*. Bypassing the
    fuzzy fallback alone does not stop that; only insisting on the full span's
    own key does.

    A name the gazetteer does not carry verbatim resolves to nothing, which is
    the correct outcome: a recovered district-day is worth less than a
    fabricated one costs.
    """

    gazetteers = load_municipality_gazetteers()
    alias_map = (
        gazetteers.en_alias_to_canonical if lang == 'en' else gazetteers.np_alias_to_canonical
    )
    return alias_map.get(_normalize_key(token))


def _candidate_place_tokens(sentence: str, lang: str) -> list[str]:
    if lang == 'np':
        raw = re.findall(r'[ऀ-ॿ]+', sentence)
    else:
        raw = re.findall(r"[A-Z][A-Za-z'’-]+(?:\s+[A-Z][A-Za-z'’-]+)?", sentence)
    tokens: list[str] = []
    for token in raw:
        cleaned = token.strip()
        if len(cleaned) < 3:
            continue
        if cleaned not in tokens:
            tokens.append(cleaned)
        # Nepali attaches case markers directly to the stem.
        if lang == 'np':
            for suffix in ('को', 'का', 'की', 'मा', 'ले', 'बाट', 'सम्म', 'तर्फ', 'कै'):
                if cleaned.endswith(suffix) and len(cleaned) > len(suffix) + 2:
                    stem = cleaned[: -len(suffix)]
                    if stem not in tokens:
                        tokens.append(stem)
    return tokens


# ---------------------------------------------------------------------------
# Traps
# ---------------------------------------------------------------------------


def _is_trapped(sentence: str, district: str, lang: str) -> bool:
    """Return whether this district mention is one of the audited traps."""

    lowered = sentence.casefold()
    haystack = sentence if lang == 'np' else lowered

    if _is_local_feature_name(sentence, district, lang):
        return True

    adjacency = NP_ADJACENCY_CUES if lang == 'np' else EN_ADJACENCY_CUES
    if any(cue in haystack for cue in adjacency):
        return True

    assessment = NP_ASSESSMENT_CUES if lang == 'np' else EN_ASSESSMENT_CUES
    if any(cue in haystack for cue in assessment):
        return True

    aggregate = NP_AGGREGATE_CUES if lang == 'np' else EN_AGGREGATE_CUES
    if any(cue in haystack for cue in aggregate):
        return True

    hospital = NP_HOSPITAL_CUES if lang == 'np' else EN_HOSPITAL_CUES
    if any(cue in haystack for cue in hospital):
        return True

    victim_cues = NP_VICTIM_CUES if lang == 'np' else EN_VICTIM_CUES
    if any(cue in haystack for cue in victim_cues):
        return True
    victim_pattern = NP_VICTIM_HOME_PATTERN if lang == 'np' else EN_VICTIM_HOME_PATTERN
    for match in victim_pattern.finditer(sentence):
        if _mentions(match.group('district'), district, lang):
            return True

    route_pattern = NP_ROUTE_PATTERN if lang == 'np' else EN_ROUTE_PATTERN
    for match in route_pattern.finditer(sentence):
        if _mentions(match.group('district'), district, lang):
            return True

    stranded_pattern = NP_STRANDED_PATTERN if lang == 'np' else EN_STRANDED_PATTERN
    for match in stranded_pattern.finditer(sentence):
        if _mentions(match.group('tail'), district, lang):
            return True

    distance_pattern = NP_DISTANCE_PATTERN if lang == 'np' else EN_DISTANCE_PATTERN
    for match in distance_pattern.finditer(sentence):
        if _mentions(match.group('district'), district, lang):
            return True

    if _is_travel_reference(sentence, district, lang):
        return True

    if _is_corridor_label(sentence, district, lang):
        return True

    return False


def _is_local_feature_name(sentence: str, district: str, lang: str) -> bool:
    """Reject a district alias used as part of a smaller named feature."""

    if lang != 'np':
        return False
    for match in re.finditer(r'[ऀ-ॿ]+', sentence):
        token = match.group(0)
        candidates = [token]
        for suffix in ('को', 'का', 'की', 'मा', 'ले', 'बाट', 'सम्म', 'तर्फ', 'कै'):
            if token.endswith(suffix) and len(token) > len(suffix) + 2:
                candidates.append(token[:-len(suffix)])
        resolved = None
        for candidate in candidates:
            resolved = normalize_district(candidate, 'np') or normalize_district(candidate, 'en')
            if resolved == district:
                break
        if resolved != district:
            continue
        tail = sentence[match.end(): match.end() + 10].lstrip()
        if any(tail.startswith(feature) for feature in NP_LOCAL_FEATURE_SUFFIXES):
            return True
    return False


def _is_corridor_label(sentence: str, district: str, lang: str) -> bool:
    """Whether the district name is part of a road's name rather than a place.

    Scoped tightly to adjacency: the district token must sit directly beside a
    road word, as in "Jumla road section" or "Hetauda-Kathmandu highway". A
    district that merely appears in the same sentence as a road is untouched,
    so "a landslide on the Mugling-Narayangadh section of Chitwan" still
    resolves Chitwan through its own possessive.
    """

    road_words = NP_ROAD_WORDS if lang == 'np' else EN_ROAD_WORDS
    pattern = r'[ऀ-ॿ]+' if lang == 'np' else r"[A-Z][A-Za-z'’-]+"
    for match in re.finditer(pattern, sentence):
        token = match.group(0)
        resolved = normalize_district(token, lang) or normalize_district(
            token, 'en' if lang == 'np' else 'np'
        )
        if resolved != district:
            continue
        after = sentence[match.end(): match.end() + 14]
        before = sentence[max(0, match.start() - 14): match.start()]
        haystack_after = after if lang == 'np' else after.casefold()
        haystack_before = before if lang == 'np' else before.casefold()
        if any(word in haystack_after for word in road_words):
            return True
        # "Hetauda-Kathmandu highway": the district is the second endpoint, so
        # the road word follows the *pair*, and a hyphen precedes the district.
        if '-' in haystack_before or '–' in haystack_before:
            if any(word in haystack_after for word in road_words):
                return True
        if any(word in haystack_before for word in road_words):
            return True
    return False


def _is_travel_reference(sentence: str, district: str, lang: str) -> bool:
    """Whether this district is named as an origin or destination of movement.

    A landslide closes a road, and reporters then say where the road went and
    where the stopped vehicles had come from. Those districts had no landslide.
    On a corpus run this made Kathmandu the most-recovered district in Nepal,
    on the strength of sentences like "vehicles coming from Kathmandu were
    halted at Mugling".
    """

    if lang == 'en':
        lowered = sentence.casefold()
        if not any(word in lowered for word in EN_MOVEMENT_WORDS):
            return False
        for match in re.finditer(r"[A-Z][A-Za-z'’-]+", sentence):
            if normalize_district(match.group(0), 'en') != district:
                continue
            prefix = sentence[max(0, match.start() - 14): match.start()].casefold()
            if any(prefix.endswith(word) for word in EN_TRAVEL_PREPOSITIONS):
                return True
        return False

    for match in re.finditer(r'[ऀ-ॿ]+', sentence):
        token = match.group(0)
        stem = token
        directional = False
        for suffix in NP_DIRECTIONAL_SUFFIXES:
            if token.endswith(suffix) and len(token) > len(suffix) + 2:
                stem = token[: -len(suffix)]
                directional = True
                break
        resolved = normalize_district(stem, 'np') or normalize_district(stem, 'en')
        if resolved != district:
            continue
        if directional:
            return True
        following = sentence[match.end(): match.end() + NP_MOVEMENT_WINDOW]
        if any(word in following for word in NP_MOVEMENT_WORDS):
            return True
    return False


def _mentions(fragment: str | None, district: str, lang: str) -> bool:
    """Return whether a text fragment resolves to this district."""

    if not fragment:
        return False
    for token in _candidate_place_tokens(fragment, lang):
        resolved = normalize_district(token, lang) or normalize_district(
            token, 'en' if lang == 'np' else 'np'
        )
        if resolved == district:
            return True
    for spans in _municipality_phrases(fragment, lang):
        for phrase in spans:
            resolved = _district_from_municipality(phrase, lang, None)
            if resolved is not None:
                if resolved == district:
                    return True
                break
    return False


# ---------------------------------------------------------------------------
# Dates
# ---------------------------------------------------------------------------


def _sentence_date_anchors(
    sentence: str,
    lang: str,
    published: date | None,
) -> list[tuple[str, str, float]]:
    """Return every ``(iso_date, basis, confidence)`` anchored in this sentence.

    All of them, not the first, because a sentence carrying two anchors is a
    status bulletin listing blockages from different days, and the caller drops
    it rather than picking one. Ordered strongest basis first.
    """

    anchors: list[tuple[str, str, float]] = []
    seen: set[str] = set()

    def add(value: str | None, basis: str, confidence: float) -> None:
        if value and value not in seen:
            seen.add(value)
            anchors.append((value, basis, confidence))

    if lang == 'np':
        for value in _explicit_bs_dates(sentence, published):
            add(value, 'explicit_bs_date', 0.92)
    else:
        for value in _explicit_ad_dates(sentence, published):
            add(value, 'explicit_ad_date', 0.92)

    if published is None:
        return anchors

    weekdays = NP_WEEKDAYS if lang == 'np' else EN_WEEKDAYS
    haystack = sentence if lang == 'np' else sentence.casefold()
    for name, index in weekdays.items():
        if name in haystack:
            delta = (published.weekday() - index) % 7
            add((published - timedelta(days=delta)).isoformat(), 'weekday', 0.78)

    if not anchors:
        last_night = NP_LAST_NIGHT_CUES if lang == 'np' else EN_LAST_NIGHT_CUES
        if any(cue in haystack for cue in last_night):
            add((published - timedelta(days=1)).isoformat(), 'previous_day', 0.72)
        today = NP_TODAY_CUES if lang == 'np' else EN_TODAY_CUES
        if any(cue in haystack for cue in today):
            add(published.isoformat(), 'publication_day_explicit', 0.70)
    return anchors


def _explicit_bs_dates(sentence: str, published: date | None) -> list[str]:
    """Return every BS date in the sentence, converted to AD.

    The BS year is rarely written in these bulletins, so it is inferred from the
    publication date; a conversion landing in the future, or more than a season
    before publication, is rejected rather than guessed at.
    """

    if published is None:
        return []
    import nepali_datetime

    ascii_digits = sentence.translate(DEVANAGARI_DIGITS)
    resolved: list[str] = []

    # A written-out BS year wins outright. Without this, "९ असार २०७४" -- a
    # 2024 article recalling a failure of 2017 -- had its year replaced by the
    # publication year and landed seven years out, on the right month and day,
    # which is exactly the shape that survives a plausibility check.
    for match in NP_BS_FULL_DATE.finditer(ascii_digits):
        day_text, month_name, year_text = match.group(1), match.group(2), match.group(3)
        month = BS_MONTH_MAP.get(month_name)
        if month is None:
            continue
        try:
            converted = bs_to_ad((int(year_text), month, int(day_text)))
        except Exception:
            continue
        iso = converted.isoformat()
        if iso not in resolved:
            resolved.append(iso)
    if resolved:
        return resolved

    pairs: list[tuple[int, int]] = []
    for match in NP_MONTH_BS_DAY.finditer(ascii_digits):
        month = BS_MONTH_MAP.get(match.group(1))
        if month:
            pairs.append((month, int(match.group(2))))
    for match in NP_BS_DAY_MONTH.finditer(ascii_digits):
        month = BS_MONTH_MAP.get(match.group(2))
        if month:
            pairs.append((month, int(match.group(1))))

    # A bare "१६ गते" carries the month of the nearest preceding BS month name.
    months_present = {month for month, _ in pairs}
    if len(months_present) == 1:
        only_month = next(iter(months_present))
        for match in re.finditer(r'(?<!\d)(\d{1,2})\s*गते', ascii_digits):
            pairs.append((only_month, int(match.group(1))))

    published_bs = nepali_datetime.date.from_datetime_date(published)
    resolved: list[str] = []
    for month, day in pairs:
        if not 1 <= day <= 32:
            continue
        for year in (published_bs.year, published_bs.year - 1):
            try:
                converted = bs_to_ad((year, month, day))
            except Exception:
                continue
            gap = (published - converted).days
            if 0 <= gap <= 120:
                iso = converted.isoformat()
                if iso not in resolved:
                    resolved.append(iso)
                break
    return resolved


def _explicit_ad_dates(sentence: str, published: date | None) -> list[str]:
    if published is None:
        return []
    months = (
        'January|February|March|April|May|June|July|August|September|October|November|December'
    )
    resolved: list[str] = []
    for match in re.finditer(rf'\b({months})\s+(\d{{1,2}})\b', sentence):
        month = datetime.strptime(match.group(1), '%B').month
        day = int(match.group(2))
        for year in (published.year, published.year - 1):
            try:
                candidate = date(year, month, day)
            except ValueError:
                continue
            gap = (published - candidate).days
            if 0 <= gap <= 120:
                iso = candidate.isoformat()
                if iso not in resolved:
                    resolved.append(iso)
                break
    return resolved


# ---------------------------------------------------------------------------
# Text preparation
# ---------------------------------------------------------------------------


def _prepare(title: str | None, text: str) -> str:
    parts = [part for part in ((title or '').strip(), (text or '').strip()) if part]
    return unicodedata.normalize('NFC', '\n'.join(parts))


def _strip_footer(text: str) -> str:
    cut = len(text)
    for marker in FOOTER_MARKERS:
        position = text.find(marker)
        if position != -1:
            cut = min(cut, position)
    return text[:cut]


def _split_sentences(text: str, lang: str) -> list[str]:
    if lang == 'np':
        pieces = re.split(r'(?<=[।!?])\s+|\n+', text)
    else:
        pieces = re.split(r'(?<=[.!?])\s+|\n+', text)
    return [piece.strip() for piece in pieces if piece and piece.strip()]


def _looks_like_dateline(sentence: str, lang: str) -> bool:
    pattern = NP_DATELINE_PATTERN if lang == 'np' else EN_DATELINE_PATTERN
    return bool(pattern.match(sentence))


def _drop_dateline(sentence: str, lang: str) -> str:
    """Remove the filing location so it cannot be read as a failure site."""

    pattern = NP_DATELINE_PATTERN if lang == 'np' else EN_DATELINE_PATTERN
    match = pattern.match(sentence)
    if match is None:
        return sentence
    return sentence[match.end():].strip()


def _days_between(left: str, right: str) -> int:
    """Return the signed day gap between two ISO dates, or 0 if unparseable."""

    first = _coerce_date(left)
    second = _coerce_date(right)
    if first is None or second is None:
        return 0
    return (first - second).days


def _coerce_date(value: str | date | None) -> date | None:
    if value is None or value == '':
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None
