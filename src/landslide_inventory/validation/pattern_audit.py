"""Substring-collision audit for the ``event_specificity`` pattern lists.

Why this module exists
----------------------
``event_specificity.py`` excludes articles using ~200 bare substrings. Bare
substrings collide. The known case is ``'by landslide'`` in
``METAPHOR_PATTERNS``, which is meant to catch *"won by landslide"* but also
matches *"buried by landslide"* and *"swept away by landslide"* -- destroying
172 real events (review section 2.1).

There is no reason to believe that is the only one, and no mechanism in the repo
that could have found it. This module is that mechanism.

What it measures
----------------
For every pattern in every exclusion list, over the full corpus:

``matched``
    articles whose text contains the pattern.

``dropped_via_reason``
    of those, how many the pipeline actually dropped with the reason that this
    pattern's list produces. A pattern can match a lot and drop nothing (it was
    overridden), which is useful to know.

``suspect_false_negatives``
    of those dropped, how many look like a **real Nepal landslide event**. Three
    conditions, all required:

    1. *direct incident evidence* -- a casualty verb next to a landslide noun
       (``DIRECT_CASUALTY_TITLE_PATTERN``) or an incident verb near one
       (``INCIDENT_NEAR_PATTERN``);
    2. *a Nepal anchor* -- a gazetteer district name appears in the text;
    3. *no foreign country named in the title*.

    Conditions 2 and 3 are not decoration. A first cut of this audit used only
    condition 1 and flagged ``'india'`` and ``'china'`` as top offenders with
    ~0.8 collision rates. Inspection showed those exclusions were **correct** --
    "15 bodies found after landslide buries scores in China" has abundant
    incident evidence and is exactly what the foreign filter is for. Without the
    Nepal anchor the metric mistakes a working filter for a broken one, which is
    a worse failure than not measuring at all.

``collision_rate``
    ``suspect_false_negatives / dropped_via_reason``. This is the number to sort
    by. A pattern with a high drop count and a high collision rate is actively
    destroying the inventory.

The output is advisory, not automatic: it ranks patterns for human review, it
does not delete them. Deciding that ``'warning'`` is too broad a term to exclude
on is a judgement about what the inventory is *for*, and belongs to the person
writing the methods section.

A second caveat, learned the same way: a high score does **not** always mean
"substring collision". ``'सञ्चालनमा'`` (FOLLOWUP) scores highly, but inspection
shows its hits are Narayangadh-Muglin road-obstruction articles. Those are a
genuine question about the *event definition* (review section 4.2), not an
accident of matching. The audit tells you where to look; it does not tell you
what you are looking at.

Usage
-----
    python -m landslide_inventory.run --stage pattern_audit
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any, Iterable, Sequence

from ..config import AppConfig
from ..db import connect_sqlite
from ..nlp_en.places import EN_DISTRICT_ALIASES_PATTERN
from ..nlp_np.places import NP_DISTRICT_ALIAS_PATTERN
from ..unify.event_specificity import (
    CONTEXT_ONLY_PATTERNS,
    DAMAGE_ONLY_PATTERNS,
    DIRECT_CASUALTY_TITLE_PATTERN,
    FOLLOWUP_PATTERNS,
    FOREIGN_TERMS,
    INCIDENT_NEAR_PATTERN,
    METAPHOR_PATTERNS,
    RISK_PATTERNS,
    ROUNDUP_PATTERNS,
)
from ..utils import ensure_directory
from .common import iso_now, write_csv

LOGGER = logging.getLogger(__name__)

# Each list, paired with the specificity_reason it produces. A list can produce
# more than one reason (roundup demotes to either 'roundup' or 'context_only'
# depending on whether it looks nationwide), hence the tuple.
PATTERN_LISTS: dict[str, tuple[Sequence[str], tuple[str, ...]]] = {
    'METAPHOR_PATTERNS': (METAPHOR_PATTERNS, ('metaphor',)),
    'ROUNDUP_PATTERNS': (ROUNDUP_PATTERNS, ('roundup', 'context_only')),
    'RISK_PATTERNS': (RISK_PATTERNS, ('risk_only',)),
    'CONTEXT_ONLY_PATTERNS': (CONTEXT_ONLY_PATTERNS, ('context_only',)),
    'FOLLOWUP_PATTERNS': (FOLLOWUP_PATTERNS, ('followup',)),
    'DAMAGE_ONLY_PATTERNS': (DAMAGE_ONLY_PATTERNS, ('damage_only',)),
    'FOREIGN_TERMS': (FOREIGN_TERMS, ('out_of_country',)),
}

REPORT_COLUMNS = [
    'pattern_list', 'pattern', 'pattern_len', 'matched', 'dropped_via_reason',
    'suspect_false_negatives', 'collision_rate', 'severity', 'example_suspect_title',
]

# A pattern shorter than this is a substring-collision risk by construction:
# short fragments appear inside unrelated words and phrases. Flagged separately
# from the empirical measurement because a short pattern that happens not to
# collide in *this* corpus will still collide in the next one.
SHORT_PATTERN_CHARS = 12


# Country names that, when they appear in a *title*, mean the article is very
# likely about a foreign event regardless of what else it contains.
FOREIGN_TITLE_TERMS = tuple(sorted(FOREIGN_TERMS, key=len, reverse=True))


@dataclass(frozen=True)
class CorpusRow:
    url: str
    title: str
    combined_cf: str
    specificity_reason: str | None
    has_direct_evidence: bool
    has_nepal_anchor: bool
    foreign_in_title: bool

    @property
    def looks_like_real_nepal_event(self) -> bool:
        """All three conditions, per the module docstring."""

        return self.has_direct_evidence and self.has_nepal_anchor and not self.foreign_in_title


@dataclass(frozen=True)
class PatternFinding:
    pattern_list: str
    pattern: str
    matched: int
    dropped_via_reason: int
    suspect_false_negatives: int
    example_suspect_title: str

    @property
    def collision_rate(self) -> float:
        if self.dropped_via_reason == 0:
            return 0.0
        return round(self.suspect_false_negatives / self.dropped_via_reason, 4)

    @property
    def severity(self) -> str:
        """Triage label. ``critical`` means: fix before the next pipeline run."""

        if self.suspect_false_negatives >= 50 and self.collision_rate >= 0.5:
            return 'critical'
        if self.suspect_false_negatives >= 20:
            return 'high'
        if self.suspect_false_negatives >= 5:
            return 'medium'
        if len(self.pattern) < SHORT_PATTERN_CHARS and self.dropped_via_reason > 0:
            return 'review_short_pattern'
        return 'ok'


def load_corpus(connection) -> list[CorpusRow]:
    """Load every article with its title, body, and the reason it was dropped."""

    query = """
        SELECT e.url                AS url,
               COALESCE(e.title, '')  AS title,
               COALESCE(r.text, '')   AS text,
               e.specificity_reason   AS specificity_reason
        FROM article_events AS e
        LEFT JOIN raw_articles AS r ON r.url = e.url
        ORDER BY e.url
    """
    rows: list[CorpusRow] = []
    for record in connection.execute(query):
        item = dict(record)
        combined = f"{item['title']}\n{item['text']}"
        title = ' '.join(item['title'].split())[:200]
        title_cf = title.casefold()
        rows.append(
            CorpusRow(
                url=item['url'],
                title=title,
                combined_cf=combined.casefold(),
                specificity_reason=item['specificity_reason'],
                has_direct_evidence=bool(
                    DIRECT_CASUALTY_TITLE_PATTERN.search(combined)
                    or INCIDENT_NEAR_PATTERN.search(combined)
                ),
                # Gazetteer district names, EN and NP. Cannot use
                # article_events.district here: the filter stages NULL it on
                # demotion (review section 2.2), so it is unavailable for
                # exactly the dropped rows this audit cares about.
                has_nepal_anchor=bool(
                    EN_DISTRICT_ALIASES_PATTERN.search(combined)
                    or NP_DISTRICT_ALIAS_PATTERN.search(combined)
                ),
                foreign_in_title=any(term in title_cf for term in FOREIGN_TITLE_TERMS),
            )
        )
    return rows


def audit_pattern(
    pattern: str,
    pattern_list: str,
    reasons: tuple[str, ...],
    corpus: Sequence[CorpusRow],
) -> PatternFinding:
    """Measure one pattern's reach, its kill count, and its collateral damage."""

    needle = pattern.casefold()
    matched = 0
    dropped = 0
    suspects = 0
    example = ''
    for row in corpus:
        if needle not in row.combined_cf:
            continue
        matched += 1
        if row.specificity_reason in reasons:
            dropped += 1
            if row.looks_like_real_nepal_event:
                suspects += 1
                if not example:
                    example = row.title
    return PatternFinding(
        pattern_list=pattern_list,
        pattern=pattern,
        matched=matched,
        dropped_via_reason=dropped,
        suspect_false_negatives=suspects,
        example_suspect_title=example,
    )


def audit_all_patterns(corpus: Sequence[CorpusRow]) -> list[PatternFinding]:
    """Audit every pattern in every list, worst offenders first."""

    findings: list[PatternFinding] = []
    for list_name in sorted(PATTERN_LISTS):
        patterns, reasons = PATTERN_LISTS[list_name]
        for pattern in patterns:
            findings.append(audit_pattern(pattern, list_name, reasons, corpus))
    findings.sort(
        key=lambda f: (-f.suspect_false_negatives, -f.collision_rate, f.pattern_list, f.pattern)
    )
    return findings


def _records(findings: Iterable[PatternFinding]) -> Iterable[dict[str, Any]]:
    for finding in findings:
        yield {
            'pattern_list': finding.pattern_list,
            'pattern': finding.pattern,
            'pattern_len': len(finding.pattern),
            'matched': finding.matched,
            'dropped_via_reason': finding.dropped_via_reason,
            'suspect_false_negatives': finding.suspect_false_negatives,
            'collision_rate': finding.collision_rate,
            'severity': finding.severity,
            'example_suspect_title': finding.example_suspect_title,
        }


def run_pattern_audit_stage(config: AppConfig) -> dict[str, Any]:
    """Write the pattern-collision report and log the critical findings."""

    outputs_dir = config.resolve_path('outputs_dir')
    ensure_directory(outputs_dir)
    report_path = outputs_dir / 'pattern_collision_audit.csv'

    with connect_sqlite(config.sqlite_path) as connection:
        corpus = load_corpus(connection)

    findings = audit_all_patterns(corpus)
    write_csv(report_path, REPORT_COLUMNS, _records(findings))

    critical = [f for f in findings if f.severity in {'critical', 'high'}]
    total_suspects = sum(f.suspect_false_negatives for f in findings)
    LOGGER.info(
        'Pattern audit: %d patterns over %d articles; %d flagged critical/high; '
        '%d suspect exclusions (non-exclusive across patterns)',
        len(findings), len(corpus), len(critical), total_suspects,
    )
    for finding in critical[:15]:
        LOGGER.warning(
            '  %-22s %-30r dropped=%-4d suspect=%-4d rate=%.2f',
            finding.pattern_list, finding.pattern,
            finding.dropped_via_reason, finding.suspect_false_negatives,
            finding.collision_rate,
        )
    return {
        'generated_at': iso_now(),
        'patterns_audited': len(findings),
        'corpus_size': len(corpus),
        'critical_or_high': len(critical),
        'report': str(report_path),
    }
