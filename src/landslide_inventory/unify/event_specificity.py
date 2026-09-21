"""Event-specificity filtering for extracted articles before dedup."""

from __future__ import annotations

import logging
import re
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from ..config import AppConfig
from ..db import connect_sqlite, initialize_sqlite
from ..utils import utc_now_iso
from .decisions import ensure_decisions_table, record_decision, snapshot_fields
from .event_typing import (
    GRANULARITY_MULTI,
    GRANULARITY_ROUNDUP,
    GRANULARITY_SINGLE,
    ROLE_FOLLOW_UP,
    classify_article_role,
    classify_event_granularity,
)

LOGGER = logging.getLogger(__name__)

RESCUE_PATTERNS = (
    'search ongoing', 'rescue operation', 'still missing', 'bodies recovered',
    'खोजी जारी', 'उद्धार', 'अझै बेपत्ता', 'शव निकालियो', 'शव फेला',
)
ROUNDUP_PATTERNS = (
    'so far this monsoon', 'this monsoon', 'in 10 years', 'in 5 years', 'in 20 years', 'death toll reaches', 'death toll rises to', 'toll rises to', 'toll climbs to', 'number of fatalities due to', 'highest number of fatalities',
    'nationwide total', 'province-wide total', 'district-wide total', 'over the last', 'cumulative', 'overall', 'has killed',
    'recent landslides and floods', 'death toll climbed to', 'this year alone', 'over the years', 'across the country', 'disaster incidents',
    'अहिलेसम्म', 'यो मनसुन', 'यति वर्षमा', 'मृत्यु हुनेको संख्या', 'मृतकको संख्या', 'कुल', 'समग्र', 'हालसम्म',
    'बाढीपहिरोमा परी मृत्यु हुनेको संख्या', 'बाढी पहिरोपीडित', 'देशभर', 'देशैभरि', 'देशभरि',
    'बाढी-पहिरोले देशभर', 'बाढीपहिरोले देशभर', 'देशभर १३ जनाको मृत्यु', 'जिल्लामा बाढीपहिरोबाट',
    'various districts', 'across various districts',
    'कहाँ कस्तो छ क्षति', 'प्रदेशमा कहाँ कस्तो', 'बाढी पहिरोको वितण्डा', 'बाढीपहिरोको वितण्डा',
)
RISK_PATTERNS = (
    'high risk', 'risk of landslides', 'warning', 'forecast', 'heavy rainfall likely', 'could trigger landslides',
    'risk of a landslide', 'at high risk of landslide', 'growing incidents of landslide', 'experts warn', 'houses at risk of being washed away',
    'उच्च जोखिम', 'पहिरोको जोखिम', 'चेतावनी', 'सतर्कता', 'पूर्वानुमान', 'भारी वर्षा', 'पहिरो जान सक्ने',
)
DAMAGE_ONLY_PATTERNS = (
    'damaged houses', 'loss', 'property damage', 'road damage', 'road section damaged', 'houses damaged',
    'क्षति', 'घरमा क्षति', 'सडकमा क्षति', 'घर क्षति', 'भौतिक क्षति',
)
FOLLOWUP_PATTERNS = (
    'relief to the families', 'compensation to the families', 'bodies recovered after', 'body recovered after',
    'identified among the dead', 'families to receive relief', 'victims get relief', 'survivors continue',
    'road reopens', 'road reopened', 'highway reopens', 'highway reopened', 'route opened',
    'debris cleared', 'landslide debris cleared', 'opened to one-way traffic', 'opened one-way',
    'मृतकका परिवारलाई', 'राहत दिइने', 'क्षतिपूर्ति', 'शव फेला', 'पहिचान खुल्यो',
    'खुल्यो', 'खुलेन', 'खुलेको', 'सञ्चालनमा आयो', 'सञ्चालनमा आउने', 'सञ्चालनमा',
    'पन्छाएपछि', 'पन्छाइएपछि', 'हटाएपछि', 'हटाइयो', 'पुन: सञ्चालन', 'पुनः सञ्चालन',
    'सनाखत', 'उपचार हुँदै', 'अपडेट',
)
CONTEXT_ONLY_PATTERNS = (
    'call for prompt relief', 'affected people', 'drawn the attention of the government',
    'meeting of the house of representatives', 'lawmakers speaking in the meeting',
    'joint press statement', 'effective relief and rescue efforts', 'relief and rescue efforts effective', 'provide food, shelter and other relief materials', 'those affected by floods, landslides and inundation',
    'poor slc results', 'blamed for poor', 'vegetables rot', 'affects road transport',
    'control landslide', 'control landslides', 'landslide control', 'dpr to control', 'permanent solution',
    'budget for flood', 'budget for landslide', 'reconstruction', 'mitigation', 'bio-engineering',
    'operation uncertain', 'landslide challenge', 'expressed sorrow', 'expresses sorrow',
    'गृहले भन्यो', 'क्षतिबारे जानकारी', 'खोजी र राहतमा जुट्न', 'हेलिकोप्टरबाट उद्धार गर्न',
    'नियन्त्रण आयोजना', 'पहिरो नियन्त्रण', 'बायो–इन्जिनियरिङ', 'बायो-इन्जिनियरिङ',
    'पुनर्निर्माण', 'बजेट', 'दुःख व्यक्त', 'जोगिने', 'चुनौती', 'सञ्चालन अनिश्चित',
)
NON_EVENT_PURPOSE_PATTERN = re.compile(
    r'\b(?:disaster|monsoon)\s+(?:preparedness|response|management)\s+(?:plan|planning)\b'
    r'|\b(?:planned|scheduled)\s+(?:road\s+)?(?:closure|shutdown)\b'
    r'|\btunnel\s+(?:work|construction)\b'
    r'|\bshut\s+during\s+night(?:time)?\b'
    r'|\b(?:monsoon\s+)?disaster\s+(?:plan|planning)\b'
    r'|\b(?:causes?|effects?|impacts?)\s+(?:and|of)\s+(?:landslides?|mitigation)\b'
    r'|\bdozer\s+use\s+causing\s+landslides?\b'
    r'|विपद्?\s*व्यवस्थापन(?:को)?\s*(?:योजना|तयारी|प्रयास)'
    r'|मनसुन(?:जन्य)?\s*विपद्?\s*(?:कार्ययोजना|तयारी)'
    r'|(?:बाढी\s*[/–—-]?\s*)?पहिरो[^\n]{0,40}(?:असर|प्रभाव)[^\n]{0,40}न्यूनीकरणका\s+उपाय',
    re.IGNORECASE,
)
GOVERNMENT_ATTENTION_PATTERN = re.compile(
    r'\b(?:lawmakers?|parliament)\b[^\n]{0,80}\b(?:investigation|attention)\b'
    r'|(?:गृहमन्त्री|संसद|सांसद)[^\n]{0,80}ध्यानाकर्षण',
    re.IGNORECASE,
)
TITLE_HAZARD_PATTERN = re.compile(
    r'\b(?:landslides?|mudslides?|rockfalls?|slope\s+failure)\b'
    r'|पहिर[ोा]|भूस्खलन|हिम\s*पहिरो|हिउँ\s*पहिरो',
    re.IGNORECASE,
)
PRIMARY_NON_LANDSLIDE_INCIDENT_PATTERN = re.compile(
    r'\b(?:bus|truck|vehicle|jeep|car)\b[^\n]{0,60}\b(?:crash|collision|accident)\b'
    r'|\b(?:crash|collision|accident)\b[^\n]{0,60}\b(?:bus|truck|vehicle|jeep|car)\b'
    r'|बसको\s+ठक्कर|सवारी\s+दुर्घटना|चितुवाको\s+आक्रमण|सर्पदंश',
    re.IGNORECASE,
)
LANDSLIDE_CAUSED_INCIDENT_PATTERN = re.compile(
    r'\b(?:crash|collision|accident)\b[^.\n]{0,80}\b(?:caused\s+by|due\s+to|after)\b'
    r'[^.\n]{0,40}\b(?:landslide|mudslide|rockfall)\b'
    r'|\b(?:landslide|mudslide|rockfall)\b[^.\n]{0,80}'
    r'\b(?:caused|triggered|led\s+to)\b[^.\n]{0,40}\b(?:crash|collision|accident)\b'
    r'|पहिरो(?:का कारण|ले)[^।\n]{0,80}(?:दुर्घटना|ठक्कर)',
    re.IGNORECASE,
)
FOREIGN_EVENT_NP_PATTERN = re.compile(
    r'(?:भारत|चीन|सिक्किम|उत्तराखण्ड|उत्तराखंड|हिमाचल|तिब्बत)मा[^।\n]{0,100}'
    r'(?:पहिरो|भूस्खलन|बाढी)[^।\n]{0,60}(?:गयो|आयो|गएको|आएको|पुरियो|बगायो)',
)
# Unambiguous political-metaphor phrases. Every entry here must be a phrase that
# cannot plausibly occur in a report of a physical landslide.
#
# HISTORY -- read before adding anything short. This tuple used to contain the
# bare substring 'by landslide', intended to catch "won by landslide". It also
# matched "buried by landslide" and "swept away by landslide", and so excluded
# 175 articles of which 128 were real Nepal landslide events with casualties
# ("11 people missing in Sankhuwasabha as eight houses are swept away by
# landslide"). That single 12-character string was the largest source of false
# negatives in the pipeline. See docs/TECHNICAL_REVIEW.md section 2.1 and run
# `--stage pattern_audit` before adding a pattern here.
#
# Entries removed for substring collision, and the regexes that replaced them:
#   'by landslide'   -> METAPHOR_ELECTORAL_PATTERN (requires a winning verb)
#   'विजय'            -> METAPHOR_ELECTORAL_PATTERN (also a common given name,
#                        Bijay; matched 44 articles, excluded 28)
#   'बहुमत'           -> METAPHOR_ELECTORAL_PATTERN
#   'constituency'   -> METAPHOR_ELECTORAL_PATTERN (appears in ordinary
#                        political-geography prose in disaster reporting)
#   'निर्वाचन'         -> METAPHOR_ELECTORAL_PATTERN
#   'अग्रता'          -> METAPHOR_ELECTORAL_PATTERN
METAPHOR_PATTERNS = (
    'landslide victory', 'landslide win', 'landslide wins', 'wins by landslide', 'won by landslide',
    'historic landslide', 'outright majority',
    'commanding lead', 'maintains lead', 'takes commanding lead', 'double lead',
    'election lead', 'parliamentary elections', 'prime ministerial candidate', 'vote count',
    'मतगणना',
)

# Political metaphor detected by *context*, not by a bare fragment. Each branch
# pairs an electoral term with an electoral action, so "swept away by landslide"
# (physical) cannot match while "swept to power by a landslide" (metaphor) can.
METAPHOR_ELECTORAL_PATTERN = re.compile(
    # "won / wins / elected ... by a landslide".
    # NOTE: 'swept' is deliberately NOT in this alternation. "swept away by
    # landslide" is the single most common phrasing for a fatal physical
    # landslide in this corpus; including 'swept' here reintroduces exactly the
    # false-negative class this regex was written to eliminate. The metaphorical
    # sense of 'swept' is handled by its own branch below, which requires
    # "to power"/"to victory".
    r'\b(?:won|win|wins|winning|elected|re-elected|romped|coasted)\b'
    r'[^.\n]{0,40}\bby\s+(?:a\s+|an\s+)?landslide\b'
    # "swept to power / to victory ... by a landslide"
    r'|\bswept\b[^.\n]{0,20}\bto\s+(?:power|victory|office)\b'
    # "landslide" adjacent to an unambiguous electoral noun
    r'|\blandslide\b[^.\n]{0,30}\b(?:victory|win|mandate|majority|verdict|poll|polls|election|elections)\b'
    r'|\b(?:victory|win|mandate|majority|verdict|poll|polls|election|elections)\b[^.\n]{0,30}\blandslide\b'
    # Nepali: an electoral noun within a short window of an electoral action.
    r'|(?:निर्वाचन|चुनाव|मतगणना|बहुमत|अग्रता)[^।\n]{0,40}(?:विजय|जित|जिते|जिती|निर्वाचित|पराजित|मत\s*पाए)'
    r'|(?:विजय|जित|जिते|जिती|निर्वाचित)[^।\n]{0,40}(?:निर्वाचन|चुनाव|मतगणना|बहुमत|अग्रता|मतदान)'
    # "constituency"/"निर्वाचन क्षेत्र" only counts alongside an electoral action.
    r'|\bconstituenc(?:y|ies)\b[^.\n]{0,60}\b(?:vote|votes|voted|ballot|poll|polls|candidate|candidates|elect|elected|election)\b'
    r'|\b(?:vote|votes|voted|ballot|poll|polls|candidate|candidates|elect|elected|election)\b[^.\n]{0,60}\bconstituenc(?:y|ies)\b',
    re.IGNORECASE,
)
FOREIGN_TERMS = (
    'india', 'china', 'pakistan', 'turkey', 'indonesia', 'bangladesh', 'afghanistan', 'myanmar', 'japan',
    'philippines', 'thailand', 'tibet', 'uttarakhand', 'himachal', 'himachal pradesh', 'sikkim', 'delhi', 'beijing', 'istanbul', 'california', 'sierra leone', 'hong kong',
    'भारत', 'चीन', 'पाकिस्तान', 'टर्की', 'इन्डोनेसिया', 'बंगलादेश', 'अफगानिस्तान', 'म्यानमार', 'जापान',
    'न्युजिल्यान्ड', 'न्यूजिल्यान्ड', 'न्युजील्यान्ड', 'न्यूजील्यान्ड', 'उत्तराखण्ड', 'उत्तराखंड', 'हिमाचल',
)

# Countries and foreign regions, EN and NP. The Nepali side was almost empty,
# which is how "सुडानमा पहिरोले पुरिएर कम्तीमा १००० जनाको मृत्यु" -- a Sudan
# landslide killing ~1,000 -- entered the inventory as an event in PARBAT
# DISTRICT, contributing 1,000 deaths to Nepal's national total.
#
# Nepali outlets report foreign disasters in Nepali, so an English-only foreign
# filter is structurally blind to exactly the articles most likely to leak. Any
# country added here must be added in BOTH scripts.
FOREIGN_TERMS_EXTRA = (
    # South Asia and neighbours
    'sri lanka', 'maldives', 'bhutan', 'sikkim', 'assam', 'meghalaya', 'kerala',
    'maharashtra', 'kashmir', 'ladakh', 'darjeeling', 'kalimpong',
    'श्रीलंका', 'श्रीलङ्का', 'भुटान', 'भूटान', 'सिक्किम', 'असम', 'केरला',
    'kedarnath', 'केदारनाथ',
    'कास्मिर', 'कस्मिर', 'दार्जिलिङ', 'दार्जिलिंग', 'लद्दाख',
    # Wider Asia
    'vietnam', 'malaysia', 'south korea', 'north korea', 'taiwan', 'cambodia',
    'भियतनाम', 'मलेसिया', 'दक्षिण कोरिया', 'उत्तर कोरिया', 'ताइवान',
    'तिब्बत', 'भारत', 'चीन', 'पाकिस्तान', 'बंगलादेश', 'श्रीलंका',
    # Africa, Americas, Europe -- all have produced fatal landslide wire copy
    'sudan', 'ethiopia', 'uganda', 'kenya', 'tanzania', 'congo', 'rwanda',
    'nigeria', 'cameroon', 'south africa',
    'सुडान', 'सूडान', 'इथियोपिया', 'युगाण्डा', 'केन्या', 'कंगो', 'नाइजेरिया',
    'colombia', 'ecuador', 'peru', 'bolivia', 'guatemala', 'mexico', 'brazil',
    'venezuela', 'chile', 'haiti',
    'कोलम्बिया', 'इक्वेडर', 'पेरु', 'बोलिभिया', 'ग्वाटेमाला', 'मेक्सिको',
    'ब्राजिल', 'भेनेजुएला', 'चिली', 'हैटी',
    'italy', 'norway', 'switzerland', 'austria', 'georgia', 'russia', 'ukraine',
    'इटाली', 'नर्वे', 'स्विट्जरल्यान्ड', 'अस्ट्रिया', 'रुस', 'युक्रेन',
    'papua new guinea', 'पपुवा न्यू गिनी', 'indonesia', 'इन्डोनेसिया',
)
FOREIGN_TERMS = tuple(dict.fromkeys(FOREIGN_TERMS + FOREIGN_TERMS_EXTRA))
NEPAL_TERMS = ('nepal', 'नेपाल')
URL_NEPAL_MARKERS = ('/nepal', '/national', '/social')
NEPAL_SIGNAL_PATTERN = re.compile(r'(?<![a-z])nepal(?![a-z])|नेपाल', re.IGNORECASE)
FOREIGN_HAZARD_DEMONYM_PATTERN = re.compile(
    r'\b(?:indian|chinese|pakistani|indonesian|bangladeshi|afghan|'
    r'japanese|filipino|myanmarese)\s+(?:landslide|mudslide|avalanche|flood)',
    re.IGNORECASE,
)

INCIDENT_NEAR_PATTERN = re.compile(
    r'(?:landslide|landslides|mudslide|mudslides|पहिरो|भूस्खलन).{0,80}'
    r'(?:occurred|hit|triggered|swept away|buried|collapsed|blocked|washed away|गयो|बगायो|पुरियो|अवरुद्ध|खस्यो|पहिरो खस्यो|पहिरो गयो)'
    r'|(?:occurred|hit|triggered|swept away|buried|collapsed|blocked|washed away|गयो|बगायो|पुरियो|अवरुद्ध|खस्यो|पहिरो खस्यो|पहिरो गयो).{0,80}'
    r'(?:landslide|landslides|mudslide|mudslides|पहिरो|भूस्खलन)',
    re.IGNORECASE | re.DOTALL,
)
DATE_PHRASE_PATTERN = re.compile(r'\b(?:today|yesterday|on\s+[A-Z][a-z]+\s+\d{1,2}(?:,\s*\d{4})?)\b', re.IGNORECASE)
NP_DATE_PHRASE_PATTERN = re.compile(r'(?:आज|हिजो|गत\s*\S+|\d{4}-\d{2}-\d{2}|[०-९]{4}-[०-९]{2}-[०-९]{2})')
MULTI_DISTRICT_PATTERN = re.compile(r'(?:\b\d+\s+districts\b|[०-९]+\s*जिल्लामा|\d+\s*जिल्लामा)')
NATIONWIDE_ROUNDUP_PATTERN = re.compile(r'(?:nationwide|province-wide|district-wide|across\s+\d+\s+districts|देशभर|देशैभरि|देशभरि)')
FOLLOWUP_DELAY_PATTERN = re.compile(r'(?:\bafter\s+\d+\s+days\b|\b\d+\s+days\s+later\b|[०-९]+\s*दिनपछि|\d+\s*दिनपछि|\bweeks\s+later\b)', re.IGNORECASE)
NP_COUNT_REACHED_PATTERN = re.compile(r'(?:मृतकको संख्या|ज्यान गुमाउनेको संख्या|मृत्यु हुनेको संख्या)\s*[०-९\d]+\s*पुग्यो')
NP_PERIOD_SUMMARY_PATTERN = re.compile(r'(?:एक|दुई|तीन|चार|पाँच|छ|सात|आठ|नौ|दश|एघार|बाह्र|तेह्र|चौध|पन्ध्र|सोह्र|सत्र|अठार|उन्नाइस|बीस|[०-९]+)\s*(?:साता|हप्ता|महिना|वर्ष|दिन)(?:को\s+अवधिमा|मा)')
NP_LONG_RUNNING_DISRUPTION_PATTERN = re.compile(r'[०-९\d]+\s*दिनदेखि[^.]{0,80}(?:यातायात|सडक|राजमार्ग).{0,40}अवरुद्ध')
ROUNDUP_CONNECTOR_PATTERN = re.compile(
    r'\b(?:likewise|similarly),[^.]{0,220}\b(?:killed|missing|dead|injured|lost\s+his\s+life|lost\s+her\s+life|lost\s+their\s+life|lost\s+their\s+lives)\b[^.]{0,220}\b(?:at|in)\s+[^.]{0,120}\b(?:municipality|rural\s+municipality|metropolitan\s+city|sub-metropolitan\s+city|district|ward|-\d)\b',
    re.IGNORECASE,
)
REGIONAL_BREAKDOWN_PATTERN = re.compile(
    r'\b(?:kathmandu valley|koshi province|madhesh province|bagmati province|gandaki province|lumbini province|karnali province|sudurpashchim province)\b',
    re.IGNORECASE,
)
DIRECT_CASUALTY_TITLE_PATTERN = re.compile(
    r'(?:\blandslide\b|\bmudslide\b|\brockfall\b|पहिरो|भूस्खलन).{0,80}(?:killed|dead|died|missing|injured|buried)'
    r'|(?:killed|dead|died|missing|injured|buried).{0,80}(?:\blandslide\b|\bmudslide\b|\brockfall\b|पहिरो|भूस्खलन)',
    re.IGNORECASE,
)
CONFIRMED_IMPACT_PATTERN = re.compile(
    r'\b(?:killed|dead|died|missing|injured|buried|blocked|obstructed|'
    r'damaged|destroyed|collapsed)\b'
    r'|मृत्यु|मृतक|बेपत्ता|घाइते|पुरियो|पुरिए|अवरुद्ध|अवरूद्ध|क्षति|भत्कियो',
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SpecificityRow:
    url: str
    source: str
    title: str | None
    text: str
    published_date_ad: str | None
    route_lang: str
    mixed_flag: bool
    devanagari_ratio: float
    event_class: int | None
    event_date_ad: str | None
    district: str | None
    municipality: str | None
    deaths: int | None
    missing: int | None
    injured: int | None


@dataclass(frozen=True)
class SpecificityDecision:
    specificity_ok: int
    specificity_reason: str
    specificity_score: float
    updated_class: int | None


def run_event_specificity_stage(config: AppConfig) -> int:
    """Populate article_specificity and downgrade non-specific rows before dedup."""

    initialize_sqlite(config.sqlite_path)
    study_start = date.fromisoformat(config.raw['study_period']['start'])
    study_end = date.fromisoformat(config.raw['study_period']['end'])
    rows = list(_specificity_rows(config.sqlite_path))
    exclude_terms = metaphor_exclude_terms(config)
    decided_at = utc_now_iso()
    reason_counts: Counter[str] = Counter()
    ok_counts: Counter[int] = Counter()

    with connect_sqlite(config.sqlite_path) as connection:
        ensure_decisions_table(connection)
        for row in rows:
            decision = decide_specificity(row, study_start, study_end, exclude_terms)
            # Log the decision AND the extractor's field values BEFORE the
            # UPDATE below nulls them. Without this, a demoted row's original
            # district/date/casualties are unrecoverable except by re-running
            # spaCy over the whole corpus (review section 2.2).
            record_decision(
                connection,
                url=row.url,
                stage='event_specificity',
                decision=decision.specificity_ok,
                reason=decision.specificity_reason,
                score=decision.specificity_score,
                updated_class=decision.updated_class,
                preserved=snapshot_fields(connection, row.url),
                decided_at=decided_at,
            )
            connection.execute(
                """
                INSERT INTO article_specificity (url, specificity_ok, specificity_reason, specificity_score, decided_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(url) DO UPDATE SET
                    specificity_ok = excluded.specificity_ok,
                    specificity_reason = excluded.specificity_reason,
                    specificity_score = excluded.specificity_score,
                    decided_at = excluded.decided_at
                """,
                (row.url, decision.specificity_ok, decision.specificity_reason, decision.specificity_score, decided_at),
            )
            connection.execute(
                """
                UPDATE article_events
                SET specificity_ok = ?,
                    specificity_reason = ?,
                    specificity_score = ?,
                    class = COALESCE(?, class),
                    event_class = COALESCE(?, event_class),
                    event_date_ad = CASE WHEN ? = 3 THEN NULL ELSE event_date_ad END,
                    district = CASE WHEN ? = 3 THEN NULL ELSE district END,
                    province = CASE WHEN ? = 3 THEN NULL ELSE province END,
                    municipality = CASE WHEN ? = 3 THEN NULL ELSE municipality END,
                    ward = CASE WHEN ? = 3 THEN NULL ELSE ward END,
                    place_admin_level = CASE WHEN ? = 3 THEN NULL ELSE place_admin_level END,
                    place_name_raw = CASE WHEN ? = 3 THEN NULL ELSE place_name_raw END,
                    place_candidates_json = CASE WHEN ? = 3 THEN NULL ELSE place_candidates_json END,
                    deaths = CASE WHEN ? = 3 THEN NULL ELSE deaths END,
                    missing = CASE WHEN ? = 3 THEN NULL ELSE missing END,
                    injured = CASE WHEN ? = 3 THEN NULL ELSE injured END,
                    trigger = CASE WHEN ? = 3 THEN NULL ELSE trigger END,
                    conf_class = CASE
                        WHEN ? IS NULL THEN conf_class
                        WHEN ? = 3 THEN MAX(COALESCE(conf_class, 0.0), 0.95)
                        ELSE MAX(COALESCE(conf_class, 0.0), 0.8)
                    END,
                    conf_date = CASE WHEN ? = 3 THEN 0.0 ELSE conf_date END,
                    conf_district = CASE WHEN ? = 3 THEN 0.0 ELSE conf_district END,
                    conf_place = CASE WHEN ? = 3 THEN 0.0 ELSE conf_place END,
                    conf_fatalities = CASE WHEN ? = 3 THEN 0.0 ELSE conf_fatalities END,
                    conf_trigger = CASE WHEN ? = 3 THEN 0.0 ELSE conf_trigger END
                WHERE url = ?
                """,
                (
                    decision.specificity_ok,
                    decision.specificity_reason,
                    decision.specificity_score,
                    decision.updated_class,
                    decision.updated_class,
                    decision.updated_class,
                    decision.updated_class,
                    decision.updated_class,
                    decision.updated_class,
                    decision.updated_class,
                    decision.updated_class,
                    decision.updated_class,
                    decision.updated_class,
                    decision.updated_class,
                    decision.updated_class,
                    decision.updated_class,
                    decision.updated_class,
                    decision.updated_class,
                    decision.updated_class,
                    decision.updated_class,
                    decision.updated_class,
                    decision.updated_class,
                    decision.updated_class,
                    decision.updated_class,
                    row.url,
                ),
            )
            reason_counts[decision.specificity_reason] += 1
            ok_counts[decision.specificity_ok] += 1
        connection.commit()

    LOGGER.info('Event specificity decisions: kept=%s downgraded=%s', ok_counts.get(1, 0), ok_counts.get(0, 0))
    for reason, count in sorted(reason_counts.items()):
        LOGGER.info('event_specificity reason=%s count=%s', reason, count)
    return len(rows)


def decide_specificity(
    row: SpecificityRow,
    study_start: date,
    study_end: date,
    extra_exclude_terms: Sequence[str] = (),
) -> SpecificityDecision:
    """Score whether an extracted row is specific enough to represent a concrete event."""

    title = _normalize_specificity_title(row.source, row.title)
    text = _trim_specificity_text(row.source, row.text or '')
    combined = f'{title}\n{text}'.strip()
    combined_cf = combined.casefold()

    has_location_anchor = bool(row.district or row.municipality)
    has_valid_date = _is_date_in_window(row.event_date_ad, study_start, study_end)
    has_incident_verb = _has_incident_verb_signal(combined)
    has_casualty_signal = _has_casualty_signal(row, combined_cf)
    has_damage_only = _has_damage_only_signal(combined_cf)
    has_roundup = _has_roundup_signal(combined_cf)
    has_risk_only = _has_risk_signal(combined_cf)
    has_followup = _has_followup_signal(combined_cf)
    has_context_only = _has_context_only_signal(combined_cf)
    has_non_event_purpose = (
        NON_EVENT_PURPOSE_PATTERN.search(f'{title}\n{text[:700]}') is not None
        or (
            GOVERNMENT_ATTENTION_PATTERN.search(title) is not None
            and TITLE_HAZARD_PATTERN.search(title) is None
        )
    )
    primary_incident_text = f'{title}\n{text[:350]}'
    unrelated_primary_incident = (
        PRIMARY_NON_LANDSLIDE_INCIDENT_PATTERN.search(title) is not None
        and LANDSLIDE_CAUSED_INCIDENT_PATTERN.search(primary_incident_text) is None
    )
    has_out_of_country = _has_out_of_country_signal(row, combined_cf)
    has_metaphor = _has_metaphor_signal(combined_cf, extra_exclude_terms)
    has_relative_date_phrase = bool(DATE_PHRASE_PATTERN.search(combined) or NP_DATE_PHRASE_PATTERN.search(combined))
    title_cf = title.casefold()
    title_event_signal = _has_title_event_signal(title_cf)
    granularity = classify_event_granularity(title, text)
    article_role = classify_article_role(title, text)
    direct_event_title = _has_direct_event_title(title_cf)
    if has_roundup and direct_event_title and has_location_anchor and (has_valid_date or has_relative_date_phrase or has_casualty_signal):
        if not REGIONAL_BREAKDOWN_PATTERN.search(combined_cf) and not NATIONWIDE_ROUNDUP_PATTERN.search(combined_cf) and 'separate incident' not in combined_cf and ROUNDUP_CONNECTOR_PATTERN.search(combined_cf) is None:
            has_roundup = False
    if has_risk_only and has_location_anchor and (has_valid_date or has_relative_date_phrase) and (
        has_casualty_signal
        or direct_event_title
        or CONFIRMED_IMPACT_PATTERN.search(combined) is not None
    ):
        has_risk_only = False

    concrete_followup = (
        has_followup
        and granularity == GRANULARITY_SINGLE
        and title_event_signal
        and has_location_anchor
        and (has_valid_date or has_relative_date_phrase)
        and (has_incident_verb or has_casualty_signal or direct_event_title)
        and not (
            (has_context_only and article_role != ROLE_FOLLOW_UP)
            or has_out_of_country
            or has_metaphor
            or has_risk_only
        )
    )

    score = 0.0
    if has_location_anchor:
        score += 0.4
    if has_valid_date:
        score += 0.3
    elif has_relative_date_phrase and row.published_date_ad and _is_date_in_window(row.published_date_ad, study_start, study_end):
        score += 0.15
    if has_incident_verb:
        score += 0.3
    if has_casualty_signal:
        score += 0.2
    if has_roundup:
        score -= 0.6
    if has_risk_only:
        score -= 0.6
    if has_followup:
        score -= 0.5
    if has_context_only:
        score -= 0.7
    if has_out_of_country:
        score -= 0.7
    if has_metaphor:
        score -= 0.7
    score = max(0.0, min(1.0, round(score, 3)))

    strong_signal_present = has_location_anchor or has_valid_date or has_incident_verb or has_casualty_signal
    hard_negative = (
        has_roundup
        or has_risk_only
        or (has_followup and not concrete_followup)
        or has_context_only
        or has_out_of_country
        or has_metaphor
        or granularity in {GRANULARITY_MULTI, GRANULARITY_ROUNDUP}
    )

    if not title_event_signal and not has_incident_verb and not has_casualty_signal:
        if has_damage_only:
            return SpecificityDecision(0, 'damage_only', score, _downgraded_class(row.event_class, 'damage_only'))
        if not strong_signal_present:
            return SpecificityDecision(0, 'no_location_signal', score, _downgraded_class(row.event_class, 'no_location_signal'))
        return SpecificityDecision(0, 'context_only', score, _downgraded_class(row.event_class, 'context_only'))
    if has_out_of_country:
        return SpecificityDecision(0, 'out_of_country', score, _downgraded_class(row.event_class, 'out_of_country'))
    if has_metaphor:
        return SpecificityDecision(0, 'metaphor', score, _downgraded_class(row.event_class, 'metaphor'))
    if has_non_event_purpose or unrelated_primary_incident:
        return SpecificityDecision(0, 'context_only', score, _downgraded_class(row.event_class, 'context_only'))
    if (
        has_context_only
        and not has_casualty_signal
        and not concrete_followup
        and not direct_event_title
    ):
        return SpecificityDecision(0, 'context_only', score, _downgraded_class(row.event_class, 'context_only'))
    if has_risk_only:
        return SpecificityDecision(0, 'risk_only', score, _downgraded_class(row.event_class, 'risk_only'))
    if has_roundup or granularity == GRANULARITY_ROUNDUP:
        nationwide_roundup = (
            not has_location_anchor
            or NATIONWIDE_ROUNDUP_PATTERN.search(combined_cf) is not None
            or REGIONAL_BREAKDOWN_PATTERN.search(combined_cf) is not None
            or 'across the country' in combined_cf
            or 'various districts' in combined_cf
        )
        reason = 'context_only' if nationwide_roundup else 'roundup'
        return SpecificityDecision(0, reason, score, _downgraded_class(row.event_class, reason))
    if granularity == GRANULARITY_MULTI:
        return SpecificityDecision(0, 'multi_event', score, _downgraded_class(row.event_class, 'multi_event'))
    if has_followup and not concrete_followup:
        return SpecificityDecision(0, 'followup', score, _downgraded_class(row.event_class, 'followup'))
    if concrete_followup:
        reason = 'event_specific_followup' if article_role == ROLE_FOLLOW_UP else 'event_specific'
        return SpecificityDecision(1, reason, max(score, 0.6), None)
    if has_damage_only and not (has_location_anchor or has_valid_date or has_incident_verb or has_casualty_signal):
        return SpecificityDecision(0, 'damage_only', score, _downgraded_class(row.event_class, 'damage_only'))
    if not strong_signal_present:
        if (
            granularity == GRANULARITY_SINGLE
            and title_event_signal
            and direct_event_title
        ):
            return SpecificityDecision(1, 'event_specific_title', 0.6, None)
        return SpecificityDecision(0, 'no_location_signal', score, _downgraded_class(row.event_class, 'no_location_signal'))
    if score >= 0.6 and not hard_negative:
        return SpecificityDecision(1, 'event_specific', score, None)
    if (
        granularity == GRANULARITY_SINGLE
        and title_event_signal
        and (direct_event_title or has_incident_verb)
    ):
        return SpecificityDecision(1, 'event_specific_title', max(score, 0.6), None)
    return SpecificityDecision(0, 'insufficient_signal', score, _downgraded_class(row.event_class, 'insufficient_signal'))


def _downgraded_class(current_class: int | None, reason: str) -> int | None:
    if current_class is None:
        return 3 if reason in {'out_of_country', 'risk_only', 'metaphor', 'context_only'} else 2
    target = 3 if reason in {'out_of_country', 'risk_only', 'metaphor', 'context_only'} else 2
    return max(int(current_class), target)


def _specificity_rows(database_path: Path) -> Iterable[SpecificityRow]:
    with connect_sqlite(database_path) as connection:
        rows = connection.execute(
            """
            SELECT e.url,
                   e.source,
                   e.title,
                   COALESCE(r.text, '') AS text,
                   r.published_date_ad,
                   COALESCE(l.route_lang, e.route_lang, 'en') AS route_lang,
                   COALESCE(l.mixed_flag, e.mixed_flag, 0) AS mixed_flag,
                   COALESCE(l.devanagari_ratio, 0.0) AS devanagari_ratio,
                   e.class,
                   e.event_date_ad,
                   e.district,
                   e.municipality,
                   e.deaths,
                   e.missing,
                   e.injured
            FROM article_events e
            LEFT JOIN raw_articles r ON r.url = e.url
            LEFT JOIN article_lang l ON l.url = e.url
            ORDER BY e.url ASC
            """
        ).fetchall()
    for row in rows:
        yield SpecificityRow(
            url=str(row['url']),
            source=str(row['source']),
            title=row['title'],
            text=str(row['text'] or ''),
            published_date_ad=row['published_date_ad'],
            route_lang=str(row['route_lang'] or 'en'),
            mixed_flag=bool(row['mixed_flag']),
            devanagari_ratio=float(row['devanagari_ratio'] or 0.0),
            event_class=int(row['class']) if row['class'] is not None else None,
            event_date_ad=row['event_date_ad'],
            district=row['district'],
            municipality=row['municipality'],
            deaths=int(row['deaths']) if row['deaths'] is not None else None,
            missing=int(row['missing']) if row['missing'] is not None else None,
            injured=int(row['injured']) if row['injured'] is not None else None,
        )


def _normalize_specificity_title(source: str, title: str | None) -> str:
    if not title:
        return ''
    if source == 'myrepublica':
        title = re.sub(r'\s*-\s*myRepublica\s*-\s*The New York Times Partner.*$', '', title, flags=re.IGNORECASE)
    if source == 'ratopati':
        title = re.sub(r'\s*\|\s*Nepal\'s first 24-hour updated news portal.*$', '', title, flags=re.IGNORECASE)
    return title.strip()



def _trim_specificity_text(source: str, text: str) -> str:
    if not text:
        return ''
    trimmed = text
    if source == 'myrepublica':
        lead_match = re.search(
            r'(?:By\s+[A-Z][A-Za-z.\s-]+\s+)?(?:[A-Z][A-Z.-]+(?:\s+[A-Z][A-Z.-]+)*|[A-Z][a-z.-]+(?:\s+[A-Z][a-z.-]+)*),\s+'
            r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}:',
            text,
        )
        if lead_match is not None and lead_match.start() >= 40:
            trimmed = text[lead_match.start():]
    return trimmed[:1800]


def _has_incident_verb_signal(text: str) -> bool:
    return INCIDENT_NEAR_PATTERN.search(text) is not None


def _has_casualty_signal(row: SpecificityRow, text_casefold: str) -> bool:
    if any(value is not None and int(value) > 0 for value in (row.deaths, row.missing, row.injured)):
        return True
    return any(pattern.casefold() in text_casefold for pattern in RESCUE_PATTERNS)


def _has_roundup_signal(text_casefold: str) -> bool:
    if any(pattern.casefold() in text_casefold for pattern in ROUNDUP_PATTERNS):
        return True
    if NP_COUNT_REACHED_PATTERN.search(text_casefold) is not None or NP_PERIOD_SUMMARY_PATTERN.search(text_casefold) is not None:
        return True
    if MULTI_DISTRICT_PATTERN.search(text_casefold) is not None or NATIONWIDE_ROUNDUP_PATTERN.search(text_casefold) is not None:
        return True
    if 'in a separate incident' in text_casefold or 'separate incidents of landslides' in text_casefold:
        return True
    if ROUNDUP_CONNECTOR_PATTERN.search(text_casefold) is not None:
        return True
    return False


def _has_risk_signal(text_casefold: str) -> bool:
    if ' at risk ' in f' {text_casefold} ' and ('landslide' in text_casefold or 'पहिरो' in text_casefold):
        if CONFIRMED_IMPACT_PATTERN.search(text_casefold) is not None:
            return False
    risk_hit = any(pattern.casefold() in text_casefold for pattern in RISK_PATTERNS)
    if risk_hit and CONFIRMED_IMPACT_PATTERN.search(text_casefold) is not None:
        return False
    return risk_hit


def _has_followup_signal(text_casefold: str) -> bool:
    if any(pattern.casefold() in text_casefold for pattern in FOLLOWUP_PATTERNS):
        return True
    if NP_LONG_RUNNING_DISRUPTION_PATTERN.search(text_casefold) is not None:
        return True
    return FOLLOWUP_DELAY_PATTERN.search(text_casefold) is not None


def _has_context_only_signal(text_casefold: str) -> bool:
    return any(pattern.casefold() in text_casefold for pattern in CONTEXT_ONLY_PATTERNS)


def _has_damage_only_signal(text_casefold: str) -> bool:
    return any(pattern.casefold() in text_casefold for pattern in DAMAGE_ONLY_PATTERNS)


def _has_metaphor_signal(text_casefold: str, extra_terms: Sequence[str] = ()) -> bool:
    """Detect political/financial metaphor use of 'landslide'.

    Three sources, in order of trust:

    1. ``extra_terms`` -- ``keywords.exclude`` from config.yaml. This is the
       supported place for a project to add its own exclusions. It existed
       before this change but was read by no code, which is why the hardcoded
       list below was doing all the work, badly.
    2. ``METAPHOR_PATTERNS`` -- unambiguous literal phrases.
    3. ``METAPHOR_ELECTORAL_PATTERN`` -- context-requiring regexes, which
       replaced the bare fragments that were destroying real events.
    """

    if any(term.casefold() in text_casefold for term in extra_terms):
        return True
    if any(pattern.casefold() in text_casefold for pattern in METAPHOR_PATTERNS):
        return True
    return METAPHOR_ELECTORAL_PATTERN.search(text_casefold) is not None


def metaphor_exclude_terms(config: AppConfig) -> tuple[str, ...]:
    """Read ``keywords.exclude`` from config, flattened across languages.

    Previously dead config: the block exists in config.yaml and config.example.yaml
    ('political landslide', 'stock slide', 'राजनीतिक पहिरो') and was never read.
    """

    raw = (config.raw.get('keywords') or {}).get('exclude') or {}
    terms: list[str] = []
    if isinstance(raw, dict):
        for language in sorted(raw):
            values = raw[language] or []
            terms.extend(str(value) for value in values if str(value).strip())
    elif isinstance(raw, list):
        terms.extend(str(value) for value in raw if str(value).strip())
    return tuple(dict.fromkeys(terms))


def _has_title_event_signal(title_casefold: str) -> bool:
    if not title_casefold:
        return False
    return any(
        term in title_casefold
        for term in (
            'landslide', 'landslides', 'mudslide', 'mudslides', 'rockfall',
            'पहिरो', 'भूस्खलन', 'हिमपहिरो', 'ढिस्को', 'पुरिए', 'पुरिँदा',
            'बेपत्ता', 'वेपत्ता', 'मृत्यु',
            'अवरुद्ध', 'अवरूद्ध', 'blocked', 'obstructed', 'buried', 'killed', 'missing', 'injured',
        )
    )


def _has_direct_event_title(title_casefold: str) -> bool:
    if not title_casefold:
        return False
    if DIRECT_CASUALTY_TITLE_PATTERN.search(title_casefold) is not None:
        return True
    has_landslide = any(term in title_casefold for term in ('landslide', 'landslides', 'mudslide', 'mudslides', 'पहिरो', 'भूस्खलन'))
    has_direct_impact = any(
        term in title_casefold
        for term in (
            'block', 'blocks', 'blocked', 'obstruct', 'obstructs', 'obstructed',
            'disrupt', 'disrupts', 'disrupted', 'shut', 'closed', 'buried',
            'marred', 'inspection',
            'death toll', 'dead', 'missing', 'identified', 'recovered',
            'अवरुद्ध', 'अवरूद्ध', 'मृत्यु', 'मृतकको संख्या', 'बेपत्ता',
            'वेपत्ता', 'पहिचान', 'शव फेला', 'पुरिए', 'बन्द', 'निरीक्षण',
        )
    )
    return has_landslide and has_direct_impact


def _has_out_of_country_signal(row: SpecificityRow, text_casefold: str) -> bool:
    title = _normalize_specificity_title(row.source, row.title).casefold()
    if _contains_foreign_term(title) or FOREIGN_HAZARD_DEMONYM_PATTERN.search(title):
        return True
    lead = text_casefold[:800]
    foreign_hit = _contains_foreign_term(lead)
    if not foreign_hit:
        return False
    if FOREIGN_EVENT_NP_PATTERN.search(lead):
        return True
    # A resolved Nepal administrative location outweighs a foreign background
    # mention (Indian victims, a Chinese contractor, a border crossing). An
    # explicitly foreign title was already rejected above.
    if row.district or row.municipality:
        return False
    nepal_signal = NEPAL_SIGNAL_PATTERN.search(lead) is not None or any(marker in row.url.casefold() for marker in URL_NEPAL_MARKERS)
    return not nepal_signal


def _contains_foreign_term(text_casefold: str) -> bool:
    """Match foreign place names without treating demonyms as locations.

    The old substring test matched ``india`` inside ``Indian nationals`` and
    consequently discarded Nepal landslides whose victims or rescue teams were
    Indian. Latin terms therefore require alphabetic boundaries; Devanagari
    country names retain substring matching so case suffixes such as ``भारतमा``
    continue to identify genuinely foreign reports.
    """

    for term in FOREIGN_TERMS:
        folded = term.casefold()
        if folded.isascii():
            if re.search(rf'(?<![a-z]){re.escape(folded)}(?![a-z])', text_casefold):
                return True
        elif re.search(rf'{re.escape(folded)}(?!ीय)', text_casefold):
            return True
    return False


def _is_date_in_window(value: str | None, study_start: date, study_end: date) -> bool:
    if not value:
        return False
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return False
    return study_start <= parsed <= study_end
