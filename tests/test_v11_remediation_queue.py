"""Tests for the v1.1 remediation queue wrapper."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load():
    path = ROOT / 'scripts/build_v11_remediation_queue.py'
    spec = importlib.util.spec_from_file_location('v11_remediation', path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_wrapper_targets_v10_audit_and_v11_outputs() -> None:
    module = load()
    assert module.core.COMPLETED.name == 'v10_final_validation_COMPLETED.csv'
    assert module.core.QUEUE.name == 'v11_remediation_queue.csv'
    summary = module.build_summary(
        [{'sampling_weight': '1'}],
        [{
            'sampling_weight': '1', 'priority_tier': 'P0_identity_or_linkage',
            'correction_readiness': 'requires_article_mapping',
            'finding_certainty': 'confirmed',
            'recommended_actions': 'exclude_false_event',
            'systematic_issue_hypotheses': 'scope_or_event_specificity',
            'source_domain': 'example.test',
        }],
    )
    assert summary['audit'] == 'v11_remediation_queue_v1'
    assert summary['source_candidate'].endswith('v1.0.0_candidate_20260927')


def test_queue_ids_and_provenance_are_renamed_for_v11() -> None:
    module = load()
    row = {
        'row_id': 'V10F-001', 'event_id': 'event-1',
        'representative_url': 'https://example.test/story',
        'cluster_article_count': '1', 'event_really_happened': 'no',
        'one_physical_event': '', 'district_correct': '', 'date_correct': '',
        'municipality_correct': '', 'event_type_true': '', 'hazard_type_true': '',
        'deaths_true': '', 'duplicate_merge_correct': '', 'annotator': 'human',
        'notes': '', 'claimed_event_date': '2024-01-01',
        'claimed_district': 'Kaski', 'claimed_municipality': '',
        'claimed_event_type': 'landslide', 'claimed_hazard_type': 'landslide',
        'claimed_deaths': '', 'claimed_missing': '', 'claimed_injured': '',
        'representative_title': 'Story',
    }
    reading = {'V10F-001': {'article_evidence': 'evidence'}}
    weight = {'V10F-001': {'stratum': 's', 'sampling_weight': '1'}}
    result = module.build_queue_rows([row], reading, weight)
    assert result[0]['queue_id'] == 'V11R-001'
    assert result[0]['sample_role'] == 'v10_final_probability'
    assert result[0]['correction_layer'] == 'v11_remediation'
