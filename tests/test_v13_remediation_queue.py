"""Tests for the v1.3 remediation queue wrapper."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load():
    path = ROOT / "scripts/build_v13_remediation_queue.py"
    spec = importlib.util.spec_from_file_location("v13_remediation", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_wrapper_targets_v12_audit_and_v13_outputs() -> None:
    module = load()
    assert module.core.COMPLETED.name == "v12_final_validation_COMPLETED.csv"
    assert module.core.QUEUE.name == "v13_remediation_queue.csv"
    assert Path(module.core.__file__).name == "build_v13_remediation_queue.py"
    summary = module.build_summary(
        [{"sampling_weight": "1"}],
        [
            {
                "sampling_weight": "1",
                "priority_tier": "P0_identity_or_linkage",
                "correction_readiness": "requires_article_mapping",
                "finding_certainty": "confirmed",
                "recommended_actions": "exclude_false_event",
                "systematic_issue_hypotheses": "scope_or_event_specificity",
                "source_domain": "example.test",
            }
        ],
    )
    assert summary["audit"] == "v13_remediation_queue_v1"
    assert summary["source_candidate"].endswith("v1.2.0_candidate_20260929")
    assert summary["target_candidate"].endswith("v1.3.0_candidate")


def test_queue_ids_and_provenance_are_renamed_for_v13() -> None:
    module = load()
    row = {
        "row_id": "V12F-001",
        "event_id": "event-1",
        "representative_url": "https://example.test/story",
        "cluster_article_count": "1",
        "event_really_happened": "yes",
        "one_physical_event": "yes",
        "district_correct": "yes",
        "date_correct": "no",
        "municipality_correct": "yes",
        "event_type_true": "landslide",
        "hazard_type_true": "landslide",
        "deaths_true": "not_reported",
        "duplicate_merge_correct": "",
        "annotator": "human_v12_blind",
        "notes": "follow-up date",
        "claimed_event_date": "2024-01-02",
        "claimed_district": "Kaski",
        "claimed_municipality": "",
        "claimed_event_type": "landslide",
        "claimed_hazard_type": "landslide",
        "claimed_deaths": "",
        "claimed_missing": "",
        "claimed_injured": "",
        "representative_title": "Story",
    }
    reading = {"V12F-001": {"article_evidence": "evidence"}}
    weight = {"V12F-001": {"stratum": "s", "sampling_weight": "1"}}
    result = module.build_queue_rows([row], reading, weight)
    assert result[0]["queue_id"] == "V13R-001"
    assert result[0]["sample_role"] == "v12_final_probability"
    assert result[0]["correction_layer"] == "v13_remediation"
    assert result[0]["recommended_actions"] == "correct_date"
