"""The gate that decides whether multi-event extraction is worth building.

The granularity work established that 29.3% of kept class-1 articles report
more than one failure, and framed that as an under-count. The tempting
inference is that per-failure extraction would recover 29% more events. It
would not, and these tests pin the three reasons why.

First, the analysis unit is the **district-day**. Several failures in one
district on one night collapse to the district-day the inventory already has.
The audit of all 47 human-labelled ``multi`` articles found 32 of them yield
nothing at all on that unit.

Second, the districts an article mentions are mostly not failure locations.
They are datelines, the home districts of the dead, the far end of a blocked
road, where stranded vehicles were headed, or the publisher's own address. A
naive "emit every district mentioned" rule would inject roughly three false
case-days for every real one.

Third, the yield estimate rests on a stratified sample in which the largest
stratum is represented by four articles. A point estimate hides that; the
decision has to be made on the interval.
"""

from __future__ import annotations

import csv
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

csv.field_size_limit(50_000_000)


def load(name: str):
    sys.path.insert(0, str(ROOT / "src"))
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def scorer():
    return load("score_multievent_yield")


@pytest.fixture(scope="module")
def audit() -> dict[str, dict[str, str]]:
    path = ROOT / "data" / "outputs" / "multievent_yield_audit.csv"
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return {row["row_id"]: row for row in csv.DictReader(handle)}


@pytest.fixture(scope="module")
def labels() -> dict[str, dict[str, str]]:
    path = ROOT / "data" / "outputs" / "granularity_class1_COMPLETED.csv"
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return {row["row_id"]: row for row in csv.DictReader(handle)}


# ---------------------------------------------------------------------------
# The audit must cover exactly the multi articles, and nothing else
# ---------------------------------------------------------------------------


def test_the_audit_covers_every_human_labelled_multi_article(audit, labels):
    """A yield estimate built on a partial read of the multi articles would be
    biased towards whichever ones happened to look interesting."""

    multi = {
        row_id for row_id, row in labels.items() if row["event_granularity_true"] == "multi"
    }
    assert multi, "the class-1 pack should contain multi articles"
    assert set(audit) == multi


def test_the_audit_does_not_reach_beyond_the_multi_articles(audit, labels):
    """Auditing `single` rows for extra districts would be fitting the
    extractor on articles the annotator already said report one event."""

    for row_id in audit:
        assert labels[row_id]["event_granularity_true"] == "multi"


# ---------------------------------------------------------------------------
# The district-day unit is what collapses the yield
# ---------------------------------------------------------------------------


def test_most_multi_articles_yield_no_additional_district_day(audit):
    """This is the finding the whole gate turns on. If multi-event articles
    mostly spanned districts or days, the 29% under-count would translate into
    a 29% recovery. They mostly do not: they report several failures in one
    district on one night."""

    barren = [
        row_id
        for row_id, row in audit.items()
        if int(row["extra_districtdays_strong"]) + int(row["extra_districtdays_weak"]) == 0
    ]
    assert len(barren) / len(audit) > 0.6


def test_recovery_is_temporal_as_well_as_spatial(audit):
    """A design that only splits by district would miss a real part of the
    yield: articles that walk through the same corridor on three named days."""

    kinds = {row["recovery_kind"] for row in audit.values()}
    assert "temporal" in kinds
    assert "spatial" in kinds


# ---------------------------------------------------------------------------
# The traps are why the extractor must be precision-first
# ---------------------------------------------------------------------------


def test_the_audit_records_why_a_district_is_mentioned_without_a_failure(audit):
    """These categories are the extractor's specification. Losing them would
    reduce the next step to guessing at which mentions are real."""

    traps = {row["trap_kind"] for row in audit.values() if row["trap_kind"]}
    for required in (
        "victim_home_district",
        "dateline",
        "road_destination",
        "stranded_destination",
        "retrospective_bulletin",
    ):
        assert required in traps, f"the trap taxonomy lost {required}"


def test_a_naive_extractor_would_be_mostly_wrong(scorer, tmp_path):
    """Pinned because it is the reason this project needs a careful extractor
    rather than a loop over place candidates. Recomputed from the audit so the
    claim cannot drift away from the evidence."""

    import json
    import subprocess

    output = tmp_path / "yield.json"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "score_multievent_yield.py"),
            "--output",
            str(output),
        ],
        cwd=ROOT,
        env={"PYTHONPATH": "src", "PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    ceiling = payload["naive_precision_ceiling"]["strong_plus_weak"]
    assert ceiling < 0.5, "a naive extractor would be right more often than the audit found"
    # And the gate's own verdict, recomputed rather than restated.
    assert payload["verdict"] == "material"
    assert payload["verdict_robust_to_sampling_error"] is True


# ---------------------------------------------------------------------------
# The decision must be made on the interval, not the point estimate
# ---------------------------------------------------------------------------


def test_the_bootstrap_resamples_within_stratum(scorer):
    """Resampling across strata would mix a weight-71 article with a weight-4
    one and silently narrow the interval."""

    per_article = {"big": [0, 0, 0, 0], "small": [1, 1, 1, 1]}
    weights = {"big": 100.0, "small": 1.0}
    lower, upper = scorer.stratified_bootstrap(per_article, weights, 2000, 1)
    # `small` contributes exactly 4 in every resample; `big` contributes 0.
    assert lower == pytest.approx(4.0)
    assert upper == pytest.approx(4.0)


def test_a_stratum_of_zeros_cannot_widen_upwards(scorer):
    """An honest reading of the interval. The largest stratum contributed four
    articles that all yielded nothing, so the bootstrap can only ever resample
    zeros from it. The interval is therefore conditional on that stratum truly
    yielding nothing, which four observations cannot establish -- so the lower
    bound is the conservative end and the true yield may be higher."""

    per_article = {"unsampled": [0, 0, 0, 0]}
    weights = {"unsampled": 71.52}
    lower, upper = scorer.stratified_bootstrap(per_article, weights, 1000, 7)
    assert lower == 0.0
    assert upper == 0.0


def test_the_bootstrap_is_deterministic(scorer):
    per_article = {"a": [0, 1, 2, 0, 1], "b": [1, 0, 0]}
    weights = {"a": 10.0, "b": 5.0}
    first = scorer.stratified_bootstrap(per_article, weights, 500, 99)
    second = scorer.stratified_bootstrap(per_article, weights, 500, 99)
    assert first == second


def test_collisions_discount_the_gross_yield(scorer):
    """Three of the fifteen recovered pairs already exist as case-days from
    other articles. Reporting the gross figure would overstate the gain."""

    assert 0 < scorer.COLLISION_RATE < 1


def test_the_extractor_stays_silent_on_articles_reporting_one_event(labels):
    """The strongest evidence available that the rules do not fire spuriously.

    The development audit covers only `multi` articles, so nothing in it says
    what the extractor does on an ordinary one -- while a corpus run applies it
    to every kept class-1 article, roughly 70% of which the annotator called
    `single`. A `single` article reports one failure by definition, so any
    record emitted from one is wrong.

    This caught a real regression: before the same-district municipality gate,
    3 of 43 `single` articles produced records, two of which were the article's
    own landslide re-dated from a weekday. Extrapolated to the corpus that was
    roughly a hundred fabricated district-days.
    """

    import csv as csv_module

    from landslide_inventory.unify.multievent import extract_secondary_failures

    pack_path = ROOT / "data" / "outputs" / "granularity_class1_reading_pack.csv"
    articles_path = ROOT / "data" / "outputs" / "article_events.csv"
    with pack_path.open("r", encoding="utf-8-sig", newline="") as handle:
        pack = {row["row_id"]: row for row in csv_module.DictReader(handle)}
    with articles_path.open("r", encoding="utf-8-sig", newline="") as handle:
        articles = {row["url"]: row for row in csv_module.DictReader(handle)}

    offenders: list[tuple[str, str, str]] = []
    checked = 0
    for row_id, label in labels.items():
        if label["event_granularity_true"] not in ("single", "not_applicable"):
            continue
        entry = pack.get(row_id)
        article = articles.get(label["url"])
        if entry is None or article is None:
            continue
        checked += 1
        for result in extract_secondary_failures(
            entry.get("title"),
            entry.get("article_text") or "",
            lang=entry.get("route_lang") or article.get("route_lang") or "en",
            published_date_ad=article.get("published_date_ad"),
            primary_district=article.get("district"),
            primary_date=article.get("event_date_ad"),
            primary_municipality=article.get("municipality") or None,
        ):
            offenders.append((row_id, result.district, result.event_date_ad))

    assert checked >= 40, "the negative control lost its articles"
    assert offenders == [], f"records emitted from single-event articles: {offenders}"


def test_the_materiality_threshold_is_fixed_in_the_module(scorer):
    """Stated before the numbers were computed, so the verdict cannot be
    reverse-engineered from whichever yield happened to come out."""

    assert scorer.MATERIALITY_THRESHOLD == 0.05
