"""Regression boundary for the failed experimental secondary extractor."""

from __future__ import annotations

import ast
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def extraction_bases(path: Path) -> set[str]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return {(row.get("extraction_basis") or "primary").strip() for row in csv.DictReader(handle)}


def test_secondary_extraction_is_not_a_pipeline_stage() -> None:
    from landslide_inventory.run import STAGE_ALIASES, STAGE_HANDLERS

    public_names = set(STAGE_HANDLERS) | set(STAGE_ALIASES)
    assert not any("secondary" in name or "multievent" in name for name in public_names)


def test_no_production_module_imports_the_experimental_extractor() -> None:
    source_root = ROOT / "src" / "landslide_inventory"
    violations: list[str] = []
    for path in source_root.rglob("*.py"):
        if path.name == "multievent.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and "multievent" in (node.module or ""):
                violations.append(str(path.relative_to(ROOT)))
            if isinstance(node, ast.Import):
                if any("multievent" in alias.name for alias in node.names):
                    violations.append(str(path.relative_to(ROOT)))
    assert violations == []


def test_working_canonical_inventory_contains_only_primary_records() -> None:
    path = ROOT / "data" / "outputs" / "canonical_events_final.csv"
    assert "secondary_failure" not in extraction_bases(path)


def test_frozen_inventory_release_contains_only_primary_records() -> None:
    path = (
        ROOT
        / "data"
        / "releases"
        / "nepal_landslide_inventory_v0.4.0_v6_20260810"
        / "canonical_events_final.csv"
    )
    assert "secondary_failure" not in extraction_bases(path)


def test_decision_record_requires_new_independent_evidence_to_reopen() -> None:
    text = (ROOT / "docs" / "SECONDARY_EXTRACTION_DECISION.md").read_text(encoding="utf-8")
    assert "DO NOT INTEGRATE" in text
    assert "independent human" in text
    assert "new versioned release" in text
