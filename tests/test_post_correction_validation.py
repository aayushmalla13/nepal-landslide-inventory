"""Tests for the locked post-correction validation draw."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "draw_post_correction_validation.py"
_spec = importlib.util.spec_from_file_location("draw_post_correction_validation", MODULE_PATH)
draw = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(draw)


def _row(event_id: str, url: str, *, event_type: str = "landslide") -> dict[str, str]:
    return {
        "event_id": event_id,
        "event_date_ad": "2024-07-01",
        "event_type": event_type,
        "cluster_size": "1",
        "representative_title": "Landslide report",
        "representative_url": url,
        "event_payload": json.dumps({"urls": [url]}),
    }


def test_prior_audit_exclusion_includes_every_cluster_url() -> None:
    prior = [_row("e1", "u1")]
    prior[0]["event_payload"] = json.dumps({"urls": ["u1", "u2"]})
    ids, urls = draw.prior_audit_exclusions(prior, [{"event_id": "e1"}])
    assert ids == {"e1"}
    assert urls == {"u1", "u2"}


def test_stratified_selection_is_deterministic() -> None:
    rows = [_row(f"e{i}", f"u{i}", event_type="landslide" if i < 10 else "road") for i in range(20)]

    def key(row: dict[str, str]) -> str:
        return row["event_type"]

    first, sizes, allocation = draw.stratified_select(rows, key, 8, 2, 42)
    second, _, _ = draw.stratified_select(rows, key, 8, 2, 42)
    assert [row["event_id"] for row in first] == [row["event_id"] for row in second]
    assert sizes == {"landslide": 10, "road": 10}
    assert allocation == {"landslide": 4, "road": 4}


def test_correction_frame_keeps_only_present_corrected_events() -> None:
    canonical = [_row("new", "u1"), _row("fixed", "u2"), _row("untouched", "u3")]
    log = [
        {"event_id": "new", "action": "add_reconstructed", "layer": "identity"},
        {"event_id": "fixed", "action": "correct_attributes", "layer": "true_value"},
        {"event_id": "gone", "action": "remove_superseded", "layer": "identity"},
    ]
    frame = draw.correction_frame(canonical, log)
    assert {row["event_id"] for row in frame} == {"new", "fixed"}
    assert {row["_correction_layer"] for row in frame} == {
        "identity_add",
        "true_value_correction",
    }
