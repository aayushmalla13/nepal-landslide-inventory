"""Tests for the external-validation release builder."""

from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts" / "assemble_external_validation_release.py"
SPEC = importlib.util.spec_from_file_location("external_release", MODULE)
assert SPEC and SPEC.loader
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def fixture_root(tmp_path: Path) -> Path:
    outputs = tmp_path / "data" / "outputs"
    outputs.mkdir(parents=True)
    inventory = tmp_path / "data" / "releases" / release.INVENTORY_RELEASE_ID
    inventory.mkdir(parents=True)
    canonical = inventory / "canonical_events_final.csv"
    canonical.write_text("event_id\ne1\n", encoding="utf-8")
    canonical_hash = release.sha256(canonical)
    release.EXPECTED_CANONICAL_SHA256 = canonical_hash
    (inventory / "release_manifest.json").write_text(
        json.dumps(
            {
                "status": "validated_event_detection_only",
                "canonical_summary": {"sha256": canonical_hash},
                "checks": {
                    "fresh_locked_event_detection_validation_complete": True,
                    "fresh_locked_full_record_validation_complete": False,
                },
            }
        ),
        encoding="utf-8",
    )
    snapshot = outputs / "external_bipad_input_snapshot.csv"
    write_csv(snapshot, [{"bipad_id": "b1", "event_date": "2024-01-01"}])
    snapshot_hash = release.sha256(snapshot)
    agreement = {
        "comparison_start": "2015-01-01",
        "comparison_end": "2024-01-01",
        "canonical_input": {
            "path": str(canonical.relative_to(tmp_path)),
            "sha256": canonical_hash,
        },
        "bipad_input": {
            "path": str(snapshot.relative_to(tmp_path)),
            "sha256": snapshot_hash,
            "rows": 1,
        },
        "layer2_overlap": {"news_total": 1, "bipad_total": 1, "matches": 1},
        "layer3_chance_corrected": {
            "tier_A": {"observed_overlap": 1.0, "chance_corrected": 0.5}
        },
    }
    (outputs / "external_agreement.json").write_text(json.dumps(agreement), encoding="utf-8")
    (outputs / "external_match_report.md").write_text(
        f"{canonical_hash}\n{snapshot_hash}\n", encoding="utf-8"
    )
    write_csv(outputs / "external_bipad_match_candidates.csv", [{"match": "1"}])
    write_csv(outputs / "external_search_seeds.csv", [{"seed": "1"}])
    write_csv(outputs / "external_unmatched_news.csv", [{"event": "1"}])
    write_csv(outputs / "external_coolr_inventories.csv", [{"inventory": "1"}])
    return tmp_path


def test_build_release_reconciles_and_locks_outputs(tmp_path: Path) -> None:
    root = fixture_root(tmp_path)
    target = root / "release"
    release.build_release(root, "test-release", target)
    manifest = json.loads((target / "release_manifest.json").read_text())
    assert manifest["summary"]["candidate_pairs"] == 1
    assert (
        manifest["checks"]["inventory_fresh_event_detection_validation_complete"]
        is True
    )
    assert manifest["checks"]["inventory_fresh_full_record_validation_complete"] is False
    assert len(manifest["files"]) == 8


def test_tampered_bipad_snapshot_is_rejected(tmp_path: Path) -> None:
    root = fixture_root(tmp_path)
    (root / "data" / "outputs" / "external_bipad_input_snapshot.csv").write_text(
        "changed\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="BIPAD-input checksum"):
        release.validate_outputs(root)


def test_wrong_canonical_inventory_is_rejected(tmp_path: Path) -> None:
    root = fixture_root(tmp_path)
    release.EXPECTED_CANONICAL_SHA256 = "0" * 64
    with pytest.raises(ValueError, match="locked v1.5"):
        release.validate_outputs(root)
