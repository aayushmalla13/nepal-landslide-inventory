"""Study-area relevance filtering for extracted articles."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from ..config import AppConfig
from ..db import connect_sqlite, initialize_sqlite
from ..utils import utc_now_iso
from .decisions import ensure_decisions_table, record_decision, snapshot_fields

NEPAL_KEYWORDS = ('nepal', 'नेपाल', 'नेपाली')
URL_NEPAL_MARKERS = ('/nepal', '/national', '/social')
GLOBAL_ROUNDUP_PATTERNS = (
    'around the world', 'global', 'worldwide', 'across the world',
    'across asia', 'partner, latest news of nepal in english', 'new york times partner',
)
FOREIGN_TERMS = (
    'india', 'china', 'turkey', 'indonesia', 'south korea', 'sierra leone', 'california', 'tibet',
    'pakistan', 'afghanistan', 'japan', 'philippines', 'myanmar', 'taiwan', 'thailand', 'bangladesh',
    'russia', 'ukraine', 'italy', 'france', 'germany', 'united states', 'america', 'canada', 'iran',
    'iraq', 'israel', 'gaza', 'syria', 'yemen', 'mexico', 'brazil', 'peru', 'chile', 'argentina',
    'australia', 'new zealand', 'south africa', 'spain', 'uk', 'england', 'scotland', 'ireland', 'hong kong', 'uttarakhand', 'sikkim', 'delhi',
    'भारत', 'चीन', 'पाकिस्तान', 'टर्की', 'इन्डोनेसिया', 'बंगलादेश',
    'अफगानिस्तान', 'म्यानमार', 'जापान', 'फिलिपिन्स', 'थाइल्यान्ड',
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
COUNTRY_LIST_PATTERN = re.compile(r'\b(?:India|China|Turkey|Indonesia|Pakistan|Japan|Bangladesh|California|Sierra Leone)(?:\s*,\s*(?:India|China|Turkey|Indonesia|Pakistan|Japan|Bangladesh|California|Sierra Leone)){2,}', re.IGNORECASE)
MYREPUBLICA_TITLE_SUFFIX_PATTERN = re.compile(
    r'\s*-\s*myRepublica\s*-\s*The New York Times Partner.*$',
    re.IGNORECASE,
)
MYREPUBLICA_LEAD_PATTERN = re.compile(
    r'(?:By\s+[A-Z][A-Za-z.\s-]+?\s+)?'
    r'(?:[A-Z][A-Z.-]+(?:\s+[A-Z][A-Z.-]+)*|[A-Z][a-z.-]+(?:\s+[A-Z][a-z.-]+)*)'
    r',\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec|'
    r'January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}:',
)
MYREPUBLICA_DATELINE_PATTERN = re.compile(
    r'\b(?:[A-Z][A-Z.-]+(?:\s+[A-Z][A-Z.-]+)*|[A-Z][a-z.-]+(?:\s+[A-Z][a-z.-]+){0,3}),\s+'
    r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec|'
    r'January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}:',
)
MYREPUBLICA_SCOPE_TEXT_LIMIT = 900
FOREIGN_TERM_PATTERNS = tuple(
    re.compile(
        (
            rf'(?<![A-Za-z]){re.escape(term)}(?![A-Za-z])'
            if term.isascii()
            else rf'{re.escape(term)}(?!ीय)'
        ),
        re.IGNORECASE,
    )
    for term in FOREIGN_TERMS
)
FOREIGN_HAZARD_DEMONYM_PATTERN = re.compile(
    r'\b(?:indian|chinese|pakistani|indonesian|bangladeshi|afghan|'
    r'japanese|filipino|myanmarese)\s+(?:landslide|mudslide|avalanche|flood)',
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ScopeDecision:
    in_nepal: int
    scope_reason: str
    scope_score: float


@dataclass(frozen=True)
class ScopeRow:
    url: str
    source: str
    title: str | None
    text: str
    route_lang: str
    devanagari_ratio: float
    district: str | None
    municipality: str | None


def decide_scope(row: ScopeRow, devanagari_threshold: float) -> ScopeDecision:
    """Decide whether an extracted article is in scope for Nepal."""

    title = _normalize_scope_title(row.source, row.title)
    text = _trim_scope_text(row.source, row.text or '')
    combined = f'{title}\n{text}'.casefold()
    url_lower = row.url.casefold()

    if _is_global_roundup(combined):
        return ScopeDecision(0, 'global_roundup', 0.98)
    if _is_out_of_country(combined) and (
        not (row.district or row.municipality)
        or _is_out_of_country(title.casefold())
    ):
        return ScopeDecision(0, 'out_of_country', 0.96)
    if row.district:
        return ScopeDecision(1, 'district_match', 1.0)
    if row.municipality:
        return ScopeDecision(1, 'municipality_match', 0.96)
    if any(keyword in combined for keyword in (term.casefold() for term in NEPAL_KEYWORDS)):
        return ScopeDecision(1, 'nepal_keyword', 0.9)
    if any(marker in url_lower for marker in URL_NEPAL_MARKERS):
        return ScopeDecision(1, 'nepal_keyword', 0.75)
    if row.route_lang == 'np' and row.devanagari_ratio >= max(0.6, devanagari_threshold):
        return ScopeDecision(1, 'np_language_high', 0.7)
    return ScopeDecision(0, 'no_location_signal', 0.55)


def run_filter_scope_stage(config: AppConfig) -> int:
    """Populate article_scope and mark out-of-scope article_events rows."""

    initialize_sqlite(config.sqlite_path)
    thresholds = dict(config.raw['language_detection'])
    devanagari_threshold = float(thresholds['devanagari_threshold'])
    rows = list(_scope_rows(config.sqlite_path))
    decided_at = utc_now_iso()
    with connect_sqlite(config.sqlite_path) as connection:
        ensure_decisions_table(connection)
        for row in rows:
            decision = decide_scope(row, devanagari_threshold)
            # Keep an immutable decision-time snapshot while preserving the
            # extractor's evidence fields for reproducible reruns and audits.
            record_decision(
                connection,
                url=row.url,
                stage='filter_scope',
                decision=decision.in_nepal,
                reason=decision.scope_reason,
                score=decision.scope_score,
                updated_class=3 if decision.in_nepal == 0 else None,
                preserved=snapshot_fields(connection, row.url),
                decided_at=decided_at,
            )
            connection.execute(
                """
                INSERT INTO article_scope (url, in_nepal, scope_reason, scope_score, decided_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(url) DO UPDATE SET
                    in_nepal = excluded.in_nepal,
                    scope_reason = excluded.scope_reason,
                    scope_score = excluded.scope_score,
                    decided_at = excluded.decided_at
                """,
                (row.url, decision.in_nepal, decision.scope_reason, decision.scope_score, decided_at),
            )
            updated_class = 3 if decision.in_nepal == 0 else None
            connection.execute(
                """
                UPDATE article_events
                SET in_nepal = ?,
                    scope_reason = ?,
                    class = COALESCE(?, class),
                    event_class = COALESCE(?, event_class),
                    conf_class = CASE WHEN ? IS NULL THEN conf_class ELSE MAX(COALESCE(conf_class, 0.0), 0.95) END
                WHERE url = ?
                """,
                (
                    decision.in_nepal,
                    decision.scope_reason,
                    updated_class,
                    updated_class,
                    updated_class,
                    row.url,
                ),
            )
        connection.commit()
    return len(rows)


def _scope_rows(database_path: Path) -> Iterable[ScopeRow]:
    with connect_sqlite(database_path) as connection:
        rows = connection.execute(
            """
            SELECT e.url, e.source, e.title, COALESCE(r.text, '') AS text,
                   COALESCE(e.route_lang, l.route_lang, 'en') AS route_lang,
                   COALESCE(l.devanagari_ratio, 0.0) AS devanagari_ratio,
                   e.district, e.municipality
            FROM article_events e
            LEFT JOIN raw_articles r ON r.url = e.url
            LEFT JOIN article_lang l ON l.url = e.url
            ORDER BY e.url ASC
            """
        ).fetchall()
    for row in rows:
        yield ScopeRow(
            url=str(row['url']),
            source=str(row['source']),
            title=row['title'],
            text=str(row['text'] or ''),
            route_lang=str(row['route_lang'] or 'en'),
            devanagari_ratio=float(row['devanagari_ratio'] or 0.0),
            district=row['district'],
            municipality=row['municipality'],
        )


def _normalize_scope_title(source: str, title: str | None) -> str:
    if not title:
        return ''
    if source == 'myrepublica':
        title = MYREPUBLICA_TITLE_SUFFIX_PATTERN.sub('', title)
    return title.strip()



def _trim_scope_text(source: str, text: str) -> str:
    if not text:
        return ''
    trimmed = text
    if source == 'myrepublica':
        lead_match = MYREPUBLICA_LEAD_PATTERN.search(text)
        if lead_match is not None and lead_match.start() >= 40:
            trimmed = text[lead_match.start():]
        return trimmed[:MYREPUBLICA_SCOPE_TEXT_LIMIT]
    return trimmed[:1800]



def _is_global_roundup(text: str) -> bool:
    lead = text[:600]
    if any(pattern in lead for pattern in GLOBAL_ROUNDUP_PATTERNS):
        return True
    return COUNTRY_LIST_PATTERN.search(lead) is not None


def _is_out_of_country(text: str) -> bool:
    lead = text[:800]
    primary = re.split(r'(?<=[.!?])\s+', lead, maxsplit=1)[0]
    foreign_hits = sum(1 for pattern in FOREIGN_TERM_PATTERNS if pattern.search(primary))
    nepal_hits = sum(1 for term in (keyword.casefold() for keyword in NEPAL_KEYWORDS) if term in primary)
    demonym_hazard = FOREIGN_HAZARD_DEMONYM_PATTERN.search(primary) is not None
    return (foreign_hits >= 1 or demonym_hazard) and nepal_hits == 0
