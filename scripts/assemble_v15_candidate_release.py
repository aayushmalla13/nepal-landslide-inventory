#!/usr/bin/env python3
"""Assemble the validated v1.5 plans into a locked candidate release."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
from datetime import date
from pathlib import Path


def _load_core():
    path = Path(__file__).with_name("assemble_post_correction_candidate_release.py")
    spec = importlib.util.spec_from_file_location("v15_candidate_assembler_core", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load candidate assembler core: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


core = _load_core()
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RELEASE_ID = "nepal_landslide_inventory_v1.5.0_candidate_20261003"
SOURCE_RELEASE_ID = "nepal_landslide_inventory_v1.4.0_candidate_20261002"
EXPECTED_SOURCE_ROWS = 2138
EXPECTED_ROWS = 2122
PLAN_FILES = {
    "remove": "v15_identity_plan_REMOVE_OLD_EVENTS.csv",
    "new": "v15_release_identity_NEW_EVENTS.csv",
    "merge": "v15_identity_plan_MERGES_EXISTING.csv",
    "identity_excluded": "v15_release_identity_EXCLUDED_CANDIDATES.csv",
    "true_corrections": "v15_true_value_plan_CORRECTIONS.csv",
    "true_exclusions": "v15_true_value_plan_EXCLUSIONS.csv",
    "structured_corrections": "v15_structured_attribute_plan_CORRECTIONS.csv",
    "structured_exclusions": "v15_structured_attribute_plan_EXCLUSIONS.csv",
}
PLAN_MANIFESTS = {
    "v15_identity_plan_manifest.json": (
        "v15_identity_plan_unapplied_true_value_and_structured_attribute_gates_pending"
    ),
    "v15_true_value_plan_manifest.json": (
        "v15_true_value_plan_unapplied_structured_attribute_gate_pending"
    ),
    "v15_structured_attribute_plan_manifest.json": (
        "all_v15_manual_gates_complete_candidate_assembly_pending"
    ),
    "v15_release_preflight_manifest.json": (
        "v15_release_preflight_exact_date_gate_complete"
    ),
}


def candidate_suffix(candidate_id: str) -> str:
    prefix = "v15_candidate_"
    if not candidate_id.startswith(prefix):
        raise ValueError(f"Unexpected v1.5 candidate ID: {candidate_id}")
    return candidate_id.removeprefix(prefix)


def configure_core() -> None:
    core.DEFAULT_RELEASE_ID = DEFAULT_RELEASE_ID
    core.SOURCE_RELEASE_ID = SOURCE_RELEASE_ID
    core.EXPECTED_SOURCE_ROWS = EXPECTED_SOURCE_ROWS
    core.EXPECTED_ROWS = EXPECTED_ROWS
    core.PLAN_FILES = PLAN_FILES
    core.PLAN_MANIFESTS = PLAN_MANIFESTS
    core._candidate_suffix = candidate_suffix
    core.LOCATION_OVERRIDES = {}
    core.ARTICLE_DATABASE_RELATIVE = (
        Path("data/releases")
        / "nepal_landslide_inventory_v1.2.0_candidate_20260929"
        / "landslide_inventory.sqlite"
    )
    core.ASSEMBLER_SCRIPT = Path(__file__)
    core.README_TITLE = "v1.5 inventory candidate"
    core.README_PLAN_LABEL = "v1.5"


configure_core()
read_csv = core.read_csv


def expected_application_actions(root: Path) -> int:
    outputs = root / "data/outputs"
    return sum(len(read_csv(outputs / name)) for name in PLAN_FILES.values())


def all_dates_are_exact(rows: list[dict[str, str]]) -> bool:
    try:
        for row in rows:
            date.fromisoformat(row["event_date_ad"])
    except (KeyError, ValueError):
        return False
    return True


def finalize_manifest(root: Path, release_dir: Path) -> None:
    manifest_path = release_dir / "release_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    with (release_dir / "correction_application_log.csv").open(
        encoding="utf-8-sig", newline=""
    ) as handle:
        logged_actions = sum(1 for _ in csv.DictReader(handle))
    canonical_rows = read_csv(release_dir / "canonical_events_final.csv")
    manifest["checks"].pop("expected_2872_rows", None)
    manifest["checks"]["expected_2122_rows"] = (
        manifest["canonical_summary"]["rows"] == EXPECTED_ROWS
    )
    manifest["checks"]["all_event_dates_exact_iso"] = all_dates_are_exact(canonical_rows)
    manifest["checks"]["all_manual_plan_actions_logged"] = (
        logged_actions == expected_application_actions(root)
    )
    manifest["notes"] = (
        "Candidate assembled from frozen v1.4 and the validated v1.5 identity, "
        "true-value, structured-attribute, and exact-date release-preflight plans. "
        "Earlier metrics do not validate this candidate."
    )
    if not all(
        value
        for key, value in manifest["checks"].items()
        if key != "fresh_locked_validation_complete"
    ):
        raise ValueError(f"v1.5 release reconciliation failed: {manifest['checks']}")
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def build_release(root: Path, release_id: str, output_dir: Path, *, force: bool = False) -> Path:
    configure_core()
    release_dir = core.build_release(root, release_id, output_dir, force=force)
    finalize_manifest(root, release_dir)
    return release_dir


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--release-id", default=DEFAULT_RELEASE_ID)
    parser.add_argument("--output-dir")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    output_dir = Path(args.output_dir).resolve() if args.output_dir else root / "data/releases" / args.release_id
    release_dir = build_release(root, args.release_id, output_dir, force=args.force)
    print(f"Wrote v1.5 candidate release to {release_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
