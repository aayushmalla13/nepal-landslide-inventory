"""Tests for the v0.9 audit-driven remediation queue."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "build_v09_remediation_queue.py"
_spec = importlib.util.spec_from_file_location("v09_remediation", MODULE_PATH)
module = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(module)


def _row(**overrides: str) -> dict[str, str]:
    row = {
        "row_id": "V8F-001",
        "event_id": "event_1",
        "claimed_event_date": "2024-07-01",
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


def _reading() -> dict[str, str]:
    return {"row_id": "V8F-001", "article_evidence": "full article"}


def _weight() -> dict[str, str]:
    return {
        "row_id": "V8F-001",
        "stratum": "np|2023-2026|landslide|single_article",
        "sampling_weight": "12.5",
    }


def test_build_queue_preserves_evidence_and_sampling_provenance() -> None:
    rows = module.build_queue_rows(
        [_row(date_correct="no")],
        {"V8F-001": _reading()},
        {"V8F-001": _weight()},
    )
    assert len(rows) == 1
    assert rows[0]["queue_id"] == "V9R-001"
    assert rows[0]["recommended_actions"] == "correct_date"
    assert rows[0]["correction_readiness"] == "requires_true_value_review"
    assert rows[0]["sampling_weight"] == "12.5"
    assert rows[0]["article_evidence"] == "full article"


def test_false_event_is_routed_to_article_mapping() -> None:
    rows = module.build_queue_rows(
        [_row(event_really_happened="no")],
        {"V8F-001": _reading()},
        {"V8F-001": _weight()},
    )
    assert rows[0]["recommended_actions"] == "exclude_false_event"
    assert rows[0]["priority_tier"] == "P0_identity_or_linkage"
    assert rows[0]["correction_readiness"] == "requires_article_mapping"


def test_clean_row_is_not_queued() -> None:
    assert module.build_queue_rows([_row()], {"V8F-001": _reading()}, {"V8F-001": _weight()}) == []


def test_validate_alignment_rejects_reordered_weights() -> None:
    labels = [_row(row_id="V8F-001"), _row(row_id="V8F-002")]
    readings = [{"row_id": "V8F-001"}, {"row_id": "V8F-002"}]
    weights = [{"row_id": "V8F-002"}, {"row_id": "V8F-001"}]
    with pytest.raises(ValueError, match="sampling-weight row order differ"):
        module.validate_alignment(labels, readings, weights)


def test_summary_uses_full_sample_as_weight_denominator() -> None:
    all_rows = [{"sampling_weight": "2"}, {"sampling_weight": "3"}]
    queue = [
        {
            "sampling_weight": "2",
            "priority_tier": "P0_identity_or_linkage",
            "correction_readiness": "requires_article_mapping",
            "finding_certainty": "confirmed",
            "recommended_actions": "exclude_false_event",
            "systematic_issue_hypotheses": "scope_or_event_specificity",
            "source_domain": "example.com",
        }
    ]
    summary = module.build_summary(all_rows, queue)
    assert summary["population_weighted_flagged_share"] == pytest.approx(0.4)
