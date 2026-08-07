"""Tests for cross-inventory agreement (review §6).

Three of these guard correctness bugs in the implementation this replaces:
the hazard filter failed open, BS dates parsed ~57 years off, and matching was
forced 1:1. The rest verify the statistics behave on data with known answers.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from landslide_inventory.bipad.agreement import (
    BikramSambatDateError,
    InventoryEvent,
    aggregate_agreement,
    capture_recapture,
    chance_corrected_agreement,
    collapse_to_incidents,
    full_agreement_report,
    is_landslide_hazard,
    match_inventories,
    match_tier,
    parse_ad_date,
)

TERMS = ('landslide', 'पहिरो', 'भूस्खलन')


def ev(i, district, day, muni=None, deaths=None, source='news'):
    return InventoryEvent(event_id=f'{source}-{i}', district=district,
                          event_date=date(2024, 7, day), municipality=muni,
                          deaths=deaths, source=source)


# --- correctness bugs from the old implementation ----------------------------

def test_hazard_filter_fails_closed() -> None:
    """The old code returned True for a missing hazard value.

    If the export's hazard column was not among the expected names, every flood,
    fire and epidemic counted as a landslide — and would have produced a
    plausible recall figure.
    """

    assert is_landslide_hazard(None, TERMS) is False
    assert is_landslide_hazard('', TERMS) is False
    assert is_landslide_hazard('   ', TERMS) is False
    assert is_landslide_hazard('Flood', TERMS) is False
    assert is_landslide_hazard('Landslide', TERMS) is True
    assert is_landslide_hazard('पहिरो', TERMS) is True


def test_bikram_sambat_dates_hard_fail() -> None:
    """2081-03-25 is a valid-looking AD string and ~57 years wrong."""

    with pytest.raises(BikramSambatDateError):
        parse_ad_date('2081-03-25')
    with pytest.raises(BikramSambatDateError):
        parse_ad_date('2075/06/12')
    assert parse_ad_date('2024-07-16') == date(2024, 7, 16)


def test_ambiguous_date_orders_are_refused_not_guessed() -> None:
    """'05-07-2024' is 5 July or 7 May. The old code silently picked one."""

    assert parse_ad_date('05-07-2024') is None
    assert parse_ad_date('') is None
    assert parse_ad_date(None) is None


def test_matching_is_many_to_many() -> None:
    """BIPAD may hold several ward rows for one news event; 1:1 discards that."""

    news = [ev(1, 'Rasuwa', 16, muni='Uttargaya')]
    bipad = [ev(i, 'Rasuwa', 16, muni='Uttargaya', source='bipad') for i in range(3)]
    matches, summary = match_inventories(news, bipad)
    assert len(matches) == 3
    assert summary['multiplicity_max_per_news'] == 3


# --- Layer 1: harmonisation --------------------------------------------------

def test_per_household_rows_collapse_to_one_incident() -> None:
    bipad = [ev(i, 'Rasuwa', 16, muni='Uttargaya', deaths=1, source='bipad') for i in range(5)]
    collapsed, summary = collapse_to_incidents(bipad)
    assert len(collapsed) == 1
    assert collapsed[0].deaths == 5, 'casualties should sum across the cluster'
    assert summary['collapse_ratio'] == 5.0
    assert summary['largest_cluster'] == 5


def test_distinct_districts_do_not_collapse() -> None:
    bipad = [ev(1, 'Rasuwa', 16, source='bipad'), ev(2, 'Dhading', 16, source='bipad')]
    collapsed, _ = collapse_to_incidents(bipad)
    assert len(collapsed) == 2


# --- Layer 2: tiers ----------------------------------------------------------

def test_tier_a_needs_municipality_and_one_day() -> None:
    a = ev(1, 'Rasuwa', 16, muni='Uttargaya')
    b = ev(2, 'Rasuwa', 17, muni='Uttargaya', source='bipad')
    assert match_tier(a, b) == 'A'


def test_tier_b_uses_casualty_agreement() -> None:
    a = ev(1, 'Rasuwa', 16, deaths=3)
    b = ev(2, 'Rasuwa', 18, deaths=3, source='bipad')
    assert match_tier(a, b) == 'B'


def test_tier_c_is_district_and_a_week() -> None:
    assert match_tier(ev(1, 'Rasuwa', 16), ev(2, 'Rasuwa', 22, source='bipad')) == 'C'


def test_different_districts_never_match() -> None:
    assert match_tier(ev(1, 'Rasuwa', 16), ev(2, 'Dhading', 16, source='bipad')) is None


def test_beyond_the_window_does_not_match() -> None:
    assert match_tier(ev(1, 'Rasuwa', 1), ev(2, 'Rasuwa', 30, source='bipad')) is None


# --- Layer 3: the null -------------------------------------------------------

def test_chance_correction_is_near_zero_when_dates_are_unrelated() -> None:
    """The whole point: a district-level ±7-day match happens by coincidence.

    Here every district has events on scattered dates with no correspondence,
    so observed overlap should be indistinguishable from the permuted null.
    """

    news = [InventoryEvent(f'n{i}', 'Rasuwa', date(2024, 7, 1) + timedelta(days=i * 3))
            for i in range(10)]
    bipad = [InventoryEvent(f'b{i}', 'Rasuwa', date(2024, 7, 2) + timedelta(days=i * 3),
                            source='bipad') for i in range(10)]
    result = chance_corrected_agreement(news, bipad, permutations=60)
    assert abs(result['chance_corrected']) < 0.25, (
        'unrelated inventories that overlap only by coincidence must show near-zero '
        f'chance-corrected agreement, got {result}'
    )


def test_chance_correction_is_reproducible() -> None:
    news = [InventoryEvent(f'n{i}', 'Rasuwa', date(2024, 7, 1 + i)) for i in range(5)]
    bipad = [InventoryEvent(f'b{i}', 'Rasuwa', date(2024, 7, 1 + i), source='bipad')
             for i in range(5)]
    first = chance_corrected_agreement(news, bipad, permutations=30, seed=7)
    second = chance_corrected_agreement(news, bipad, permutations=30, seed=7)
    assert first == second


# --- Layer 4: capture-recapture ----------------------------------------------

def test_capture_recapture_recovers_a_known_population() -> None:
    """200 events, each inventory sees 100, 50 shared -> population ~200."""

    result = capture_recapture(news_total=100, bipad_total=100, matched=50)
    assert 190 <= result['estimated_population'] <= 210
    assert result['news_completeness'] == pytest.approx(0.5, abs=0.05)


def test_capture_recapture_states_its_assumption() -> None:
    result = capture_recapture(100, 100, 50)
    assert 'media-triggered' in result['assumption']
    assert 'lower bound' in result['assumption']


def test_capture_recapture_undefined_without_overlap() -> None:
    assert capture_recapture(100, 100, 0)['estimate'] is None


# --- Layer 5: aggregate ------------------------------------------------------

def test_perfectly_correlated_district_years() -> None:
    news, bipad = [], []
    for n, district in enumerate(['Rasuwa', 'Dhading', 'Kaski', 'Myagdi'], start=1):
        for i in range(n):
            news.append(InventoryEvent(f'n{district}{i}', district, date(2024, 7, 1)))
            bipad.append(InventoryEvent(f'b{district}{i}', district, date(2024, 7, 1),
                                        source='bipad'))
    result = aggregate_agreement(news, bipad, 'district_year')
    assert result['spearman_rho'] == pytest.approx(1.0)
    assert result['bland_altman_mean_difference'] == pytest.approx(0.0)


# --- end to end --------------------------------------------------------------

def test_full_report_never_reports_precision_or_recall() -> None:
    """The framing is the point (§6.1a)."""

    news = [InventoryEvent(f'n{i}', 'Rasuwa', date(2024, 7, 1 + i)) for i in range(6)]
    bipad = [InventoryEvent(f'b{i}', 'Rasuwa', date(2024, 7, 1 + i), source='bipad')
             for i in range(6)]
    report = full_agreement_report(news, bipad, permutations=20)
    flat = str(report).casefold()
    assert 'precision' not in flat.replace('precision and recall against bipad are', '')
    assert set(report) >= {
        'layer1_harmonisation', 'layer2_overlap', 'layer3_chance_corrected',
        'layer4_capture_recapture', 'layer5_aggregate', 'layer6_unmatched_samples',
    }
    assert 'not ground truth' in report['framing_note']


# --- loading -----------------------------------------------------------------

def test_loader_excludes_and_counts_every_rejection(tmp_path) -> None:
    """The denominator of a completeness statistic depends on these choices."""

    import csv as _csv
    from landslide_inventory.bipad.agreement import load_bipad_rows

    path = tmp_path / 'bipad.csv'
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = _csv.DictWriter(handle, fieldnames=['id', 'hazard', 'date', 'district', 'deaths'])
        writer.writeheader()
        writer.writerow({'id': '1', 'hazard': 'Landslide', 'date': '2024-07-16',
                         'district': 'Rasuwa', 'deaths': '3'})       # kept
        writer.writerow({'id': '2', 'hazard': 'Flood', 'date': '2024-07-16',
                         'district': 'Rasuwa', 'deaths': '1'})       # wrong hazard
        writer.writerow({'id': '3', 'hazard': '', 'date': '2024-07-16',
                         'district': 'Rasuwa', 'deaths': '1'})       # fails CLOSED
        writer.writerow({'id': '4', 'hazard': 'Landslide', 'date': '2081-03-25',
                         'district': 'Rasuwa', 'deaths': '2'})       # Bikram Sambat
        writer.writerow({'id': '5', 'hazard': 'Landslide', 'date': '2009-07-16',
                         'district': 'Rasuwa', 'deaths': '2'})       # before window
        writer.writerow({'id': '6', 'hazard': 'Landslide', 'date': '2024-07-16',
                         'district': '', 'deaths': '2'})             # no district

    events, counts = load_bipad_rows(
        path, TERMS, date(2015, 1, 1), date(2026, 12, 31),
        hazard_columns=['hazard'], date_columns=['date'], district_columns=['district'])

    assert counts['kept'] == 1 and len(events) == 1
    assert counts['not_landslide'] == 2, 'flood plus the blank hazard (fails closed)'
    assert counts['bs_date'] == 1
    assert counts['out_of_window'] == 1
    assert counts['no_district'] == 1
    assert events[0].deaths == 3
