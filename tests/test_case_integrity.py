"""Integrity invariants over the district-days the analysis actually uses.

The pipeline's quality machinery all measures one thing -- whether an article is
a real Nepali landslide report -- and none of it asks whether the record that
article produced is internally coherent. These checks ask that instead, and the
tests below pin two properties that matter more than the checks' coverage.

First, that the impossible cases really are treated as impossible. An event
dated after its own publication is not unlikely, it is incoherent, and a release
carrying one is wrong however few there are.

Second, that the judgement-dependent checks do not fire on ordinary landslide
reports. Both of them started out doing exactly that: the forecast check flagged
real events that ended "20 houses at risk", and the anthropogenic check flagged
every article that mentioned an excavator -- which is the machine that *clears*
a landslide. Those regressions are pinned individually, because a noisy check
gets ignored and an ignored check protects nothing.
"""

from __future__ import annotations

from datetime import date

import pytest

from landslide_inventory.validation import case_integrity as ci


# ---------------------------------------------------------------------------
# The impossible cases
# ---------------------------------------------------------------------------


def test_an_event_cannot_postdate_the_article_reporting_it():
    """The cheapest true invariant available, and it was never run. The rows it
    catches are disproportionately not landslide reports at all -- a date pulled
    from unrelated text has no reason to fall before publication."""

    finding = ci.check_event_precedes_publication(
        "Kathmandu", "2018-09-09", "2018-08-19", url="http://x", title="t"
    )
    assert finding is not None
    assert finding.check == "event_after_publication"
    assert finding.severity == ci.SEVERITY_VIOLATION
    assert "21 days after publication" in finding.detail


def test_an_event_on_its_publication_day_is_fine():
    """Same-day reporting is the norm for these outlets, not an anomaly."""

    assert ci.check_event_precedes_publication("Kaski", "2020-07-10", "2020-07-10") is None
    assert ci.check_event_precedes_publication("Kaski", "2020-07-09", "2020-07-10") is None


def test_a_missing_publication_date_is_not_an_impossibility():
    """Absence of evidence. Flagging it would turn a coverage gap into a defect."""

    assert ci.check_event_precedes_publication("Kaski", "2020-07-10", None) is None
    assert ci.check_event_precedes_publication("Kaski", "2020-07-10", "") is None


def test_an_event_outside_the_study_period_is_a_violation():
    start, end = date(2015, 1, 1), date(2026, 8, 14)
    assert ci.check_within_study_period("Kaski", "2020-07-10", start, end) is None
    late = ci.check_within_study_period("Kaski", "2027-01-01", start, end)
    assert late is not None and late.severity == ci.SEVERITY_VIOLATION


def test_an_unparseable_date_is_a_violation_not_a_silent_skip():
    start, end = date(2015, 1, 1), date(2026, 8, 14)
    finding = ci.check_within_study_period("Kaski", "not-a-date", start, end)
    assert finding is not None
    assert finding.check == "unparseable_event_date"


# ---------------------------------------------------------------------------
# The article is not an event report
# ---------------------------------------------------------------------------


def test_an_article_with_no_landslide_term_is_flagged():
    """Not a judgement about severity or scope -- the word is simply absent.
    The v0.6.0 case set contained a party convention, a gold-smuggling story and
    an essay on the Bikram Sambat calendar."""

    finding = ci.check_article_mentions_the_hazard(
        "Chitwan", "2021-10-21", "एमाले महाधिवेशन चितवनमा हुने, बादलको संयोजकत्वमा"
    )
    assert finding is not None
    assert finding.check == "no_hazard_term_in_article"


@pytest.mark.parametrize(
    "text",
    [
        "चितवनमा पहिरो खस्दा एक जनाको मृत्यु",
        "Landslide buries house in Sindhupalchok",
        "A mudslide blocked the highway",
    ],
)
def test_a_real_landslide_report_is_not_flagged_for_the_missing_term(text):
    assert ci.check_article_mentions_the_hazard("X", "2020-07-10", text) is None


def test_a_rainfall_forecast_is_flagged():
    """The most damaging single failure available to this analysis. A day taken
    from "heavy rain expected, high caution advised" is selected *on rainfall*
    and enters the case arm carrying high antecedent rainfall by construction --
    contamination in the exact direction of the study's own finding."""

    finding = ci.check_not_a_forecast(
        "Kathmandu",
        "2023-06-19",
        "आजको मौसम : मेघगर्जनसहित वर्षा हुनसक्ने, बाढी/पहिरोबाट जोगिन आग्रह",
    )
    assert finding is not None
    assert finding.check == "forecast_not_occurrence"


def test_a_real_event_with_a_risk_clause_is_not_called_a_forecast():
    """A keyword-only version of this check flagged 34 case-days, most of them
    genuine landslides that happened to end with a warning about what might
    happen next. Forecast language alone is not enough; the occurrence
    predicate has to be absent too."""

    assert (
        ci.check_not_a_forecast(
            "Gorkha",
            "2019-08-21",
            "Landslide sweeps away a house, 29 houses at risk and more damage is expected",
        )
        is None
    )


def test_both_spellings_of_the_obstruction_verb_count_as_an_occurrence():
    """अवरुद्ध and अवरूद्ध both occur in the corpus. Listing only one flagged a
    real road-blocking landslide as a forecast."""

    for spelling in ("अवरुद्ध", "अवरूद्ध"):
        assert ci.reports_an_occurrence(f"पहिरोले सडक {spelling} भयो")


# ---------------------------------------------------------------------------
# Burials by placed earth, and the false positives that version one produced
# ---------------------------------------------------------------------------


def test_a_burial_by_placed_earth_is_flagged():
    """Terai and valley districts have no landslide terrain. What they have is
    spoil heaps, plotting sites and sand piles, and those burials were entering
    the case set as `unknown`-trigger landslides."""

    finding = ci.check_anthropogenic_trigger_was_caught(
        "Dang", "2018-06-29", "दाङमा माटोको ढिस्कोले पुरिएर महिलाको मृत्यु", "unknown"
    )
    assert finding is not None
    assert finding.check == "anthropogenic_trigger_missed"


def test_an_extraction_site_is_flagged():
    finding = ci.check_anthropogenic_trigger_was_caught(
        "Kathmandu",
        "2021-06-02",
        "नैकापमा जग्गा प्लटिङ गरेको ठाउँमा पर्खाल लगाउँदा पुरेर दुई जनाको मृत्यु",
        "unknown",
    )
    assert finding is not None


@pytest.mark.parametrize(
    "text",
    [
        # An excavator is what CLEARS a landslide, not what causes one. Version
        # one of this check flagged 41 case-days on this word alone.
        "सुक्खा पहिरोबाट कर्णाली राजमार्ग अवरुद्ध, एक्स्काभेटर परिचालन",
        # A wall is what a landslide destroys.
        "पहिरो खस्दा कालीपुलका आठ घर र पर्खाल क्षति",
        # Gravel and sand are what the debris is made of.
        "पहिरोले बगाएको गिट्टी र बालुवाले सडक पुरियो",
        # Digging here is the rescue.
        "पहिरोमा पुरिएकालाई खन्दै उद्धार गरियो",
    ],
)
def test_the_machinery_of_clearing_a_landslide_is_not_evidence_of_causing_one(text):
    assert ci.check_anthropogenic_trigger_was_caught("X", "2020-07-10", text, "unknown") is None


def test_an_already_excluded_trigger_is_not_re_flagged():
    """The analysis already drops anthropogenic and earthquake events. Flagging
    them again would double-count a problem the pipeline handled correctly."""

    text = "माटोको ढिस्कोले पुरिएर एक जनाको मृत्यु"
    assert ci.check_anthropogenic_trigger_was_caught("X", "2020-07-10", text, "anthropogenic") is None
    assert ci.check_anthropogenic_trigger_was_caught("X", "2020-07-10", text, "earthquake") is None
    assert ci.check_anthropogenic_trigger_was_caught("X", "2020-07-10", text, "unknown") is not None


# ---------------------------------------------------------------------------
# What is NOT a defect
# ---------------------------------------------------------------------------


def test_several_events_on_one_district_day_are_informational_not_a_defect():
    """The analysis unit is the district-day, so two separate landslides in one
    district on one night *should* collapse to one case-day. 1,999 canonical
    events over 1,508 case-days is the expected shape, and calling it
    contamination would have put a quarter of the case set on the excludable
    list for no reason."""

    rows = [("Kaski", "2020-07-10", f"event_{i}") for i in range(5)]
    findings = ci.check_case_days_are_unique(rows)
    assert len(findings) == 1
    assert findings[0].severity == ci.SEVERITY_INFORMATIONAL
    assert findings[0].check == "many_events_one_case_day"


def test_an_ordinary_pair_of_events_is_not_reported_at_all():
    rows = [("Kaski", "2020-07-10", "a"), ("Kaski", "2020-07-10", "b")]
    assert ci.check_case_days_are_unique(rows) == []


def test_informational_findings_are_excluded_from_the_excludable_set():
    """The sensitivity analysis removes case-days. Removing ones that are not
    defects would misreport the robustness of the threshold."""

    report = ci.IntegrityReport(
        case_days=10,
        findings=[
            ci.IntegrityFinding("A", "2020-01-01", "x", ci.SEVERITY_VIOLATION, ""),
            ci.IntegrityFinding("B", "2020-01-02", "y", ci.SEVERITY_CONTAMINATION, ""),
            ci.IntegrityFinding("C", "2020-01-03", "z", ci.SEVERITY_INFORMATIONAL, ""),
        ],
    )
    excludable = report.flagged_case_days(ci.SEVERITY_VIOLATION) | report.flagged_case_days(
        ci.SEVERITY_CONTAMINATION
    )
    assert ("C", "2020-01-03") not in excludable
    assert len(excludable) == 2


def test_the_report_counts_findings_by_check():
    report = ci.IntegrityReport(
        case_days=3,
        findings=[
            ci.IntegrityFinding("A", "2020-01-01", "alpha", ci.SEVERITY_VIOLATION, ""),
            ci.IntegrityFinding("B", "2020-01-02", "alpha", ci.SEVERITY_VIOLATION, ""),
            ci.IntegrityFinding("C", "2020-01-03", "beta", ci.SEVERITY_CONTAMINATION, ""),
        ],
    )
    assert report.by_check() == {"alpha": 2, "beta": 1}
    assert len(report.violations) == 2
