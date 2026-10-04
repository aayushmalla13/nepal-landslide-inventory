#!/usr/bin/env python3
"""Freeze external-agreement outputs into a checksummed release bundle."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_RELEASE_ID = "nepal_landslide_external_validation_v0.2.0_20261004"
INVENTORY_RELEASE_ID = (
    "nepal_landslide_inventory_v1.5.0_event_detection_validated_20261004"
)
EXPECTED_CANONICAL_SHA256 = (
    "313745c27218be7989764cc9614b71cc69a9549ff05c483247a6c89bd276ae19"
)
OUTPUT_FILES = (
    "external_agreement.json",
    "external_match_report.md",
    "external_bipad_input_snapshot.csv",
    "external_bipad_match_candidates.csv",
    "external_search_seeds.csv",
    "external_unmatched_news.csv",
    "external_coolr_inventories.csv",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def csv_rows(path: Path) -> int:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def validate_outputs(root: Path) -> dict[str, Any]:
    outputs = root / "data" / "outputs"
    missing = [name for name in OUTPUT_FILES if not (outputs / name).is_file()]
    if missing:
        raise FileNotFoundError(f"External-validation outputs missing: {missing}")

    agreement = json.loads((outputs / "external_agreement.json").read_text(encoding="utf-8"))
    inventory_dir = root / "data" / "releases" / INVENTORY_RELEASE_ID
    inventory_manifest = json.loads(
        (inventory_dir / "release_manifest.json").read_text(encoding="utf-8")
    )
    canonical_path = root / agreement["canonical_input"]["path"]
    canonical_hash = sha256(canonical_path)
    if canonical_hash != EXPECTED_CANONICAL_SHA256:
        raise ValueError("Configured canonical CSV is not the locked v1.5 research release")
    if agreement["canonical_input"]["sha256"] != canonical_hash:
        raise ValueError("Agreement canonical-input checksum mismatch")
    if inventory_manifest["canonical_summary"]["sha256"] != canonical_hash:
        raise ValueError("Inventory manifest does not pin the agreement input")

    snapshot_path = root / agreement["bipad_input"]["path"]
    snapshot_hash = sha256(snapshot_path)
    if agreement["bipad_input"]["sha256"] != snapshot_hash:
        raise ValueError("Agreement BIPAD-input checksum mismatch")
    snapshot_rows = csv_rows(snapshot_path)
    if snapshot_rows != agreement["bipad_input"]["rows"]:
        raise ValueError("Agreement BIPAD-input row count mismatch")

    overlap = agreement["layer2_overlap"]
    match_rows = csv_rows(outputs / "external_bipad_match_candidates.csv")
    if match_rows != overlap["matches"]:
        raise ValueError("Match-candidate table does not reconcile to agreement JSON")
    report = (outputs / "external_match_report.md").read_text(encoding="utf-8")
    if canonical_hash not in report or snapshot_hash not in report:
        raise ValueError("External match report does not record both input hashes")

    return {
        "agreement": agreement,
        "inventory_manifest": inventory_manifest,
        "canonical_hash": canonical_hash,
        "bipad_hash": snapshot_hash,
        "bipad_rows": snapshot_rows,
        "match_rows": match_rows,
        "search_seed_rows": csv_rows(outputs / "external_search_seeds.csv"),
        "unmatched_news_rows": csv_rows(outputs / "external_unmatched_news.csv"),
    }


def build_release(root: Path, release_id: str, output_dir: Path) -> Path:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"Release directory is not empty: {output_dir}")
    validated = validate_outputs(root)
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = root / "data" / "outputs"
    for name in OUTPUT_FILES:
        shutil.copy2(outputs / name, output_dir / name)

    agreement = validated["agreement"]
    overlap = agreement["layer2_overlap"]
    readme = output_dir / "EXTERNAL_VALIDATION_README.md"
    readme.write_text(
        "\n".join(
            [
                "# External agreement analysis",
                "",
                f"Release: `{release_id}`",
                f"Inventory: `{INVENTORY_RELEASE_ID}`",
                f"Comparison cutoff: {agreement['comparison_end']}",
                f"Eligible news events: {overlap['news_total']:,}",
                f"Harmonized BIPAD incidents: {overlap['bipad_total']:,}",
                "Status: analysis complete; linked inventory validated for event detection.",
                "",
                "BIPAD is an incomplete comparison system, not ground truth. The",
                "bundle reports overlap and agreement, not precision or recall.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    bundled = [*(output_dir / name for name in OUTPUT_FILES), readme]
    files = [
        {"file": path.name, "bytes": path.stat().st_size, "sha256": sha256(path)}
        for path in bundled
    ]
    lock_payload = "\n".join(f"{item['file']}:{item['sha256']}" for item in files)
    inventory_status = validated["inventory_manifest"].get("status", "unknown")
    manifest = {
        "release_id": release_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "analysis_complete_inventory_event_detection_validated",
        "inventory_release": INVENTORY_RELEASE_ID,
        "inventory_validation_status": inventory_status,
        "comparison_period": {
            "start": agreement["comparison_start"],
            "end": agreement["comparison_end"],
        },
        "inputs": {
            "canonical_events": {
                "path": agreement["canonical_input"]["path"],
                "sha256": validated["canonical_hash"],
            },
            "bipad_snapshot": {
                "path": "external_bipad_input_snapshot.csv",
                "sha256": validated["bipad_hash"],
                "rows": validated["bipad_rows"],
            },
        },
        "summary": {
            "eligible_news_events": overlap["news_total"],
            "bipad_incident_clusters": overlap["bipad_total"],
            "candidate_pairs": validated["match_rows"],
            "search_seeds": validated["search_seed_rows"],
            "unmatched_news_events": validated["unmatched_news_rows"],
            "tier_a_observed_overlap": agreement["layer3_chance_corrected"]["tier_A"][
                "observed_overlap"
            ],
            "tier_a_chance_corrected": agreement["layer3_chance_corrected"]["tier_A"][
                "chance_corrected"
            ],
        },
        "checks": {
            "canonical_hash_matches_inventory_release": True,
            "bipad_snapshot_hash_matches_agreement": True,
            "bipad_snapshot_rows_match_agreement": True,
            "match_table_reconciles_to_agreement": True,
            "input_hashes_present_in_report": True,
            "inventory_fresh_event_detection_validation_complete": validated[
                "inventory_manifest"
            ].get("checks", {}).get(
                "fresh_locked_event_detection_validation_complete", False
            ),
            "inventory_fresh_full_record_validation_complete": validated[
                "inventory_manifest"
            ].get("checks", {}).get(
                "fresh_locked_full_record_validation_complete", False
            ),
        },
        "files": files,
        "bundle_lock_hash": hashlib.sha256(lock_payload.encode("utf-8")).hexdigest(),
        "notes": (
            "Agreement between incomplete observation systems; BIPAD is not ground "
            "truth and precision/recall must not be derived from this release."
        ),
    }
    (output_dir / "release_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_dir


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--release-id", default=DEFAULT_RELEASE_ID)
    parser.add_argument("--output-dir")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    output_dir = (
        Path(args.output_dir).resolve()
        if args.output_dir
        else root / "data" / "releases" / args.release_id
    )
    release = build_release(root, args.release_id, output_dir)
    print(f"Wrote external-validation release to {release}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
