"""Tests for the frozen post-correction remediation queue."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "build_post_correction_remediation_queue.py"
_spec = importlib.util.spec_from_file_location("post_correction_remediation", MODULE_PATH)
module = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(module)


def _row(**overrides: str) -> dict[str, str]:
    row = {
        "row_id": "PCF-001",
        "sample_role": "fresh_probability",
        "correction_layer": "",
        "event_id": "event_1",
        "claimed_event_date": "2020-01-01",
        "claimed_district": "Kaski",
        "claimed_municipality": "",
        "claimed_event_type": "landslide",
        "claimed_hazard_type": "landslide",
        "claimed_deaths": "",
        "claimed_missing": "",
        "claimed_injured": "",
        "cluster_article_count": "1",
        "representative_title": "A landslide",
        "representative_url": "https://www.example.com/story",
        "event_evidence": "",
        "event_really_happened": "yes",
        "one_physical_event": "yes",
        "district_correct": "yes",
        "date_correct": "yes",
        "municipality_correct": "",
        "event_type_true": "landslide",
        "hazard_type_true": "landslide",
        "deaths_true": "not_reported",
        "duplicate_merge_correct": "not_applicable",
        "annotator": "reviewer",
        "notes": "",
    }
    row.update(overrides)
    return row


def test_build_queue_preserves_provenance_and_weight() -> None:
    rows = module.build_queue_rows(
        [_row(district_correct="no")],
        {"PCF-001": {"article_evidence": "full article"}},
        {"PCF-001": {"stratum": "np|recent", "sampling_weight": "12.5"}},
        first_number=1,
    )
    assert len(rows) == 1
    assert rows[0]["queue_id"] == "PCR-001"
    assert rows[0]["recommended_actions"] == "correct_district"
    assert rows[0]["source_domain"] == "example.com"
    assert rows[0]["sampling_weight"] == "12.5"
    assert rows[0]["article_evidence"] == "full article"


def test_clean_row_is_not_queued() -> None:
    assert (
        module.build_queue_rows(
            [_row()],
            {"PCF-001": {"article_evidence": "full article"}},
            {"PCF-001": {"stratum": "np|recent", "sampling_weight": "12.5"}},
            first_number=1,
        )
        == []
    )


def test_challenge_findings_are_unweighted() -> None:
    row = _row(
        row_id="PCC-001",
        sample_role="correction_challenge",
        correction_layer="identity_add",
        date_correct="unclear",
    )
    result = module.build_queue_rows(
        [row], {"PCC-001": {"article_evidence": "evidence"}}, {}, first_number=125
    )
    assert result[0]["queue_id"] == "PCR-125"
    assert result[0]["sampling_weight"] == ""
    assert result[0]["finding_certainty"] == "requires_review"


def test_validate_alignment_rejects_reordered_evidence() -> None:
    labels = [_row(row_id="PCF-001"), _row(row_id="PCF-002")]
    readings = [
        {"row_id": "PCF-002"},
        {"row_id": "PCF-001"},
    ]
    with pytest.raises(ValueError, match="row order differ"):
        module.validate_alignment(labels, readings, "fresh_probability")


def test_summary_keeps_fresh_and_challenge_counts_separate() -> None:
    fresh = [{"sampling_weight": "2"}, {"sampling_weight": "3"}]
    challenge = [{}, {}]
    queue = [
        {
            "sample_role": "fresh_probability",
            "sampling_weight": "2",
            "priority_tier": "P0_identity_or_linkage",
            "correction_readiness": "requires_article_mapping",
            "finding_certainty": "confirmed",
            "recommended_actions": "exclude_false_event",
            "systematic_issue_hypotheses": "scope_or_event_specificity",
            "source_domain": "example.com",
        },
        {
            "sample_role": "correction_challenge",
            "sampling_weight": "",
            "priority_tier": "P2_uncertain",
            "correction_readiness": "requires_true_value_review",
            "finding_certainty": "requires_review",
            "recommended_actions": "review_date",
            "systematic_issue_hypotheses": "event_date_resolution",
            "source_domain": "example.org",
        },
    ]
    summary = module.build_summary(fresh, challenge, queue)
    assert summary["fresh_flagged_rows"] == 1
    assert summary["challenge_flagged_rows"] == 1
    assert summary["fresh_weighted_flagged_share"] == pytest.approx(0.4)
