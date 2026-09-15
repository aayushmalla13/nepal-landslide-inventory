from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load_scorer():
    sys.path.insert(0, str(ROOT / "src"))
    path = ROOT / "scripts" / "score_secondary_locked_v8.py"
    spec = importlib.util.spec_from_file_location("score_secondary_locked_v8", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def row(row_id, gold, unresolved="no"):
    return {
        "row_id": row_id,
        "url": f"https://example.test/{row_id}",
        "primary_district_date_true": "Kalikot|2020-01-01",
        "additional_district_dates_true": gold,
        "unresolved_additional_events_true": unresolved,
    }


def key(row_id, predictions, weight="1"):
    return {
        "row_id": row_id,
        "url": f"https://example.test/{row_id}",
        "stratum": "en:ordinary",
        "inclusion_weight": weight,
        "strict_v2_predictions": predictions,
        "pipeline_primary_district": "Kalikot",
        "pipeline_primary_date": "2020-01-01",
    }


def test_exact_pairs_score_tp_fp_and_fn():
    scorer = load_scorer()
    labels = [row("a", "Kailali|2020-01-02; Jumla|2020-01-03")]
    hidden = [key("a", "Kailali|2020-01-02; Bajura|2020-01-04")]
    report, comparison = scorer.score_rows(labels, hidden)
    assert report["unweighted"]["counts"]["recovery_tp"] == 1
    assert report["unweighted"]["counts"]["recovery_fn"] == 1
    assert report["unweighted"]["counts"]["precision_fp"] == 1
    assert comparison[0]["unscorable_predicted_pairs"] == 0


def test_unmatched_prediction_is_unscorable_when_truth_is_partial():
    scorer = load_scorer()
    labels = [row("a", "unclear", "yes")]
    hidden = [key("a", "Sindhupalchok|2021-06-15")]
    report, comparison = scorer.score_rows(labels, hidden)
    assert report["unweighted"]["counts"]["precision_fp"] == 0
    assert report["unweighted"]["counts"]["unscorable_predictions"] == 1
    assert comparison[0]["unscorable_predicted_pairs"] == 1


def test_exact_pairs_still_contribute_to_recall_with_other_unresolved_events():
    scorer = load_scorer()
    labels = [row("a", "Palpa|2019-09-13", "yes")]
    hidden = [key("a", "none", "3")]
    report, _ = scorer.score_rows(labels, hidden)
    assert report["unweighted"]["pipeline_missing_exact_pair_recall"]["denominator"] == 1
    assert report["weighted"]["pipeline_missing_exact_pair_recall"]["denominator"] == 3


def test_unclear_requires_unresolved_yes():
    scorer = load_scorer()
    with pytest.raises(ValueError, match="require unresolved=yes"):
        scorer.score_rows([row("a", "unclear", "no")], [key("a", "none")])


def test_completed_pack_scores_to_the_conservative_decision():
    scorer = load_scorer()
    base = ROOT / "data" / "outputs"
    labels = scorer.read_csv(base / "secondary_locked_v8_COMPLETED.csv")
    hidden = scorer.read_csv(base / "secondary_locked_v8_DO_NOT_OPEN_predictions.csv")
    report, _ = scorer.score_rows(labels, hidden)
    assert report["unweighted"]["pipeline_missing_exact_pair_recall"]["estimate"] == 0
    assert report["unweighted"]["adjudicable_pair_precision"]["estimate"] is None
    assert report["unweighted"]["counts"]["unscorable_predictions"] == 1
