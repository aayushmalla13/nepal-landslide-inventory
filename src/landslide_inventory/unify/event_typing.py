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
no settlement impact. A labelled development-set review subsequently confirmed
that a real, single road landslide belongs in the article headline target. Such
rows therefore count when ``event_granularity = 'single'``; the subtype remains
available for impact-specific analyses and is still excluded from the BIPAD
comparison, where the unit of analysis does not match.

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

import logging
import re
from dataclasses import dataclass
from typing import Any

LOGGER = logging.getLogger(__name__)

EVENT_TYPE_LANDSLIDE = 'landslide'
EVENT_TYPE_ROAD_OBSTRUCTION = 'road_obstruction'
EVENT_TYPE_AGGREGATE_REPORT = 'aggregate_report'
EVENT_TYPE_OTHER = 'other'

GRANULARITY_SINGLE = 'single'
GRANULARITY_MULTI = 'multi'
GRANULARITY_ROUNDUP = 'roundup'

ROLE_FIRST_REPORT = 'first_report'
ROLE_FOLLOW_UP = 'follow_up'
ROLE_RETROSPECTIVE = 'retrospective'
ROLE_FORECAST_OR_RISK = 'forecast_or_risk'

# Hazard vocabulary, matching validation/locked_test_set.TRUTH_VOCABULARIES so
# annotator labels and pipeline output are directly comparable.
HAZARD_LANDSLIDE = 'landslide'
HAZARD_DEBRIS_FLOW = 'debris_flow'
HAZARD_ROCKFALL = 'rockfall'
HAZARD_AVALANCHE = 'avalanche'
HAZARD_FLOOD = 'flood'
HAZARD_OTHER = 'other_hazard'

# Only these count as a landslide inventory event. Avalanche and flood are
# different hazards with different physics, different triggers and different
# terrain, and pooling them makes the inventory unusable for susceptibility
# modelling.
HEADLINE_HAZARDS = frozenset({HAZARD_LANDSLIDE, HAZARD_DEBRIS_FLOW, HAZARD_ROCKFALL})

# AVALANCHE, and why it must be tested before anything else.
#
# In Nepali an avalanche is हिमपहिरो / हिउँपहिरो -- literally "snow-landslide".
# It *contains* पहिरो, the collection keyword. So every avalanche report is
# collected as a landslide by construction, and 'हिमपहिरो' was additionally
# listed in the title-event-signal tuple in event_specificity.py, which
# confirmed it as a landslide event rather than excluding it.
#
# Result: 25 of 1,003 headline events were avalanches, including Everest
# ("सगरमाथाको हिमपहिरो") and Manaslu. Review section 4.1 noted this in passing;
# the data says it is a systematic hazard-type error, not a footnote.
#
# Written with optional whitespace and both हिम/हिउँ stems because the compound
# is spelled हिमपहिरो, हिम पहिरो, हिउँपहिरो and हिउँ पहिरो interchangeably.
AVALANCHE_PATTERN = re.compile(
    r'\bavalanche(?:s)?\b|\bsnow\s*slide\b|\bsnowslide\b'
    r'|हिम\s*पहिरो|हिउँ\s*पहिरो|हिउ\s*पहिरो|हिमपात\s*पहिरो'
    r'|हिउँको\s+ढिस्को|हिउको\s+ढिस्को',
    re.IGNORECASE,
)

ROCKFALL_PATTERN = re.compile(
    r'\brock\s*fall(?:s)?\b|\brockslide\b|\bboulder\b'
    r'|(?:ढुंगा|चट्टान|पहरा)\s*(?:खस|झर)'
    r'|(?:खसेको|झरेको)\s*(?:ढुंगा|चट्टान|पहरा)',
    re.IGNORECASE,
)

DEBRIS_FLOW_PATTERN = re.compile(
    r'\bdebris\s*flow\b|\bmudflow\b|\bmudslide(?:s)?\b'
    r'|बाढी\s*पहिरो|थेग्रो|डेब्रिज|लेदो\s*(?:माटो|सहित(?:को)?)?',
    re.IGNORECASE,
)

LANDSLIDE_PATTERN = re.compile(
    r'\blandslide(?:s)?\b|\bslope\s*failure\b|\bslip\b'
    r'|पहिरो|भूस्खलन|ढिस्को',
    re.IGNORECASE,
)

# Flood-only reports that carry no landslide term at all.
FLOOD_PATTERN = re.compile(
    r'\bflood(?:s|ing)?\b|\binundation\b|\bdeluge\b'
    r'|बाढी|डुबान|जलमग्न',
    re.IGNORECASE,
)

EXTRACTION_BASIS_FULL = 'full_text'
EXTRACTION_BASIS_TITLE_ONLY = 'title_only'

# Bodies at or below this are too thin to have supported extraction. Matches
# MIN_BODY_CHARS in validation/article_quality.py -- keep them in step.
TITLE_ONLY_BODY_CHARS = 200

# Impact language is only reliable in the headline and article lead. Scraped
# pages often append related stories, navigation, and a second district event;
# treating every later mention as part of the headline event caused systematic
# road-obstruction false negatives in the adjudicated audit.
IMPACT_LEAD_CHARS = 600

# AGGREGATE REPORTS -- articles that state a running total, not an event.
#
# These are the single largest source of error in the casualty field. Before
# this filter the inventory recorded 6,242 landslide deaths across 862 events
# (25.6 per fatal event) against a real national toll of roughly 100-150 a year.
# Scoping the casualty extractor to the lead removed half of it; the remainder
# comes from articles that are *entirely* aggregate:
#
#   "Floods, landslides claim 1000 plus lives in five years"        -> 480 deaths
#   "134 people dead in floods, landslides since monsoon rain"      -> 134
#   "90 killed in floods, landslides so far, DPM informs House"     ->  90
#   "गृहको समीक्षा : समन्वयमा चुक्यौं" (Home Ministry review)         -> 170
#
# Every one was assigned to a single district -- 480 deaths to Bardiya, a Terai
# district. They are not extraction failures; they are non-events that the
# specificity filter let through. Typed and excluded rather than deleted, so the
# count is disclosable.
PERIOD_TOTAL_PATTERN = re.compile(
    r'\bsince\s+(?:the\s+)?(?:monsoon|onset|beginning|start)'
    r'|\bso far\b|\bto date\b|\bthis (?:monsoon|year|season)\b|\bthis year alone\b'
    r'|\bin\s+(?:the\s+)?(?:past|last)?\s*(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)'
    r'\s*(?:years?|months?|weeks?|days?)\b'
    r'|\bover the (?:years|last|past)\b|\bcumulative\b|\bin total\b'
    r'|अहिलेसम्म|हालसम्म|यसवर्ष|यस वर्ष|यो मनसुन|यता|वर्षमा|महिनामा|कुल|जम्मा',
    re.IGNORECASE,
)

MULTI_HAZARD_PATTERN = re.compile(
    r'\bfloods?\s+and\s+landslides?\b|\blandslides?\s+and\s+floods?\b'
    r'|\bfloods?,\s*landslides?\b|\blandslides?,\s*floods?\b'
    r'|बाढी\s*[–—-]?\s*पहिरो|पहिरो\s*[–—-]?\s*बाढी|बाढीपहिरो|प्राकृतिक विपद',
    re.IGNORECASE,
)

NATIONAL_SCOPE_PATTERN = re.compile(
    r'\bnationwide\b|\bacross the country\b|\bcountry-?wide\b|\bin nepal\b'
    r'|\bvarious districts\b|\bseveral districts\b'
    r'|देशभर|देशैभरि|देशभरि|राष्ट्रिय',
    re.IGNORECASE,
)

# Government/institutional framing: a ministry review, a PM inspection, a
# parliamentary statement. The article is about the response, not an event.
INSTITUTIONAL_PATTERN = re.compile(
    r'\b(?:informs house|house of representatives|parliament|minister|ministry|'
    r'prime minister|cabinet|review meeting|convenes|briefing|'
    r'informs|urges|directs|discussion)\b'
    r'|गृहको समीक्षा|मन्त्रिपरिषद|प्रधानमन्त्री|प्रचण्ड|देउवा|ओली|संसद|मन्त्रालय|'
    r'समीक्षा|बैठक|छलफल|बोलाए|निर्देशन',
    re.IGNORECASE,
)

RESPONSE_ONLY_TITLE_PATTERN = re.compile(
    r'\b(?:relief|compensation|prevention|mitigation|control project|response team)\b'
    r'|(?:राहत|क्षतिपूर्ति|रोकथाम|नियन्त्रण|नियंत्रण|उद्दारका लागि|उद्धारका लागि)',
    re.IGNORECASE,
)

MULTI_EVENT_PATTERN = re.compile(
    r'\b(?:several|various|multiple|different)\s+'
    r'(?:places|locations|villages|districts|parts|vdc(?:s)?|sites)\b'
    r'|\b(?:two|three|four|five|six|seven|eight|nine|ten|\d+)\s+'
    r'(?:different\s+)?(?:places|locations|villages|districts|vdc(?:s)?|sites)\b'
    r'|\b(?:separate|distinct)\s+(?:landslides|incidents)\b'
    r'|\bmultiple\s+landslides?\b'
    r'|ठाउँठाउँ|ठाउँ-ठाउँ|विभिन्न\s*(?:स्थान|ठाउँ|गाउँ|जिल्ला|वडा|भाग)'
    r'|(?:दुई|तीन|चार|पाँच|छ|सात|आठ|नौ|दश|[२-९2-9])\s*'
    r'(?:वटा\s*)?(?:स्थान|ठाउँ|गाउँ|जिल्ला|वडा|आयोजना)'
    r'|यी\s+सडकखण्ड',
    re.IGNORECASE,
)

MULTI_ADMIN_PATTERN = re.compile(
    r'\b(?:municipality|rural municipality|vdc|ward)\b[^.\n]{0,140}'
    r'\b(?:and|similarly|likewise)\b[^.\n]{0,140}'
    r'\b(?:municipality|rural municipality|vdc|ward)\b'
    r'|(?:नगरपालिका|गाउँपालिका|वडा)[^।\n]{0,140}'
    r'(?:त्यसैगरी|यस्तै|र)[^।\n]{0,140}(?:नगरपालिका|गाउँपालिका|वडा)',
    re.IGNORECASE,
)

REPEATED_EVENT_PATTERN = re.compile(
    r'\b(?:again|repeatedly|another landslide|fresh landslide)\b'
    r'|फेरि[^।\n]{0,20}पहिरो|पुनः[^।\n]{0,20}पहिरो|बारम्बार\s*पहिरो',
    re.IGNORECASE,
)

FOLLOW_UP_TITLE_PATTERN = re.compile(
    r'\b(?:update|death toll (?:reaches|rises|climbs)|bodies? recovered|'
    r'identified|reopens?|reopened|resumes?|resumed|relief|compensation|'
    r'inspection|search continues?)\b'
    r'|अपडेट|मृतकको संख्या|मृत्यु हुनेको संख्या|पहिचान खुल्यो|सनाखत|'
    r'खुल्यो|खुलेको|सञ्चालनमा|निरीक्षण|राहत|क्षतिपूर्ति|शव\s*(?:फेला|भेटियो)',
    re.IGNORECASE,
)

FORECAST_TITLE_PATTERN = re.compile(
    r'\b(?:at high risk|risk of|warning|forecast|could trigger|likely to|'
    r'prevention|preparedness|monitoring)\b'
    r'|उच्च जोखिम|पहिरोको जोखिम|चेतावनी|पूर्वानुमान|रोकथाम|तयारी|'
    r'हुन नदिइने|जान सक्ने',
    re.IGNORECASE,
)

RETROSPECTIVE_TITLE_PATTERN = re.compile(
    r'\b(?:years? (?:after|since)|anniversary|history of|over the years)\b'
    r'|वर्षपछि|वर्षदेखि|इतिहास|विगत',
    re.IGNORECASE,
)

OBSERVED_EVENT_PATTERN = re.compile(
    r'\b(?:occurred|triggered|hit|fell|collapsed|blocked|obstructed|washed away|'
    r'buried|damaged|killed|missing|injured|mud slip)\b'
    r'|पहिरो\s*(?:गयो|खस्यो|आयो)|बगायो|पुरियो|पुरिए|अवरुद्ध|क्षति|मृत्यु|'
    r'बेपत्ता|घाइते|विस्थापित',
    re.IGNORECASE,
)


# A specific incident with its own casualties, e.g. "Landslide kills three in
# Sindhupalchok". Protects real events from the institutional/multi-hazard
# heuristics above.
DIRECT_INCIDENT_TITLE_PATTERN = re.compile(
    r'(?:landslide|landslides|mudslide|rockfall|पहिरो|भूस्खलन)[^\n]{0,60}'
    r'(?:kill|kills|killed|dead|die|dies|died|buri|swept|missing|injur|'
    r'मृत्यु|मृतक|शव|पुरिए|पुरिँदा|बेपत्ता|वेपत्ता|घाइते|बगायो)'
    r'|(?:kill|kills|killed|dead|die|dies|died|buri|swept|missing|injur|'
    r'मृत्यु|मृतक|शव|पुरिए|पुरिँदा|बेपत्ता|वेपत्ता|घाइते|बगायो)[^\n]{0,60}'
    r'(?:landslide|landslides|mudslide|rockfall|पहिरो|भूस्खलन)',
    re.IGNORECASE,
)


def is_aggregate_report(title: str | None) -> bool:
    """Whether a title states a running total or institutional response.

    Judged on the TITLE only. A body may legitimately mention seasonal totals as
    context; a title that leads with one means the article itself is an
    aggregate.
    """

    heading = (title or '').strip()
    if not heading:
        return False
    period = PERIOD_TOTAL_PATTERN.search(heading) is not None
    multi = MULTI_HAZARD_PATTERN.search(heading) is not None
    national = NATIONAL_SCOPE_PATTERN.search(heading) is not None
    institutional = INSTITUTIONAL_PATTERN.search(heading) is not None
    response_only = RESPONSE_ONLY_TITLE_PATTERN.search(heading) is not None
    # A title reporting a specific incident with its own casualties is an
    # event even if a minister appears in it ("Minister visits site where three
    # died"). Everything else that is institutional is about the response, not
    # the event.
    direct_incident = DIRECT_INCIDENT_TITLE_PATTERN.search(heading) is not None
    if direct_incident and not (period or national or multi):
        return False
    return period or national or institutional or multi or response_only


# Road/highway infrastructure vocabulary, EN and NP.
ROAD_TERMS_PATTERN = re.compile(
    r'\b(?:highway|high\s*way|road|roadway|road\s*section|carriageway|track)\b'
    r'|सडक|राजमार्ग|मार्ग|बाटो|सडकखण्ड|खण्ड|करिडोर|आवागमन',
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
    r'पन्छाउन|सञ्चालनमा|खुल्यो|खुलेको|खुलेन|एकतर्फी|यातायात',
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
    r'\b(?:house|houses|homes|household|households|'
    r'school|shed|cowshed|farmland|cattle)\b'
    r'|घर|घरहरू|बस्ती|विद्यालय|गोठ|खेत|पशु',
    re.IGNORECASE,
)

# Outside an explicit road-obstruction headline, preserve the conservative
# full-text rule used by earlier releases. These broad locality terms are only
# unsafe when a headline already establishes that the observation unit is the
# road blockage itself.
SETTLEMENT_MENTION_PATTERN = re.compile(
    r'\b(?:house|houses|home|homes|household|households|village|settlement|'
    r'school|shed|cowshed|farmland|cattle)\b'
    r'|घर|घरहरू|बस्ती|गाउँ|विद्यालय|गोठ|खेत|पशु',
    re.IGNORECASE,
)

# Directly work-induced collapses are occupational/construction accidents, not
# natural slope-failure observations. Keep this deliberately phrase-based so a
# natural landslide that merely hits workers or a construction site is not
# removed from the inventory.
WORK_INDUCED_COLLAPSE_PATTERN = re.compile(
    r'\bwhile\s+(?:digging|excavating|widening)\b'
    r'|\bduring\s+(?:excavation|road\s+widening|construction\s+work)\b'
    r'|\bdigging\s+(?:the\s+)?foundation\b'
    r'|(?:सडक\s*फराकिलो|ढुंगा\s*फुटाउने|सडक\s*खन्ने|सडक\s*खन्‍ने)'
    r'[^।\n]{0,60}क्रममा',
    re.IGNORECASE,
)


@dataclass(frozen=True)
class EventTyping:
    event_type: str
    extraction_basis: str
    reason: str
    hazard_type: str = HAZARD_LANDSLIDE
    event_granularity: str = GRANULARITY_SINGLE
    article_role: str = ROLE_FIRST_REPORT

    @property
    def in_headline_counts(self) -> bool:
        """Whether this row belongs in the paper's headline event count.

        A road obstruction caused by a real, single landslide is still a
        landslide observation. ``event_type`` remains available as an impact
        subtype; granularity and hazard decide headline eligibility.
        """

        return (
            self.hazard_type in HEADLINE_HAZARDS
            and self.event_type in {EVENT_TYPE_LANDSLIDE, EVENT_TYPE_ROAD_OBSTRUCTION}
            and self.event_granularity == GRANULARITY_SINGLE
            and self.article_role != ROLE_FORECAST_OR_RISK
        )

    @property
    def eligible_for_bipad(self) -> bool:
        """Road obstructions have no counterpart unit in BIPAD.

        Avalanches do exist in BIPAD but under a different hazard code, so
        comparing them against a landslide inventory would inflate both sides.
        """

        return self.in_headline_counts and self.event_type == EVENT_TYPE_LANDSLIDE


def classify_hazard_type(title: str | None, text: str | None) -> str:
    """Identify which hazard an article actually describes.

    Order is not arbitrary. Avalanche is tested first because the Nepali word
    for it (हिमपहिरो, "snow-landslide") *contains* the word for landslide, so
    any landslide-first check classifies every avalanche as a landslide.
    Debris flow and rockfall are tested before the generic landslide term for
    the same containment reason.
    """

    heading = (title or '').strip()
    body = (text or '').strip()
    combined = f'{heading}\n{body}'
    if not combined.strip():
        return HAZARD_LANDSLIDE

    lead = f'{heading}\n{body[:IMPACT_LEAD_CHARS]}'
    if WORK_INDUCED_COLLAPSE_PATTERN.search(lead):
        return HAZARD_OTHER

    # A specific title is authoritative. A generic landslide title may be
    # refined by mud/debris or direct falling-rock language in the lead, but a
    # background avalanche/flood mention must not override the headline event.
    if AVALANCHE_PATTERN.search(heading):
        return HAZARD_AVALANCHE
    if DEBRIS_FLOW_PATTERN.search(heading):
        return HAZARD_DEBRIS_FLOW
    if ROCKFALL_PATTERN.search(heading):
        return HAZARD_ROCKFALL
    if LANDSLIDE_PATTERN.search(heading):
        if DEBRIS_FLOW_PATTERN.search(lead):
            return HAZARD_DEBRIS_FLOW
        if ROCKFALL_PATTERN.search(lead):
            return HAZARD_ROCKFALL
        return HAZARD_LANDSLIDE
    if FLOOD_PATTERN.search(heading):
        return HAZARD_FLOOD

    for pattern, hazard in (
        (AVALANCHE_PATTERN, HAZARD_AVALANCHE),
        (DEBRIS_FLOW_PATTERN, HAZARD_DEBRIS_FLOW),
        (ROCKFALL_PATTERN, HAZARD_ROCKFALL),
        (LANDSLIDE_PATTERN, HAZARD_LANDSLIDE),
        (FLOOD_PATTERN, HAZARD_FLOOD),
    ):
        if pattern.search(lead):
            return hazard
    return HAZARD_OTHER


def classify_event_granularity(title: str | None, text: str | None) -> str:
    """Classify one article as a single event, multiple events, or a roundup."""

    heading = (title or '').strip()
    body = (text or '').strip()
    lead = body[:250]
    combined = f'{heading}\n{lead}'
    if is_aggregate_report(heading):
        return GRANULARITY_ROUNDUP
    if MULTI_EVENT_PATTERN.search(heading) or MULTI_ADMIN_PATTERN.search(heading):
        return GRANULARITY_MULTI
    if (
        ROAD_TERMS_PATTERN.search(heading)
        and OBSTRUCTION_TERMS_PATTERN.search(heading)
        and (
            re.search(r'\blandslides\b|\bmost roads\b', heading, re.IGNORECASE)
            or re.search(r'विभिन्न\s*सडक|सडक[^।\n]{0,50}\sर\s[^।\n]{0,50}सडक', heading)
        )
    ):
        return GRANULARITY_MULTI
    # Road reports use the blockage as their observation unit. Later prose
    # often lists other unstable spots along the corridor as context; that
    # does not turn the reported blockage into a roundup.
    if ROAD_TERMS_PATTERN.search(heading) and OBSTRUCTION_TERMS_PATTERN.search(heading):
        return GRANULARITY_SINGLE
    # "Again"/"fresh" describes a newly observed occurrence, not multiple
    # events inside this article.
    if REPEATED_EVENT_PATTERN.search(heading):
        return GRANULARITY_SINGLE
    if MULTI_EVENT_PATTERN.search(lead) or MULTI_ADMIN_PATTERN.search(lead):
        return GRANULARITY_MULTI
    # A singular, direct-incident headline remains the unit of analysis even
    # when the final paragraph mentions other affected places as context.
    if (
        DIRECT_INCIDENT_TITLE_PATTERN.search(heading)
        and re.search(r'\blandslides\b', heading, re.IGNORECASE) is None
    ):
        return GRANULARITY_SINGLE
    if (
        MULTI_EVENT_PATTERN.search(combined)
        or MULTI_ADMIN_PATTERN.search(combined)
    ):
        return GRANULARITY_MULTI
    if (
        len(body) < TITLE_ONLY_BODY_CHARS
        and re.search(r'\blandslides\b', heading, re.IGNORECASE)
        and DIRECT_INCIDENT_TITLE_PATTERN.search(heading)
    ):
        return GRANULARITY_MULTI
    return GRANULARITY_SINGLE


def classify_article_role(title: str | None, text: str | None) -> str:
    """Classify the article's relationship to the reported event."""

    heading = (title or '').strip()
    if re.search(
        r'\b(?:prevention|preparedness|monitoring)\b|रोकथाम|हुन नदिइने|जान नदिइने',
        heading,
        re.IGNORECASE,
    ):
        return ROLE_FORECAST_OR_RISK
    if (
        FORECAST_TITLE_PATTERN.search(heading)
        and OBSERVED_EVENT_PATTERN.search(heading) is None
    ):
        return ROLE_FORECAST_OR_RISK
    if RETROSPECTIVE_TITLE_PATTERN.search(heading):
        return ROLE_RETROSPECTIVE
    if FOLLOW_UP_TITLE_PATTERN.search(heading):
        return ROLE_FOLLOW_UP
    return ROLE_FIRST_REPORT


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
    lead_scope = f'{heading}\n{body[:IMPACT_LEAD_CHARS]}'
    heading_has_road = bool(ROAD_TERMS_PATTERN.search(heading))
    heading_has_obstruction = bool(OBSTRUCTION_TERMS_PATTERN.search(heading))
    road_obstruction_title = heading_has_road and heading_has_obstruction
    road_obstruction_focus = road_obstruction_title or (
        heading_has_road and bool(OBSTRUCTION_TERMS_PATTERN.search(lead_scope))
    ) or (
        heading_has_obstruction and bool(ROAD_TERMS_PATTERN.search(lead_scope))
    )
    impact_scope = (
        lead_scope
        if road_obstruction_focus
        else combined
    )
    hazard = classify_hazard_type(title, text)
    granularity = classify_event_granularity(title, text)
    role = classify_article_role(title, text)

    basis = (
        EXTRACTION_BASIS_TITLE_ONLY
        if len(body) < TITLE_ONLY_BODY_CHARS
        else EXTRACTION_BASIS_FULL
    )

    # Checked before casualties: an aggregate report always HAS a casualty
    # count -- that is what makes it dangerous. Letting the casualty branch win
    # would keep every roundup in the headline inventory.
    if is_aggregate_report(title):
        return EventTyping(
            EVENT_TYPE_AGGREGATE_REPORT, basis, 'aggregate_report', hazard,
            granularity, role,
        )
    if WORK_INDUCED_COLLAPSE_PATTERN.search(impact_scope):
        return EventTyping(
            EVENT_TYPE_OTHER, basis, 'construction_induced_slope_collapse', hazard,
            granularity, role,
        )
    if any(value for value in (deaths, missing, injured) if value):
        return EventTyping(
            EVENT_TYPE_LANDSLIDE, basis, 'casualties_recorded', hazard,
            granularity, role,
        )
    if HUMAN_IMPACT_PATTERN.search(impact_scope):
        return EventTyping(
            EVENT_TYPE_LANDSLIDE, basis, 'human_impact_language', hazard,
            granularity, role,
        )
    settlement_pattern = (
        SETTLEMENT_IMPACT_PATTERN
        if road_obstruction_focus
        else SETTLEMENT_MENTION_PATTERN
    )
    if settlement_pattern.search(impact_scope):
        return EventTyping(
            EVENT_TYPE_LANDSLIDE, basis, 'settlement_impact_language', hazard,
            granularity, role,
        )

    # No human or settlement impact in the relevant event scope. Anchor at
    # least one road/obstruction signal in the title; a body that merely
    # mentions a highway in passing is not a road-obstruction report.
    if road_obstruction_focus:
        return EventTyping(
            EVENT_TYPE_ROAD_OBSTRUCTION, basis,
            'road_obstruction_title' if road_obstruction_title else 'road_obstruction_body',
            hazard,
            granularity, role,
        )
    if ROAD_TERMS_PATTERN.search(combined) and OBSTRUCTION_TERMS_PATTERN.search(combined):
        return EventTyping(
            EVENT_TYPE_ROAD_OBSTRUCTION, basis, 'road_obstruction_body', hazard,
            granularity, role,
        )

    return EventTyping(
        EVENT_TYPE_LANDSLIDE, basis, 'default_landslide', hazard,
        granularity, role,
    )


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
    hazards: dict[str, int] = {}
    granularities: dict[str, int] = {}
    roles: dict[str, int] = {}
    headline = 0
    for record in records:
        types[record['event_type']] = types.get(record['event_type'], 0) + 1
        bases[record['extraction_basis']] = bases.get(record['extraction_basis'], 0) + 1
        hazard = record.get('hazard_type', HAZARD_LANDSLIDE)
        hazards[hazard] = hazards.get(hazard, 0) + 1
        granularity = record.get('event_granularity', GRANULARITY_SINGLE)
        role = record.get('article_role', ROLE_FIRST_REPORT)
        granularities[granularity] = granularities.get(granularity, 0) + 1
        roles[role] = roles.get(role, 0) + 1
        if (
            hazard in HEADLINE_HAZARDS
            and record['event_type'] in {
                EVENT_TYPE_LANDSLIDE,
                EVENT_TYPE_ROAD_OBSTRUCTION,
            }
            and granularity == GRANULARITY_SINGLE
            and role != ROLE_FORECAST_OR_RISK
        ):
            headline += 1
    return {
        'total': len(records),
        'headline_events': headline,
        'road_obstruction': types.get(EVENT_TYPE_ROAD_OBSTRUCTION, 0),
        'non_landslide_hazard': sum(n for h, n in hazards.items() if h not in HEADLINE_HAZARDS),
        'by_event_type': dict(sorted(types.items(), key=lambda kv: -kv[1])),
        'by_hazard_type': dict(sorted(hazards.items(), key=lambda kv: -kv[1])),
        'by_event_granularity': dict(
            sorted(granularities.items(), key=lambda kv: -kv[1])
        ),
        'by_article_role': dict(sorted(roles.items(), key=lambda kv: -kv[1])),
        'by_extraction_basis': dict(sorted(bases.items(), key=lambda kv: -kv[1])),
    }
