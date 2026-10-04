"""Tests for conservative normalization of v0.9 mapping decisions."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "normalize_v09_article_mapping_submission.py"
_spec = importlib.util.spec_from_file_location("normalize_v09_mapping", MODULE_PATH)
module = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(module)


def _row(queue_id: str, groups: list[dict[str, str]]) -> dict[str, str]:
    return {
        "queue_id": queue_id,
        "final_resolution": "decompose_source_article",
        "final_event_count": str(len(groups)),
        "final_event_groups_json": json.dumps(groups),
        "excluded_article_mapping_ids_json": "[]",
    }


def test_unclear_normalization_clears_actionable_fields(monkeypatch) -> None:
    monkeypatch.setattr(module, "UNCLEAR_ROWS", {"Q1"})
    monkeypatch.setattr(module, "RETAIN_GROUPS", {})
    normalized, log = module.normalize_rows([_row("Q1", [{"group_id": "G1"}])])
    assert normalized[0]["final_resolution"] == "unclear"
    assert normalized[0]["final_event_count"] == ""
    assert normalized[0]["final_event_groups_json"] == ""
    assert normalized[0]["excluded_article_mapping_ids_json"] == ""
    assert log[0]["normalization_action"] == "clear_non_actionable_event_fields"


def test_partial_normalization_retains_only_complete_selected_groups(monkeypatch) -> None:
    monkeypatch.setattr(module, "UNCLEAR_ROWS", set())
    monkeypatch.setattr(module, "RETAIN_GROUPS", {"Q1": {"G2"}})
    groups = [{"group_id": "G1"}, {"group_id": "G2"}]
    normalized, _log = module.normalize_rows([_row("Q1", groups)])
    assert normalized[0]["final_event_count"] == "1"
    assert json.loads(normalized[0]["final_event_groups_json"]) == [{"group_id": "G2"}]
