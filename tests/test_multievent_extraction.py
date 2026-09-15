"""The secondary-failure extractor: what it must recover and what it must refuse.

This module emits *additional* district-days from one article. Every test here
is oriented by one asymmetry: a missed recovery costs one district-day out of a
projected two hundred, while a false recovery puts a fabricated landslide into
the canonical inventory, spatially correlated with rainfall, where nothing
downstream can tell it from a real one.

So the refusal tests are the important ones. Each is drawn from a district
mention observed in the 47-article audit that would have become a false
case-day: the home district of someone who died somewhere else, the filing
city, the far end of a blocked road, where stranded vehicles were going, a
person whose given name is also a rural municipality, a highway whose name is
also a rural municipality, and a settlement whose name belongs to a
municipality in another district.
"""

from __future__ import annotations

import pytest

from landslide_inventory.unify.multievent import extract_secondary_failures


def run(
    text,
    *,
    lang="en",
    published,
    primary_district=None,
    primary_date=None,
    primary_municipality=None,
    title=None,
):
    return extract_secondary_failures(
        title,
        text,
        lang=lang,
        published_date_ad=published,
        primary_district=primary_district,
        primary_date=primary_date,
        primary_municipality=primary_municipality,
    )


def districts(results):
    return {result.district for result in results}


def pairs(results):
    return {(result.district, result.event_date_ad) for result in results}


# ---------------------------------------------------------------------------
# What it must recover
# ---------------------------------------------------------------------------


def test_a_second_district_in_the_same_sentence_is_recovered():
    """An explicit date, failure and location in one sentence are recoverable."""

    text = (
        "On April 6, landslides occurred in Dullu Municipality of Dailekh and "
        "Shubh Kalika Rural Municipality of Kalikot, leaving many stranded."
    )
    results = run(
        text, published="2019-04-07", primary_district="Dailekh", primary_date="2019-04-06"
    )
    assert ("Kalikot", "2019-04-06") in pairs(results)


def test_a_second_dated_occasion_in_the_same_district_is_recovered():
    """c1-0017: the analysis unit is the district-day, so a second *day* in the
    same district is as much a recovery as a second district."""

    text = (
        "Netra Prasad Khand died on the night of June 9 when a landslide swept away his house "
        "at Agnichok in Tripura Sundari Rural Municipality-5. "
        "Her house was badly damaged in a landslide on June 14 at "
        "Gangajamuna Rural Municipality-5."
    )
    results = run(
        text, published="2022-06-22", primary_district="Dhading", primary_date="2022-06-09"
    )
    assert ("Dhading", "2022-06-14") in pairs(results)


def test_a_retrospectively_reported_but_dated_failure_still_counts():
    """Being reported late is not a reason to discard an occurrence that names
    its own district, its own date and its own local unit. The first read of
    the audit got this wrong, conflating *reported late* with *unusable*."""

    text = (
        "A landslide killed two at Beni Municipality-2 in Myagdi district. "
        "On June 21, landslides had damaged water pipelines at "
        "Raghuganga Rural Municipality-3."
    )
    results = run(
        text,
        published="2021-08-23",
        primary_district="Myagdi",
        primary_date="2021-08-23",
        primary_municipality="Beni Municipality",
    )
    assert ("Myagdi", "2021-06-21") in pairs(results)


def test_a_dated_second_occasion_with_no_named_local_unit_is_given_up():
    """The cost of the municipality gate, recorded rather than hidden.

    c1-0035's real sentence names its failures only as "Maruwa, Upllo Khanna
    and Bankhe Chhaharo" -- settlements the gazetteer does not carry. The
    audit counts that as a defensible recovery and the extractor now refuses
    it, which is the deliberate side of the trade: the same shape, in a
    follow-up re-dating the article's own landslide, is the commonest bad
    record in the corpus. Recall on the development audit fell from 0.53 to
    0.35 for this reason.
    """

    text = (
        "Bagarphant village at Beni Municipality-2 in Myagdi district is without water. "
        "On June 21, landslides at Maruwa damaged water sources and pipelines, "
        "causing acute shortage for 208 houses."
    )
    results = run(
        text,
        published="2021-08-23",
        primary_district="Myagdi",
        primary_date="2021-08-23",
        primary_municipality="Beni Municipality",
    )
    assert results == []


# ---------------------------------------------------------------------------
# What it must refuse: the nine traps
# ---------------------------------------------------------------------------


def test_the_home_district_of_the_dead_is_not_an_event_location():
    """c1-0034. Nine people died at Timure in Rasuwa; the article identifies
    them by where they came from. Emitting those would place fatal landslides
    in two districts that had none."""

    text = (
        "On Wednesday night a landslide claimed nine lives in Timure. "
        "The deceased have been identified as Shyam Shrestha and Mangal Tamang of "
        "Bhotekoshi Rural Municipality-4, Sindhupalchok district, and Ramesh Tamang of Nuwakot."
    )
    results = run(
        text, published="2018-07-27", primary_district="Rasuwa", primary_date="2018-07-25"
    )
    assert "Sindhupalchok" not in districts(results)
    assert "Nuwakot" not in districts(results)


def test_the_dateline_city_is_not_an_event_location():
    """c1-0009 was filed from Surkhet about failures in Dailekh and Kalikot."""

    text = (
        "Surkhet, April 7\n"
        "Landslides have occurred in Dullu Municipality of Dailekh after heavy rain on Saturday."
    )
    results = run(
        text, published="2019-04-07", primary_district="Dailekh", primary_date="2019-04-06"
    )
    assert "Surkhet" not in districts(results)


def test_an_uppercase_dateline_is_also_refused():
    """myRepublica and The Himalayan Times file as `BHOJPUR:` with no comma."""

    text = (
        "BHOJPUR: Two persons were buried to death in landslides triggered by "
        "incessant rainfall in Dhankuta and Sankhuwasabha districts on September 21."
    )
    results = run(
        text, published="2016-09-21", primary_district="Dhankuta", primary_date="2016-09-21"
    )
    assert "Bhojpur" not in districts(results)
    assert "Sankhuwasabha" in districts(results)


def test_page_chrome_and_a_byline_do_not_hide_a_dateline():
    text = (
        "Resize Text Size Small Medium Large Listen By Bira Gadal BAITADI, July 4: "
        "On July 4, houses were swept by a landslide in Bajhang district."
    )
    results = run(
        text, published="2020-07-04", primary_district="Bajura", primary_date=None
    )
    assert "Baitadi" not in districts(results)
    assert "Bajhang" in districts(results)


def test_a_district_alias_inside_a_local_feature_name_is_refused():
    text = "काभ्रे भिरमा पहिरोका कारण भदौ २७ गतेदेखि सडक अवरुद्ध भएको थियो ।"
    results = run(
        text, lang="np", published="2018-09-20", primary_district="Myagdi", primary_date=None
    )
    assert "Kavrepalanchok" not in districts(results)


def test_the_far_end_of_a_blocked_road_is_not_an_event_location():
    """c1-0011: every failure is in Myagdi; Mustang is where the road goes."""

    text = (
        "Landslides in various places of Raghuganga Rural Municipality have affected "
        "traffic on the Beni-Jomsom road connecting Mustang with the national highway "
        "on Tuesday."
    )
    results = run(
        text, published="2024-07-04", primary_district="Myagdi", primary_date="2024-07-04"
    )
    assert "Mustang" not in districts(results)


def test_where_stranded_vehicles_were_headed_is_not_an_event_location():
    """c1-0047 named five districts this way, on a single Lamjung blockage."""

    text = (
        "A landslide blocked the road at Besisahar Municipality-1 on Sunday. "
        "Vehicles headed to Kathmandu, Pokhara, Chitwan, Gorkha and Tanahu could not run."
    )
    results = run(
        text, published="2022-07-18", primary_district="Lamjung", primary_date="2022-07-17"
    )
    assert not districts(results) & {"Chitwan", "Gorkha", "Tanahu"}

    # The same districts, asserted as failure sites rather than destinations,
    # must still be recovered -- otherwise this test would pass for the wrong
    # reason if district resolution simply stopped working.
    control = (
        "On July 17, landslides hit Gorkha."
    )
    recovered = run(
        control, published="2022-07-18", primary_district="Lamjung", primary_date="2022-07-17"
    )
    assert "Gorkha" in districts(recovered)


def test_a_sentence_naming_three_districts_is_an_enumeration():
    """"landslides fell at various places in districts including Palpa,
    Syangja and Gulmi" is an aggregate over an unstated set of failures. It
    locates nothing, and on a corpus run these lists were the second-largest
    source of bad records."""

    text = (
        "A landslide blocked the road at Besisahar Municipality-1 on Sunday. "
        "Landslides also hit Chitwan, Gorkha and Tanahu on Sunday."
    )
    results = run(
        text, published="2022-07-18", primary_district="Lamjung", primary_date="2022-07-17"
    )
    assert not districts(results) & {"Chitwan", "Gorkha", "Tanahu"}


def test_a_distance_reference_is_not_an_event_location():
    """c1-0006: "around 85 kilometres northeast of Kathmandu" locates the event
    by reference to a place it did not happen."""

    text = (
        "At least three persons have died in landslides in Bahrabise municipality of "
        "Sindhupalchok, around 85 kilometres northeast of Kathmandu, on Sunday."
    )
    results = run(
        text,
        published="2020-09-13",
        primary_district="Sindhupalchok",
        primary_date="2020-09-13",
    )
    assert "Kathmandu" not in districts(results)

    control = (
        "At least three persons have died in landslides in Bahrabise municipality of "
        "Sindhupalchok, and landslides hit Kathmandu, on September 13."
    )
    assert "Kathmandu" in districts(
        run(
            control,
            published="2020-09-13",
            primary_district="Sindhupalchok",
            primary_date="2020-09-13",
        )
    )


def test_a_hospital_referral_is_not_an_event_location():
    """c1-0081: victims buried in Rukum West were taken to Jajarkot because it
    was nearer, and the pipeline recorded the event in Jajarkot."""

    text = (
        "पहिरोले पुरेका तीन आमा छोरीलाई उद्धार गरी जिल्ला अस्पताल जाजरकोट तर्फ "
        "पठाइएको छ । आइतबार दिउँसो पहिरो खसेको थियो ।"
    )
    results = run(
        text, lang="np", published="2022-08-28", primary_district="Rukum West", primary_date=None
    )
    assert "Jajarkot" not in districts(results)


def test_a_border_adjacency_mention_is_not_an_event_location():
    """c1-0010: "close to the border with Syangja" on a Gulmi event."""

    text = (
        "Six persons died in landslides in wards 3 and 4 of Satyawati rural municipality "
        "on Tuesday. The incident site is close to the border with Syangja."
    )
    results = run(
        text, published="2019-07-23", primary_district="Gulmi", primary_date="2019-07-23"
    )
    assert "Syangja" not in districts(results)


# ---------------------------------------------------------------------------
# Gazetteer hazards -- these produced real false positives during development
# ---------------------------------------------------------------------------


def test_a_persons_given_name_is_not_read_as_a_municipality():
    """Ramprasad is a rural municipality in Bhojpur. It is also an extremely
    common Nepali given name, and the article here is about Sankhuwasabha."""

    text = (
        "मणिप्रसाद राई, रामप्रसाद राई र दीलबहादुर राईको घर पहिरोले बगाएको छ । "
        "गएराति पहिरो खसेको हो ।"
    )
    results = run(
        text,
        lang="np",
        published="2024-06-13",
        primary_district="Sankhuwasabha",
        primary_date="2024-06-12",
    )
    assert "Bhojpur" not in districts(results)


def test_a_highway_name_is_not_read_as_a_municipality():
    """Koshi Rural Municipality is in Sunsari; the Koshi Highway is not."""

    text = (
        "कोशी राजमार्ग अन्तर्गत मकालु गाउँपालिका–३ नयाँबस्तीमा गएराति गएको पहिरोका "
        "कारण बाटो अवरुद्ध भएको छ ।"
    )
    results = run(
        text, lang="np", published="2026-05-07", primary_district="Bhojpur", primary_date=None
    )
    assert "Sunsari" not in districts(results)


def test_the_longest_municipality_span_wins():
    """Likhu Tamakoshi Rural Municipality is in Ramechhap; Tamakoshi Rural
    Municipality alone is in Dolakha. Matching the shorter span would move the
    event to the wrong district."""

    text = (
        "रामेछापको लिखु तामाकोशी गाउँपालिका–२ मा गएराति पहिरो खस्दा एक जना "
        "गम्भीर घाइते हुनुभएको छ ।"
    )
    results = run(
        text,
        lang="np",
        published="2025-06-23",
        primary_district="Ramechhap",
        primary_date="2025-06-22",
    )
    assert "Dolakha" not in districts(results)


def test_a_municipality_resolves_only_by_its_own_full_name():
    """Tested at the resolver, not through the extractor.

    An earlier version of this test went through `run()` and passed for the
    wrong reason -- a broken regex happened to mangle the name before the
    gazetteer ever saw it. When the regex was fixed the fabricated Rasuwa
    record reappeared, and the test kept passing. So the guarantee is pinned
    where it actually lives.

    Two separate forgiving behaviours have to stay bypassed. The gazetteer ends
    in a 90%-similarity fuzzy match, and before that it tries the trailing 2-
    to 5-token suffixes of the input. "Shubh Kalika Rural Municipality" is a
    real local unit of Kalikot; its 3-token suffix "Kalika Rural Municipality"
    is a real local unit of Rasuwa and matches *exactly*.
    """

    from landslide_inventory.unify.multievent import _exact_municipality

    assert _exact_municipality("Shubh Kalika Rural Municipality", "en") is None
    # ...while names the gazetteer does carry still resolve.
    assert _exact_municipality("Dullu Municipality", "en") == "Dullu Municipality"
    assert (
        _exact_municipality("Gangajamuna Rural Municipality", "en")
        == "Gangajamuna Rural Municipality"
    )
    assert _exact_municipality("गजुरी गाउँपालिका", "np") == "Gajuri Rural Municipality"


def test_the_suffix_shortcut_cannot_fabricate_a_district():
    """The end-to-end consequence of the resolver rule above."""

    text = (
        "Heavy rain fell on Saturday night. A landslide occurred in "
        "Shubh Kalika Rural Municipality, blocking the highway."
    )
    results = run(text, published="2019-04-07", primary_district=None, primary_date=None)
    assert "Rasuwa" not in districts(results)


def test_an_english_municipality_name_is_never_split():
    """Dropping a leading word does not recover the intended name -- it
    constructs a different real one. Every word the pattern matched begins with
    a capital, so all of them belong to the name."""

    from landslide_inventory.unify.multievent import _municipality_phrases

    spans = _municipality_phrases(
        "A landslide hit Shubh Kalika Rural Municipality today.", "en"
    )
    assert spans == [["Shubh Kalika Rural Municipality"]]


# ---------------------------------------------------------------------------
# Dates
# ---------------------------------------------------------------------------


def test_a_sentence_without_a_date_anchor_yields_nothing_in_a_multi_date_article():
    """The reproducibility rules forbid using a publication date as an event
    date. In a bulletin that carries several dates, reusing one for an
    unanchored sentence is the same error wearing a different hat."""

    text = (
        "A landslide blocked the road in Ilam on April 20. "
        "A landslide has also blocked the road in Myagdi on April 16. "
        "Roads in Lamjung are obstructed."
    )
    results = run(text, published="2026-05-05", primary_district="Ilam", primary_date=None)
    assert "Lamjung" not in districts(results)


def test_a_sentence_with_two_dates_is_dropped_entirely():
    """c1-0044's central sentence lists three blockages from three days. There
    is no way to attribute one date to one district, so nothing is emitted."""

    text = (
        "यही वैशाख १२ गतेको पहिराले अवरुद्ध भोजपुर नगरपालिका–५ को लोकमार्ग र "
        "१६ गतेको पहिराले अवरुद्ध म्याग्दीको सडकखण्ड पुरिएको छ ।"
    )
    results = run(
        text, lang="np", published="2026-05-05", primary_district="Ilam", primary_date=None
    )
    assert results == []


def test_a_date_anchor_is_never_shared_across_sentences():
    """The date must occur in the same evidence sentence as the failure."""

    text = (
        "Heavy rainfall fell on April 6. "
        "Landslides have occurred in Dullu Municipality of Dailekh and in "
        "Shubh Kalika Rural Municipality of Kalikot."
    )
    results = run(
        text, published="2019-04-07", primary_district="Dailekh", primary_date="2019-04-06"
    )
    assert results == []


def test_a_same_district_record_on_the_publication_day_is_refused():
    """c1-0046 and c1-0088: an article published on day D describing a failure
    on day D in the district it is already about is describing its own subject,
    usually an ongoing blockage that keeps recurring."""

    text = (
        "पहिरोले सडक अवरुद्ध भएको छ । बिहीबार साढे १२ बजे इच्छाकामना गाउँपालिका-६ "
        "मा पहिरो खसेको हो ।"
    )
    results = run(
        text, lang="np", published="2023-06-29", primary_district="Chitwan",
        primary_date="2023-06-28",
    )
    assert ("Chitwan", "2023-06-29") not in pairs(results)


def test_a_relative_cue_cannot_support_a_same_district_second_occasion():
    """c1-0045: "last night" is how a reporter refers to the event already
    being reported, not evidence of a distinct occasion."""

    text = (
        "Landslides in Taplejung district's Phungling area claimed the lives of four "
        "and destroyed many houses after heavy rains in the region last night."
    )
    results = run(
        text, published="2016-09-03", primary_district="Taplejung", primary_date="2016-09-03"
    )
    assert "Taplejung" not in districts(results)


# ---------------------------------------------------------------------------
# Occurrence, not risk
# ---------------------------------------------------------------------------


def test_a_risk_warning_is_not_an_occurrence():
    text = "Over a dozen households in Dailekh are at high risk of landslide on Tuesday."
    results = run(text, published="2017-08-26", primary_district="Jajarkot", primary_date=None)
    assert "Dailekh" not in districts(results)


def test_a_reopening_bulletin_is_not_an_occurrence():
    """c1-0079 reports that Salyan's blocked section has been *restored*. A
    road coming back into service is not a new landslide."""

    text = (
        "कर्णाली प्रदेशमा सल्यान जिल्लाको पहिरोका कारण अवरुद्ध सडक खण्ड आज बिहान "
        "७:४५ बजेदेखि पूर्ण रूपमा सुचारु भएको छ ।"
    )
    results = run(
        text, lang="np", published="2026-05-07", primary_district="Bhojpur", primary_date=None
    )
    assert "Salyan" not in districts(results)


def test_an_assessment_team_itinerary_is_not_a_list_of_event_locations():
    """c1-0049: "a team went to Taplejung, Panchthar and Sankhuwasabha to
    assess the damage caused by floods and landslides". The sentence carries a
    failure term and a damage word, so it passes the occurrence test on its own
    terms, and the districts are real -- but the event it reports is a visit."""

    text = (
        "ताप्लेजुङ पाँचथर र संखुवासभामा बाढी र पहिरोले पुर्‍याएको क्षतिको "
        "मूल्याङ्कनका लागि गएको टोलीले सोमबार अध्ययन गर्‍यो ।"
    )
    results = run(
        text, lang="np", published="2023-06-17", primary_district="Taplejung",
        primary_date="2023-06-17",
    )
    assert not districts(results) & {"Panchthar", "Sankhuwasabha"}


# ---------------------------------------------------------------------------
# Same-district recoveries: the corpus run's largest source of bad records
# ---------------------------------------------------------------------------


def test_a_same_district_recovery_needs_a_different_municipality():
    """A corpus run produced 134 same-district records sitting exactly one day
    from their article's primary date. That pile-up at a one-day gap is the
    signature of one landslide redescribed by weekday, not of a second
    occasion. A genuine second occasion points somewhere else in the district."""

    same_place = (
        "A landslide buried a house at Jugal Rural Municipality-2 on Thursday, "
        "and the toll from the Jugal Rural Municipality landslide has risen."
    )
    assert "Sindhupalchok" not in districts(
        run(
            same_place,
            published="2020-08-20",
            primary_district="Sindhupalchok",
            primary_date="2020-08-20",
            title=None,
        )
    )


def test_a_same_district_recovery_in_another_municipality_is_kept():
    """A different municipality and an explicit date support another occasion."""

    text = (
        "A landslide killed three at Tripura Sundari Rural Municipality-6. "
        "On July 20, a landslide had killed one at Gajuri Rural Municipality-4."
    )
    results = run(
        text,
        published="2020-07-21",
        primary_district="Dhading",
        primary_date="2020-07-21",
    )
    assert ("Dhading", "2020-07-20") in pairs(results)


def test_a_cross_district_recovery_does_not_need_a_municipality():
    """The municipality gate applies only to same-district records. A second
    *district* is already a distinction the primary record cannot be making."""

    text = (
        "On April 6, landslides occurred in Dullu Municipality of Dailekh and Kalikot."
    )
    results = run(
        text, published="2019-04-07", primary_district="Dailekh", primary_date="2019-04-06"
    )
    assert "Kalikot" in districts(results)


def test_prevention_works_are_not_an_occurrence():
    """c1-0022 is a rock-anchoring story."""

    text = (
        "Landslide prevention works have begun in Raghu Ganga Rural Municipality on "
        "Thursday, and rock anchoring will prevent further landslides."
    )
    results = run(text, published="2024-07-25", primary_district="Kaski", primary_date=None)
    assert "Myagdi" not in districts(results)


# ---------------------------------------------------------------------------
# Structural guarantees
# ---------------------------------------------------------------------------


def test_the_primary_record_is_never_re_emitted():
    text = "A landslide occurred in Dullu Municipality of Dailekh on April 6."
    results = run(
        text, published="2019-04-07", primary_district="Dailekh", primary_date="2019-04-06"
    )
    assert ("Dailekh", "2019-04-06") not in pairs(results)


def test_every_record_carries_its_evidence():
    """Recovered records are the ones most likely to be wrong, so each has to
    stay auditable and separable from the primary inventory."""

    text = "On April 6, landslides occurred in Shubh Kalika Rural Municipality of Kalikot."
    results = run(
        text, published="2019-04-07", primary_district="Dailekh", primary_date="2019-04-06"
    )
    assert results
    for result in results:
        record = result.to_record()
        assert record["extraction_basis"] == "secondary_failure"
        assert record["evidence_sentence"]
        assert record["date_basis"]
        assert 0.0 < float(record["conf_date"]) <= 1.0


def test_output_is_deterministic_and_ordered():
    text = (
        "On April 6, landslides occurred in Dullu Municipality of Dailekh and "
        "Shubh Kalika Rural Municipality of Kalikot."
    )
    kwargs = dict(published="2019-04-07", primary_district="Dailekh", primary_date="2019-04-06")
    first = [(r.district, r.event_date_ad) for r in run(text, **kwargs)]
    second = [(r.district, r.event_date_ad) for r in run(text, **kwargs)]
    assert first == second == sorted(first)


def test_empty_text_is_handled():
    assert run("", published="2020-01-01", primary_district="Kaski", primary_date=None) == []


def test_a_missing_publication_date_yields_no_relative_anchors():
    """Without a publication date a weekday cannot be resolved, and guessing
    would put the event on an arbitrary day."""

    text = "Landslides have occurred in Dullu Municipality of Dailekh on Saturday."
    assert run(text, published=None, primary_district=None, primary_date=None) == []


@pytest.mark.parametrize("lang", ["en", "np"])
def test_both_language_routes_run(lang):
    text = "Landslides occurred." if lang == "en" else "पहिरो खस्यो ।"
    assert run(text, lang=lang, published="2020-07-01", primary_district=None,
               primary_date=None) == []
