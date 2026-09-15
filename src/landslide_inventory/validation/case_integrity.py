"""Invariant checks over the district-days the rainfall analysis actually uses.

Why this module exists
----------------------
The pipeline has extensive quality machinery -- scope filters, specificity
filters, an adjudicator, a locked test set -- and all of it measures the same
thing: whether an article is a real Nepali landslide report. None of it asks
whether the *record* the article produced is internally coherent.

Some of those questions have answers that are simply impossible rather than
merely unlikely, and are three lines of code to detect:

* an event dated **after** the article reporting it was published;
* a case-day whose article contains no landslide term anywhere;
* a case-day built from a **rainfall forecast**.

That last one is the reason this module exists rather than being a nice-to-have.
The analysis asks whether antecedent rainfall discriminates landslide days from
non-landslide days. A case-day taken from *"heavy rain expected from Saun 4,
high caution advised"* is a day selected **because rainfall was forecast**, with
no landslide attached. It enters the case arm guaranteed to carry high
antecedent rainfall, which is the one form of contamination that biases the
result in the direction of its own finding. Two such days were found in
v0.6.0's case set by hand, and nothing in the pipeline would have caught them.

Design
------
Checks report; they never delete. Each flagged case-day carries its reason and
its evidence, and `scripts/run_case_integrity_audit.py` measures separately what
excluding them does to the threshold, against the frozen baseline. A check that
quietly dropped rows would make the inventory depend on the auditor's judgement
with no record of it.

Severity is split deliberately:

* ``violation`` -- logically impossible. A release carrying one is wrong,
  regardless of how few there are.
* ``contamination`` -- the article is not an event report. Needs judgement, so
  these are reported for review rather than treated as automatic failures.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
import re
from typing import Iterable

SEVERITY_VIOLATION = 'violation'
SEVERITY_CONTAMINATION = 'contamination'
SEVERITY_INFORMATIONAL = 'informational'

# Human excavation and earthworks. The pipeline already classifies an
# `anthropogenic` trigger and the analysis already drops those events -- the
# machinery is there and works. What it lacks is Nepali vocabulary: the
# `road_construction` trigger list carries three terms (सडक विस्तार, डोजर,
# निर्माण) and none of them is the word these reports actually use.
#
# A first attempt listed every earthworks word -- excavator, digging, wall,
# gravel, sand -- and flagged 109 case-days, most of them wrongly. An excavator
# is what *clears* a landslide; a wall is what a landslide *destroys*; gravel
# and sand are what the debris is made of. Those words are evidence of a
# landslide being dealt with, not of one being caused.
#
# What actually separates the two is a burial by **placed** earth: a spoil
# heap, a sand pile, a plotting site. Those reports say "माटोको ढिस्कोले
# पुरिएर" -- buried by a mound of soil -- and they describe a pile that someone
# put there.
NP_PLACED_EARTH_PATTERNS = (
    'माटोको ढिस्को', 'बालुवाको ढिस्को', 'ढिस्कोले पुरि', 'ढिस्कोमा पुरि',
    'ढिस्काले पुरि', 'ढिस्कोले पुर',
)
EN_PLACED_EARTH_PATTERNS = (
    'mound of soil', 'pile of soil', 'pile of sand', 'heap of soil', 'soil pile',
)

# Site types that are unambiguous on their own: a landslide report has no
# reason to mention a crusher plant or a land-plotting site unless that is
# where the ground gave way.
NP_EXTRACTION_SITE_CUES = ('प्लटिङ', 'प्लटिङ्ग', 'क्रसर', 'उत्खनन')
EN_EXTRACTION_SITE_CUES = ('land plotting', 'crusher', 'quarry', 'sand mining')

NP_HAZARD_TERMS = ('पहिरो', 'पहिरा', 'भूस्खलन', 'लेदो', 'पहिराले')
EN_HAZARD_TERMS = (
    'landslide', 'landslip', 'mudslide', 'debris flow', 'rockfall', 'rock fall',
    'mudflow', 'slope failure',
)

# Forecast and advisory language. On its own this flags far too much -- a real
# landslide report routinely ends "20 more houses at risk" -- so a row is only
# called a forecast when it carries this language *and* no occurrence predicate
# anywhere. An earlier keyword-only pass flagged 34 case-days of which most were
# genuine events with a risk clause attached.
NP_FORECAST_CUES = (
    'पूर्वानुमान', 'सम्भावना', 'हुनसक्ने', 'हुन सक्ने', 'चेतावनी', 'सतर्कता',
    'सावधानी अपनाउन', 'आगामी', 'अपेक्षा',
)
EN_FORECAST_CUES = (
    'forecast', 'warning issued', 'alert issued', 'advisory', 'expected to',
    'likely to', 'predicted', 'may occur', 'could occur', 'to be closed',
    'to open', 'set to',
)

NP_OCCURRENCE_TERMS = (
    'खस', 'गएको', 'गयो', 'जाँदा', 'पुरि', 'पुरे', 'पुर्‍यो', 'बगा', 'बगे', 'भत्कि',
    'मृत्यु', 'ज्यान', 'घाइते', 'विस्थापित', 'क्षति', 'बाँचे', 'उद्धार', 'बेपत्ता',
    # Both spellings occur in the corpus and only one was listed at first, which
    # flagged a real road-blocking landslide as a forecast.
    'अवरुद्ध', 'अवरूद्ध',
)
EN_OCCURRENCE_TERMS = (
    'occurred', 'buried', 'swept', 'hit', 'struck', 'blocked', 'obstructed',
    'killed', 'died', 'dead', 'damaged', 'destroyed', 'displaced', 'injured',
    'took place', 'caved', 'claimed', 'washed away',
)


@dataclass(frozen=True)
class IntegrityFinding:
    """One case-day that fails one invariant."""

    district: str
    event_date_ad: str
    check: str
    severity: str
    detail: str
    url: str = ''
    title: str = ''

    @property
    def case_day(self) -> tuple[str, str]:
        return (self.district, self.event_date_ad)


@dataclass
class IntegrityReport:
    """All findings, with the case-day totals they are measured against."""

    case_days: int
    findings: list[IntegrityFinding] = field(default_factory=list)

    def by_check(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for finding in self.findings:
            counts[finding.check] = counts.get(finding.check, 0) + 1
        return dict(sorted(counts.items()))

    def flagged_case_days(self, severity: str | None = None) -> set[tuple[str, str]]:
        return {
            finding.case_day
            for finding in self.findings
            if severity is None or finding.severity == severity
        }

    @property
    def violations(self) -> list[IntegrityFinding]:
        return [f for f in self.findings if f.severity == SEVERITY_VIOLATION]


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def contains_hazard_term(text: str) -> bool:
    if not text:
        return False
    lowered = text.casefold()
    return any(term in text for term in NP_HAZARD_TERMS) or any(
        term in lowered for term in EN_HAZARD_TERMS
    )


def reports_an_occurrence(text: str) -> bool:
    if not text:
        return False
    lowered = text.casefold()
    return any(term in text for term in NP_OCCURRENCE_TERMS) or any(
        term in lowered for term in EN_OCCURRENCE_TERMS
    )


def looks_like_forecast(text: str) -> bool:
    if not text:
        return False
    lowered = text.casefold()
    return any(cue in text for cue in NP_FORECAST_CUES) or any(
        cue in lowered for cue in EN_FORECAST_CUES
    )


def check_event_precedes_publication(
    district: str,
    event_date_ad: str,
    published_date_ad: str | None,
    url: str = '',
    title: str = '',
) -> IntegrityFinding | None:
    """An event cannot happen after the article reporting it was published.

    This is the cheapest true invariant the project has, and it was never run.
    It is also a useful tracer: the rows it catches are disproportionately
    articles that are not landslide reports at all, because a date extracted
    from unrelated text has no reason to fall before publication.
    """

    event = parse_date(event_date_ad)
    published = parse_date(published_date_ad)
    if event is None or published is None or event <= published:
        return None
    return IntegrityFinding(
        district=district,
        event_date_ad=event_date_ad,
        check='event_after_publication',
        severity=SEVERITY_VIOLATION,
        detail=f'event {event.isoformat()} is {(event - published).days} days after publication {published.isoformat()}',
        url=url,
        title=title,
    )


def check_within_study_period(
    district: str,
    event_date_ad: str,
    study_start: date,
    study_end: date,
    url: str = '',
    title: str = '',
) -> IntegrityFinding | None:
    event = parse_date(event_date_ad)
    if event is None:
        return IntegrityFinding(
            district=district,
            event_date_ad=event_date_ad or '',
            check='unparseable_event_date',
            severity=SEVERITY_VIOLATION,
            detail=f'cannot parse {event_date_ad!r}',
            url=url,
            title=title,
        )
    if study_start <= event <= study_end:
        return None
    return IntegrityFinding(
        district=district,
        event_date_ad=event_date_ad,
        check='event_outside_study_period',
        severity=SEVERITY_VIOLATION,
        detail=f'{event.isoformat()} is outside {study_start.isoformat()}..{study_end.isoformat()}',
        url=url,
        title=title,
    )


def check_article_mentions_the_hazard(
    district: str,
    event_date_ad: str,
    text: str,
    url: str = '',
    title: str = '',
) -> IntegrityFinding | None:
    """A case-day whose source article never says 'landslide'.

    Not a judgement call about severity or scope -- the word is simply absent.
    Whatever produced the record, it was not a landslide report.
    """

    if contains_hazard_term(text):
        return None
    return IntegrityFinding(
        district=district,
        event_date_ad=event_date_ad,
        check='no_hazard_term_in_article',
        severity=SEVERITY_CONTAMINATION,
        detail='no landslide-family term anywhere in title or body',
        url=url,
        title=title,
    )


def check_not_a_forecast(
    district: str,
    event_date_ad: str,
    text: str,
    url: str = '',
    title: str = '',
) -> IntegrityFinding | None:
    """A case-day built from a forecast rather than an occurrence.

    The most damaging single failure available to this analysis, because such a
    day is selected *on rainfall* and enters the case arm carrying high
    antecedent rainfall by construction.

    Requires forecast language AND no occurrence predicate anywhere: a real
    report that ends "20 more houses at risk" must not be flagged.
    """

    if not looks_like_forecast(text):
        return None
    if reports_an_occurrence(text):
        return None
    return IntegrityFinding(
        district=district,
        event_date_ad=event_date_ad,
        check='forecast_not_occurrence',
        severity=SEVERITY_CONTAMINATION,
        detail='forecast or advisory language with no occurrence predicate',
        url=url,
        title=title,
    )


def check_anthropogenic_trigger_was_caught(
    district: str,
    event_date_ad: str,
    text: str,
    recorded_trigger: str | None,
    url: str = '',
    title: str = '',
) -> IntegrityFinding | None:
    """A burial during earthworks that the trigger classifier did not catch.

    The analysis removes ``anthropogenic`` and ``earthquake`` events, so a
    quarry collapse or a wall-building burial is meant to be excluded already.
    This flags the ones that reached the case set as ``unknown``.

    It matters more than the count suggests. These are burials by *placed*
    earth -- a spoil heap, a plotting site, a sand pile -- whose timing is set
    by a machine rather than by a hillslope. They carry no physical relationship
    to antecedent rainfall, and several sit in flat Terai and valley districts
    that have no landslide terrain at all, so they enter the case arm as days
    whose rainfall is drawn from an unrelated distribution.

    Fires only on a burial by *placed* earth, or on a site type that a landslide
    report has no other reason to mention. Never on the machinery and materials
    that appear in the aftermath of a real landslide, which is what an earlier,
    looser version of this check mistook for evidence.
    """

    if (recorded_trigger or '').strip() in {'anthropogenic', 'earthquake'}:
        return None
    if not text:
        return None
    lowered = text.casefold()
    hits = [cue for cue in NP_PLACED_EARTH_PATTERNS if cue in text]
    hits += [cue for cue in EN_PLACED_EARTH_PATTERNS if cue in lowered]
    hits += [cue for cue in NP_EXTRACTION_SITE_CUES if cue in text]
    hits += [cue for cue in EN_EXTRACTION_SITE_CUES if cue in lowered]
    if not hits:
        return None
    return IntegrityFinding(
        district=district,
        event_date_ad=event_date_ad,
        check='anthropogenic_trigger_missed',
        severity=SEVERITY_CONTAMINATION,
        detail=(
            f'placed-earth or extraction-site cues {hits[:3]} but trigger '
            f'recorded as {recorded_trigger or "unset"!r}'
        ),
        url=url,
        title=title,
    )


def check_case_days_are_unique(
    rows: Iterable[tuple[str, str, str]],
    report_threshold: int = 4,
) -> list[IntegrityFinding]:
    """Several canonical events sharing one district-day.

    Not a defect. The analysis unit is the district-day, so two genuinely
    separate landslides in one district on one night *should* collapse to one
    case-day, and 1,999 canonical events over 1,508 case-days is the expected
    shape rather than evidence of a dedup failure.

    It is reported for two narrower reasons: any per-event count in the paper
    has to be stated against the right denominator, and a district-day carrying
    an implausible pile-up of separate events is worth a look, since that is
    what a real dedup failure would look like. Hence the threshold -- only the
    extremes are listed, and at informational severity.
    """

    seen: dict[tuple[str, str], list[str]] = {}
    for district, event_date_ad, event_id in rows:
        seen.setdefault((district, event_date_ad), []).append(event_id)
    findings: list[IntegrityFinding] = []
    for (district, event_date_ad), event_ids in sorted(seen.items()):
        if len(event_ids) >= report_threshold:
            findings.append(
                IntegrityFinding(
                    district=district,
                    event_date_ad=event_date_ad,
                    check='many_events_one_case_day',
                    severity=SEVERITY_INFORMATIONAL,
                    detail=(
                        f'{len(event_ids)} canonical events share this district-day: '
                        f'{sorted(event_ids)[:4]}'
                    ),
                )
            )
    return findings
