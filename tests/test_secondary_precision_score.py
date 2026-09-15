"""Tests for the blind secondary-recovery precision gate."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load_scorer():
    spec = importlib.util.spec_from_file_location("score_secondary_precision", ROOT / "scripts" / "score_secondary_precision.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def fixtures():
    labels = [
        {"row_id": "sec-0001", "claimed_district": "Kalikot", "claimed_date": "2020-01-01", "failure_really_happened_there": "yes", "date_is_right": "yes", "annotator": "human", "notes": "confirmed"},
        {"row_id": "sec-0002", "claimed_district": "Jumla", "claimed_date": "2020-01-02", "failure_really_happened_there": "yes", "date_is_right": "unclear", "annotator": "human", "notes": "date absent"},
        {"row_id": "sec-0003", "claimed_district": "Humla", "claimed_date": "2020-01-03", "failure_really_happened_there": "no", "date_is_right": "", "annotator": "human", "notes": "travel destination"},
    ]
    strata = [
        {"row_id": row["row_id"], "url": f"https://example.test/{index}", "district": row["claimed_district"], "event_date_ad": row["claimed_date"], "stratum": "cross:firm" if index != 2 else "cross:soft", "stratum_population": "3", "inclusion_weight": "1.0", "date_basis": "weekday"}
        for index, row in enumerate(labels, start=1)
    ]
    recovered = [
        {"url": row["url"], "source": "test", "route_lang": "en", "primary_district": "Dolpa", "primary_date": "2020-01-01", "district": row["district"], "event_date_ad": row["event_date_ad"], "date_basis": row["date_basis"], "conf_date": "0.8", "firm_date": "True", "already_in_inventory": "False", "already_a_case_day": "False", "evidence_sentence": "A landslide occurred."}
        for row in strata
    ]
    return labels, strata, recovered


def test_only_jointly_confirmed_claims_enter_the_supplement():
    scorer = load_scorer()
    report, verified = scorer.score(*fixtures())
    assert [row["row_id"] for row in verified] == ["sec-0001"]
    assert verified[0]["manual_verification_status"] == scorer.VERIFIED_STATUS
    assert verified[0]["release_status"] == scorer.SUPPLEMENT_STATUS
    assert report["overall"]["joint_district_date_precision"] == pytest.approx(1 / 3, abs=1e-4)
    assert report["release_gate"]["decision"] == "failed"
    assert report["design"]["recall_estimable"] is False


def test_date_must_be_blank_when_location_is_not_yes():
    scorer = load_scorer()
    labels, strata, recovered = fixtures()
    labels[2]["date_is_right"] = "yes"
    with pytest.raises(ValueError, match="date label must be blank"):
        scorer.score(labels, strata, recovered)


def test_reviewed_claim_must_join_back_to_the_dry_run():
    scorer = load_scorer()
    labels, strata, recovered = fixtures()
    recovered.pop()
    with pytest.raises(ValueError, match="absent from secondary_failures"):
        scorer.score(labels, strata, recovered)


def test_current_completed_census_exports_52_verified_claims():
    scorer = load_scorer()
    labels = scorer.read_csv(ROOT / "data/outputs/secondary_precision_HUMAN_COMPLETED.csv")
    strata = scorer.read_csv(ROOT / "data/outputs/secondary_precision_strata.csv")
    recovered = scorer.read_csv(ROOT / "data/outputs/secondary_failures.csv")
    report, verified = scorer.score(labels, strata, recovered)
    assert report["overall"]["reviewed_claims"] == 154
    assert report["overall"]["location_confirmed"] == 108
    assert report["overall"]["verified_claims"] == 52
    assert report["overall"]["joint_district_date_precision"] == 0.3377
    assert report["verified_supplement"]["distinct_district_days"] == 48
    assert len(verified) == 52
    assert all(row["release_status"] == scorer.SUPPLEMENT_STATUS for row in verified)
