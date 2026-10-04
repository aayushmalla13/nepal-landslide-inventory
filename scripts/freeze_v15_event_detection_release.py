#!/usr/bin/env python3
"""Freeze v1.5 as an event-detection-validated research release.

This is deliberately not a full-record promotion. The locked v1.5 audit
passed the prespecified event-existence and district thresholds, but failed
the usable-record, single-event, and date thresholds. The resulting manifest
preserves that boundary explicitly.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


SOURCE_RELEASE_ID = "nepal_landslide_inventory_v1.5.0_candidate_20261003"
DEFAULT_RELEASE_ID = (
    "nepal_landslide_inventory_v1.5.0_event_detection_validated_20261004"
)
EXPECTED_CANONICAL_ROWS = 2122
EXPECTED_CANONICAL_SHA256 = (
    "313745c27218be7989764cc9614b71cc69a9549ff05c483247a6c89bd276ae19"
)

VALIDATION_FILES = (
    "v15_final_validation_COMPLETED.csv",
    "v15_final_validation_weights.csv",
    "v15_final_validation_manifest.json",
    "v15_final_validation_score.json",
    "v15_final_validation_report.md",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inventory_lock(release_id: str, files: list[dict[str, object]]) -> str:
    payload = json.dumps(
        [
            "release_bundle",
            release_id,
            [[item["file"], item["sha256"]] for item in files],
        ],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def validation_scope(score: dict[str, object]) -> dict[str, object]:
    metrics = score["metrics"]
    decision = score["promotion_decision"]
    checks = decision["checks"]

    event_passed = bool(checks["event_existence_precision"]["passed"])
    district_passed = bool(checks["district_accuracy"]["passed"])
    full_record_passed = bool(decision["passed"])
    if not event_passed:
        raise ValueError("locked validation did not pass event-existence precision")
    if full_record_passed:
        raise ValueError("this partial-scope freezer cannot promote a full-record release")

    return {
        "validated_primary_claim": "high-precision event detection",
        "event_detection": {
            "validated": True,
            "estimate": metrics["event_existence_precision"]["estimate"],
            "ci95": metrics["event_existence_precision"][
                "ci95_stratified_bootstrap"
            ],
            "threshold_passed": event_passed,
        },
        "district_assignment": {
            "validated": district_passed,
            "estimate": metrics["district_accuracy"]["estimate"],
            "ci95": metrics["district_accuracy"]["ci95_stratified_bootstrap"],
            "threshold_passed": district_passed,
        },
        "full_record": {
            "validated": False,
            "promotion_rule_passed": full_record_passed,
            "failed_prespecified_metrics": [
                name
                for name in (
                    "usable_record_precision",
                    "single_event_accuracy",
                    "date_accuracy",
                )
                if not checks[name]["passed"]
            ],
        },
    }


def file_entry(path: Path, release_dir: Path) -> dict[str, object]:
    return {
        "file": path.relative_to(release_dir).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def build_release(
    root: Path, release_id: str, output_dir: Path, *, force: bool = False
) -> Path:
    source_dir = root / "data" / "releases" / SOURCE_RELEASE_ID
    source_manifest_path = source_dir / "release_manifest.json"
    outputs = root / "data" / "outputs"

    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    if source_manifest["release_id"] != SOURCE_RELEASE_ID:
        raise ValueError("source release ID does not match the expected v1.5 candidate")
    canonical = source_manifest["canonical_summary"]
    if canonical["rows"] != EXPECTED_CANONICAL_ROWS:
        raise ValueError(f"expected {EXPECTED_CANONICAL_ROWS} canonical rows")
    if canonical["sha256"] != EXPECTED_CANONICAL_SHA256:
        raise ValueError("v1.5 canonical hash does not match the locked candidate")

    score_path = outputs / "v15_final_validation_score.json"
    score = json.loads(score_path.read_text(encoding="utf-8"))
    if score["inventory_release"] != SOURCE_RELEASE_ID:
        raise ValueError("locked validation was not scored against the source candidate")
    audit_manifest = json.loads(
        (outputs / "v15_final_validation_manifest.json").read_text(encoding="utf-8")
    )
    if audit_manifest["canonical_sha256"] != EXPECTED_CANONICAL_SHA256:
        raise ValueError("audit manifest canonical hash does not match v1.5")
    scope = validation_scope(score)

    if output_dir.exists():
        if not force:
            raise FileExistsError(f"release directory already exists: {output_dir}")
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    copied: list[Path] = []
    for entry in source_manifest["files"]:
        source = source_dir / entry["file"]
        target = output_dir / entry["file"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied.append(target)

    source_manifest_copy = output_dir / "source_candidate_manifest.json"
    shutil.copy2(source_manifest_path, source_manifest_copy)
    copied.append(source_manifest_copy)

    validation_dir = output_dir / "validation"
    validation_dir.mkdir()
    for name in VALIDATION_FILES:
        target = validation_dir / name
        shutil.copy2(outputs / name, target)
        copied.append(target)

    readme = output_dir / "RESEARCH_RELEASE_README.md"
    event = scope["event_detection"]
    district = scope["district_assignment"]
    readme.write_text(
        "\n".join(
            [
                "# Nepal landslide inventory v1.5.0 research release",
                "",
                "This immutable bundle supports a validated high-precision web-derived ",
                "landslide event-detection claim for Nepal. It is not validated as a ",
                "complete census or as a high-precision full-record inventory.",
                "",
                f"- Canonical events: {EXPECTED_CANONICAL_ROWS:,}",
                f"- Event-existence precision: {event['estimate']:.3f} "
                f"(95% CI {event['ci95'][0]:.3f}-{event['ci95'][1]:.3f})",
                f"- District accuracy: {district['estimate']:.3f} "
                f"(95% CI {district['ci95'][0]:.3f}-{district['ci95'][1]:.3f})",
                "- Validation sample: 150 locked, stratified probability-audit rows",
                "",
                "The prespecified full-record promotion rule failed because usable-record ",
                "precision, single-event accuracy, and exact-date accuracy did not meet ",
                "their thresholds. Those results are retained in `validation/` and must ",
                "be reported with analyses that depend on exact dates or event granularity.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    copied.append(readme)

    files = [file_entry(path, output_dir) for path in sorted(copied)]
    manifest = {
        "release_id": release_id,
        "status": "validated_event_detection_only",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_candidate": SOURCE_RELEASE_ID,
        "canonical_summary": canonical,
        "validation_scope": scope,
        "checks": {
            "candidate_content_unchanged": True,
            "fresh_locked_event_detection_validation_complete": True,
            "fresh_locked_full_record_validation_complete": False,
            "event_detection_threshold_passed": True,
            "district_threshold_passed": scope["district_assignment"][
                "threshold_passed"
            ],
            "full_record_promotion_rule_passed": False,
        },
        "notes": (
            "The source candidate is unchanged. This release freezes the candidate "
            "together with its completed locked audit and narrows the validated claim "
            "to event detection; it does not override the failed full-record decision."
        ),
        "files": files,
    }
    manifest["bundle_lock_hash"] = inventory_lock(release_id, files)
    (output_dir / "release_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return output_dir


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--release-id", default=DEFAULT_RELEASE_ID)
    parser.add_argument("--output-dir")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    output = (
        Path(args.output_dir).resolve()
        if args.output_dir
        else root / "data" / "releases" / args.release_id
    )
    release = build_release(root, args.release_id, output, force=args.force)
    print(release)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
