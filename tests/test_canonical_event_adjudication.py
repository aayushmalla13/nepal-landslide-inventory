"""Regression tests for canonical event audit adjudication."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "outputs"


def load():
    path = ROOT / "scripts" / "finalize_canonical_event_adjudication.py"
    spec = importlib.util.spec_from_file_location("finalize_canonical_event_adjudication", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def labelled_row(event_id: str, *, final: str = "yes") -> dict[str, str]:
    return {
        "event_id": event_id,
        "final_event_really_happened": final,
        "final_one_physical_event": "yes" if final == "yes" else "",
        "final_district_correct": "yes" if final == "yes" else "",
        "final_date_correct": "no" if final == "yes" else "",
        "final_municipality_correct": "",
        "final_event_type_true": "landslide" if final == "yes" else "",
        "final_hazard_type_true": "landslide" if final == "yes" else "",
        "final_deaths_true": "not_reported" if final == "yes" else "",
        "final_duplicate_merge_correct": "not_applicable" if final == "yes" else "",
        "adjudicator": "reviewer_C",
        "adjudication_notes": "resolved from evidence",
    }


def test_merge_changes_only_adjudicated_rows() -> None:
    module = load()
    first = [
        {"event_id": "event-1", "date_correct": "yes", "annotator": "A", "notes": "first"},
        {"event_id": "event-2", "date_correct": "yes", "annotator": "A", "notes": "agreed"},
    ]
    for row in first:
        for field in module.REVIEW_FIELDS:
            row.setdefault(field, "yes")
    merged = module.merge(first, [labelled_row("event-1")])
    assert merged[0]["date_correct"] == "no"
    assert merged[0]["annotator"] == "reviewer_C"
    assert merged[1] == first[1]


def test_merge_rejects_unknown_event() -> None:
    module = load()
    with pytest.raises(ValueError, match="unknown event IDs"):
        module.merge([{"event_id": "event-1"}], [labelled_row("other")])


@pytest.mark.skipif(
    not (OUTPUT / "canonical_event_audit_ADJUDICATE_COMPLETED.csv").exists(),
    reason="completed adjudication is not available",
)
def test_completed_adjudication_validates() -> None:
    module = load()
    agreement = __import__("json").loads(module.AGREEMENT.read_text(encoding="utf-8"))
    module.validate(
        module.read_csv(module.DEFAULT_COMPLETED),
        module.read_csv(module.ADJUDICATION_TEMPLATE),
        agreement["outputs"][module.ADJUDICATION_TEMPLATE.name],
    )
