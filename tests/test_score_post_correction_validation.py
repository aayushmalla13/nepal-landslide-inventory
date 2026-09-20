"""Tests for post-correction validation scoring."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "score_post_correction_validation.py"
)
_spec = importlib.util.spec_from_file_location("score_post_correction_validation", MODULE_PATH)
score = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(score)


def _label(**overrides: str) -> dict[str, str]:
    row = {
        "event_really_happened": "yes",
        "one_physical_event": "yes",
        "district_correct": "yes",
        "date_correct": "yes",
        "municipality_correct": "yes",
        "event_type_true": "landslide",
        "claimed_event_type": "landslide",
        "hazard_type_true": "landslide",
        "claimed_hazard_type": "landslide",
        "deaths_true": "not_reported",
        "claimed_deaths": "",
        "duplicate_merge_correct": "yes",
        "cluster_article_count": "2",
        "claimed_municipality": "Town",
    }
    row.update(overrides)
    return row


def test_usable_record_requires_identity_date_and_district() -> None:
    assert score.usable_record(_label()) == 1.0
    assert score.usable_record(_label(date_correct="no")) == 0.0
    assert score.usable_record(_label(district_correct="unclear")) is None
    assert score.usable_record(_label(event_really_happened="no")) == 0.0


def test_targeted_structured_correction_scores_only_changed_fields() -> None:
    action = {
        "action": "correct_attributes",
        "changed_fields_json": json.dumps(["hazard_type", "deaths"]),
    }
    assert score.targeted_correction_pass(_label(), action) == 1.0
    assert score.targeted_correction_pass(_label(hazard_type_true="rockfall"), action) == 0.0
    assert score.targeted_correction_pass(_label(deaths_true="unclear"), action) is None


def test_reconstructed_event_requires_all_core_claims() -> None:
    action = {"action": "add_reconstructed", "changed_fields_json": "[]"}
    assert score.targeted_correction_pass(_label(), action) == 1.0
    assert score.targeted_correction_pass(_label(one_physical_event="no"), action) == 0.0
    assert score.targeted_correction_pass(_label(date_correct="unclear"), action) is None


def test_merge_challenge_uses_identity_and_duplicate_labels() -> None:
    action = {"action": "merge_into_existing", "changed_fields_json": "[]"}
    assert score.targeted_correction_pass(_label(), action) == 1.0
    assert score.targeted_correction_pass(_label(duplicate_merge_correct="no"), action) == 0.0
