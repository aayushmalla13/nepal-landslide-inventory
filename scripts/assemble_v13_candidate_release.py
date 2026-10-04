#!/usr/bin/env python3
"""Assemble the validated v1.3 plans into a locked candidate release."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
from pathlib import Path


def _load_core():
    path = Path(__file__).with_name("assemble_post_correction_candidate_release.py")
    spec = importlib.util.spec_from_file_location("v13_candidate_assembler_core", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load candidate assembler core: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


core = _load_core()
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RELEASE_ID = "nepal_landslide_inventory_v1.3.0_candidate_20260930"
SOURCE_RELEASE_ID = "nepal_landslide_inventory_v1.2.0_candidate_20260929"
EXPECTED_SOURCE_ROWS = 2160
EXPECTED_ROWS = 2146
PLAN_FILES = {
    "remove": "v13_identity_plan_REMOVE_OLD_EVENTS.csv",
    "new": "v13_identity_plan_NEW_EVENTS.csv",
    "merge": "v13_identity_plan_MERGES_EXISTING.csv",
    "identity_excluded": "v13_identity_plan_EXCLUDED_CANDIDATES.csv",
    "true_corrections": "v13_true_value_plan_CORRECTIONS.csv",
    "true_exclusions": "v13_true_value_plan_EXCLUSIONS.csv",
    "structured_corrections": "v13_structured_attribute_plan_CORRECTIONS.csv",
    "structured_exclusions": "v13_structured_attribute_plan_EXCLUSIONS.csv",
}
PLAN_MANIFESTS = {
    "v13_identity_plan_manifest.json": (
        "v13_identity_plan_unapplied_true_value_and_structured_attribute_gates_pending"
    ),
    "v13_true_value_plan_manifest.json": (
        "v13_true_value_plan_unapplied_structured_attribute_gate_pending"
    ),
    "v13_structured_attribute_plan_manifest.json": (
        "all_v13_manual_gates_complete_candidate_assembly_pending"
    ),
}


def candidate_suffix(candidate_id: str) -> str:
    prefix = "v13_candidate_"
    if not candidate_id.startswith(prefix):
        raise ValueError(f"Unexpected v1.3 candidate ID: {candidate_id}")
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
        Path("data/releases") / SOURCE_RELEASE_ID / "landslide_inventory.sqlite"
    )
    core.ASSEMBLER_SCRIPT = Path(__file__)
    core.README_TITLE = "v1.3 inventory candidate"
    core.README_PLAN_LABEL = "v1.3"


configure_core()
assemble_rows = core.assemble_rows
read_csv = core.read_csv
sha256 = core.sha256


def expected_application_actions(root: Path) -> int:
    outputs = root / "data/outputs"
    return sum(len(read_csv(outputs / name)) for name in PLAN_FILES.values())


def finalize_manifest(root: Path, release_dir: Path) -> None:
    manifest_path = release_dir / "release_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    with (release_dir / "correction_application_log.csv").open(
        encoding="utf-8-sig", newline=""
    ) as handle:
        logged_actions = sum(1 for _ in csv.DictReader(handle))
    expected_actions = expected_application_actions(root)
    manifest["checks"].pop("expected_2872_rows", None)
    manifest["checks"]["expected_2146_rows"] = (
        manifest["canonical_summary"]["rows"] == EXPECTED_ROWS
    )
    manifest["checks"]["all_manual_plan_actions_logged"] = (
        logged_actions == expected_actions
    )
    manifest["notes"] = (
        "Candidate assembled from frozen v1.2 and the validated v1.3 identity, "
        "true-value, and structured-attribute plans. Earlier metrics do not "
        "validate this candidate."
    )
    if not all(
        value
        for key, value in manifest["checks"].items()
        if key != "fresh_locked_validation_complete"
    ):
        raise ValueError(f"v1.3 release reconciliation failed: {manifest['checks']}")
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def build_release(
    root: Path, release_id: str, output_dir: Path, *, force: bool = False
) -> Path:
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
    output_dir = (
        Path(args.output_dir).resolve()
        if args.output_dir
        else root / "data/releases" / args.release_id
    )
    release_dir = build_release(root, args.release_id, output_dir, force=args.force)
    print(f"Wrote v1.3 candidate release to {release_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
