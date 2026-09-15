"""Dedup once an article can yield several district-days.

Dedup was written when each article produced exactly one event, and it encoded
that assumption in two places that both break silently rather than loudly:
union-find keyed on ``url``, and cluster ``size`` counting records. Neither
raises when an article starts producing three records -- the first quietly
discards two of them, the second quietly reports one article as three
independent corroborating reports.

These tests pin both, plus the rules that keep a recovered record from
overstating what it actually knows.
"""

from __future__ import annotations

import json

import pytest

from landslide_inventory.unify.dedup_stage import (
    EXTRACTION_PRIMARY,
    EXTRACTION_SECONDARY,
    FIRM_DATE_BASES,
    DedupConfig,
    EventRecord,
    build_canonical_event,
    build_cluster_summary,
    choose_representative,
    cluster_events,
    cluster_is_secondary_only,
    secondary_only_cluster_admitted,
)

CONFIG = DedupConfig(
    candidate_window_days=3,
    primary_window_days=1,
    headline_sim_threshold=0.80,
    body_sim_threshold=0.85,
    high_body_sim_threshold=0.93,
    guard_deaths_delta=2,
    prefer_same_municipality=True,
)


def record(
    url,
    district,
    date_ad,
    *,
    basis=EXTRACTION_PRIMARY,
    date_basis=None,
    title="Landslide blocks road",
    body="A landslide blocked the road after heavy rainfall overnight.",
    source="example",
    deaths=None,
    municipality=None,
):
    return EventRecord(
        url=url,
        source=source,
        title=title,
        body_text=body,
        event_date_ad=date_ad,
        district=district,
        province=None,
        municipality=municipality,
        ward=None,
        place_name_raw=None,
        deaths=deaths,
        missing=None,
        injured=None,
        trigger=None,
        route_lang="en",
        event_class=1,
        in_nepal=1,
        conf_class=0.9,
        conf_date=0.9,
        conf_district=0.9,
        conf_place=0.5,
        conf_fatalities=0.0,
        conf_trigger=0.0,
        extraction_basis=basis,
        evidence_sentence=("Landslides also occurred in the district." if basis != EXTRACTION_PRIMARY else None),
        date_basis=date_basis,
    )


# ---------------------------------------------------------------------------
# The URL is no longer the record identity
# ---------------------------------------------------------------------------


def test_one_article_can_contribute_to_several_district_days():
    """The blocker this change exists to remove. Keyed on url, the Kalikot
    record would vanish into the Dailekh cluster and the recovery would be
    silently discarded."""

    events = [
        record("http://a", "Dailekh", "2019-04-06"),
        record("http://a", "Kalikot", "2019-04-06", basis=EXTRACTION_SECONDARY,
               date_basis="weekday"),
    ]
    clusters, _ = cluster_events(events, CONFIG)
    districts = {cluster[0].district for cluster in clusters}
    assert districts == {"Dailekh", "Kalikot"}
    assert sum(len(cluster) for cluster in clusters) == 2


def test_record_key_separates_records_of_one_article():
    left = record("http://a", "Dailekh", "2019-04-06")
    right = record("http://a", "Kalikot", "2019-04-06", basis=EXTRACTION_SECONDARY)
    assert left.record_key != right.record_key
    assert left.url == right.url


def test_two_records_from_one_article_never_merge():
    """Two records from one URL are, by construction, two distinct occasions
    the extractor separated. Their body text is identical, so the similarity
    path would merge them every single time if allowed to try -- undoing the
    separation and inflating the cluster size at once."""

    events = [
        record("http://a", "Dhading", "2022-06-09"),
        record("http://a", "Dhading", "2022-06-10", basis=EXTRACTION_SECONDARY,
               date_basis="weekday"),
    ]
    clusters, _ = cluster_events(events, CONFIG)
    assert len(clusters) == 2


def test_records_from_different_articles_still_merge():
    """The counterpart. Blocking same-article merges must not block genuine
    corroboration between two outlets covering one event."""

    events = [
        record("http://a", "Dhading", "2022-06-09"),
        record("http://b", "Dhading", "2022-06-09", source="other"),
    ]
    clusters, _ = cluster_events(events, CONFIG)
    assert len(clusters) == 1
    assert len(clusters[0]) == 2


# ---------------------------------------------------------------------------
# An article cannot corroborate itself
# ---------------------------------------------------------------------------


def test_cluster_size_counts_articles_not_records():
    """`size` is read downstream as "how many independent reports support this
    event". One article split across district-days must not read as several."""

    cluster = [
        record("http://a", "Dhading", "2022-06-09"),
        record("http://a", "Dhading", "2022-06-09", basis=EXTRACTION_SECONDARY),
    ]
    summary = build_cluster_summary(cluster, "2026-09-12T00:00:00Z", cluster_id="c1")
    assert summary["size"] == 1
    assert summary["record_count"] == 2
    assert summary["secondary_record_count"] == 1


def test_cluster_size_is_unchanged_for_a_primary_only_cluster():
    """The change must be invisible to a run with no recovered records, or it
    would silently alter the frozen baseline it is meant to be compared with."""

    cluster = [
        record("http://a", "Dhading", "2022-06-09"),
        record("http://b", "Dhading", "2022-06-09", source="other"),
    ]
    summary = build_cluster_summary(cluster, "2026-09-12T00:00:00Z", cluster_id="c1")
    assert summary["size"] == 2 == summary["record_count"]
    assert summary["secondary_record_count"] == 0


def test_canonical_payload_counts_articles_not_records():
    cluster = [
        record("http://a", "Dhading", "2022-06-09"),
        record("http://a", "Dhading", "2022-06-09", basis=EXTRACTION_SECONDARY),
    ]
    canonical = build_canonical_event(cluster, "2026-09-12T00:00:00Z", cluster_id="c1")
    payload = json.loads(canonical["event_payload"])
    assert payload["size"] == 1
    assert payload["record_count"] == 2
    assert payload["urls"] == ["http://a"]


# ---------------------------------------------------------------------------
# A recovered record must not speak for the event
# ---------------------------------------------------------------------------


def test_a_directly_reported_record_represents_the_cluster():
    """The recovered record's casualties, municipality and trigger belong to
    the article's own subject, which is a different district-day."""

    secondary = record(
        "http://a", "Dhading", "2022-06-09", basis=EXTRACTION_SECONDARY, date_basis="weekday"
    )
    primary = record("http://b", "Dhading", "2022-06-09", source="other", deaths=3)
    assert choose_representative([secondary, primary]).url == "http://b"
    assert choose_representative([primary, secondary]).url == "http://b"


def test_a_more_confident_secondary_still_loses_to_a_primary():
    """Confidence is not the tiebreaker here. A recovered record can look
    arbitrarily confident about the one thing it knows and still know nothing
    about the impact fields the representative supplies."""

    secondary = EventRecord(
        **{
            **record("http://a", "Dhading", "2022-06-09",
                     basis=EXTRACTION_SECONDARY, date_basis="explicit_ad_date").__dict__,
            "conf_class": 0.99,
            "conf_date": 0.99,
            "conf_district": 0.99,
            "conf_place": 0.99,
        }
    )
    primary = record("http://b", "Dhading", "2022-06-09", source="other")
    assert choose_representative([secondary, primary]).is_secondary is False


def test_a_secondary_record_carries_no_impact_fields():
    """Checked at the extractor boundary, because this is the error that would
    make the inventory look *more* complete and so be least questioned."""

    from landslide_inventory.unify.multievent import SecondaryFailure

    payload = SecondaryFailure(
        district="Kalikot",
        event_date_ad="2019-04-06",
        sentence="Landslides have occurred in Shubh Kalika Rural Municipality of Kalikot.",
        date_basis="weekday",
        confidence=0.78,
    ).to_record()
    for field in ("deaths", "missing", "injured", "municipality", "ward", "trigger"):
        assert payload[field] is None, f"a recovered record must not inherit {field}"
    assert payload["district"] == "Kalikot"
    assert payload["evidence_sentence"]


# ---------------------------------------------------------------------------
# The gate on district-days no article is actually about
# ---------------------------------------------------------------------------


def test_a_cluster_with_any_primary_record_is_not_secondary_only():
    cluster = [
        record("http://a", "Dhading", "2022-06-09"),
        record("http://b", "Dhading", "2022-06-09", basis=EXTRACTION_SECONDARY, source="o"),
    ]
    assert cluster_is_secondary_only(cluster) is False
    assert secondary_only_cluster_admitted(cluster) is True


def test_a_secondary_only_cluster_needs_a_firm_date_anchor():
    """A district-day no article is about, dated from 'last night', is the
    single most likely way a fabricated event enters a release."""

    soft = [
        record("http://a", "Kalikot", "2019-04-06", basis=EXTRACTION_SECONDARY,
               date_basis="previous_day")
    ]
    assert cluster_is_secondary_only(soft) is True
    assert secondary_only_cluster_admitted(soft) is False

    firm = [
        record("http://a", "Kalikot", "2019-04-06", basis=EXTRACTION_SECONDARY,
               date_basis="explicit_ad_date")
    ]
    assert secondary_only_cluster_admitted(firm) is True


def test_one_firm_record_admits_a_mixed_secondary_only_cluster():
    cluster = [
        record("http://a", "Kalikot", "2019-04-06", basis=EXTRACTION_SECONDARY,
               date_basis="previous_day"),
        record("http://b", "Kalikot", "2019-04-06", basis=EXTRACTION_SECONDARY,
               date_basis="explicit_ad_date", source="other"),
    ]
    assert secondary_only_cluster_admitted(cluster) is True


def test_an_empty_cluster_is_not_secondary_only():
    assert cluster_is_secondary_only([]) is False


# ---------------------------------------------------------------------------
# The two copies of the firm-basis list must not drift
# ---------------------------------------------------------------------------


def test_firm_date_bases_match_the_extractor():
    """dedup_stage duplicates the list rather than importing it, so that dedup
    does not depend on the extractor. Duplication is only safe while something
    fails when the copies disagree."""

    from landslide_inventory.unify.multievent import FIRM_DATE_BASES as EXTRACTOR_BASES

    assert FIRM_DATE_BASES == frozenset(EXTRACTOR_BASES)


def test_extraction_basis_constants_agree_across_modules():
    from landslide_inventory.unify.multievent import SecondaryFailure

    payload = SecondaryFailure("Kalikot", "2019-04-06", "x", "weekday", 0.7).to_record()
    assert payload["extraction_basis"] == EXTRACTION_SECONDARY


def test_an_existing_database_gains_the_record_count_columns(tmp_path):
    """The counts are new columns on a table that already exists in every
    working copy, so `CREATE TABLE IF NOT EXISTS` alone would silently leave
    old databases one INSERT away from failing."""

    import sqlite3

    from landslide_inventory.db import initialize_sqlite

    database = tmp_path / "old.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            CREATE TABLE cluster_summary (
                cluster_id TEXT PRIMARY KEY,
                district TEXT NOT NULL,
                date_min TEXT NOT NULL,
                date_max TEXT NOT NULL,
                size INTEGER NOT NULL,
                sources TEXT NOT NULL,
                urls TEXT NOT NULL,
                inserted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

    initialize_sqlite(database)

    with sqlite3.connect(database) as connection:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(cluster_summary)").fetchall()
        }
    assert {"record_count", "secondary_record_count"} <= columns


@pytest.mark.parametrize("basis", sorted(FIRM_DATE_BASES))
def test_each_firm_basis_admits_a_secondary_only_cluster(basis):
    cluster = [
        record("http://a", "Kalikot", "2019-04-06", basis=EXTRACTION_SECONDARY,
               date_basis=basis)
    ]
    assert secondary_only_cluster_admitted(cluster) is True
