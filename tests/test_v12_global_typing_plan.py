"""Tests for the v1.2 corpus-wide typing repair plan."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load():
    path = ROOT / "scripts/build_v12_global_typing_plan.py"
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def release_row(**updates: str) -> dict[str, str]:
    row = {
        "event_id": "event_1",
        "representative_url": "https://example.test/one",
        "event_type": "landslide",
        "hazard_type": "landslide",
        "event_granularity": "single",
        "article_role": "first_report",
        "extraction_basis": "full_text",
        "deaths": "",
        "missing": "",
        "injured": "",
        "event_payload": json.dumps(
            {
                "representative_url": "https://example.test/one",
                "urls": ["https://example.test/one"],
            }
        ),
    }
    row.update(updates)
    return row


def test_global_plan_retypes_stale_release_row() -> None:
    module = load()
    row = release_row()
    articles = {
        row["representative_url"]: {
            "title": "Landslide blocks Prithvi Highway",
            "text": "The road remained obstructed by debris. " * 20,
        }
    }
    plan = module.build_plan([row], articles, {})
    assert plan[0]["new_event_type"] == "road_obstruction"
    assert "event_type" in json.loads(plan[0]["changed_fields_json"])


def test_human_reviewed_type_is_not_overwritten() -> None:
    module = load()
    row = release_row(event_type="landslide")
    articles = {
        row["representative_url"]: {
            "title": "Landslide blocks Prithvi Highway",
            "text": "The road remained obstructed by debris. " * 20,
        }
    }
    plan = module.build_plan([row], articles, {"event_1": {"event_type"}})
    assert plan[0]["new_event_type"] == "landslide"
    assert plan[0]["event_type_source"] == "human_review"


def test_member_multi_event_evidence_propagates_to_cluster() -> None:
    module = load()
    first = "https://example.test/one"
    second = "https://example.test/two"
    row = release_row(
        event_payload=json.dumps(
            {"representative_url": first, "urls": [first, second]}
        )
    )
    articles = {
        first: {
            "title": "Landslide blocks Prithvi Highway",
            "text": "A single blockage was reported. " * 20,
        },
        second: {
            "title": "Landslides obstruct roads at several places",
            "text": "Several distinct failures were reported.",
        },
    }
    plan = module.build_plan([row], articles, {})
    assert plan[0]["new_event_granularity"] == "multi"


def test_classifier_fingerprint_is_stable_sha256() -> None:
    module = load()
    fingerprint = module.classifier_sha256()
    assert len(fingerprint) == 64
    assert all(character in "0123456789abcdef" for character in fingerprint)
