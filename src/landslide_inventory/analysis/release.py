"""Build a frozen, checksummed rainfall-analysis bundle."""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
from pathlib import Path

from ..config import AppConfig
from ..utils import utc_now_iso

LOGGER = logging.getLogger(__name__)

OUTPUT_FILES = [
    "rainfall_daily_quality.json",
    "rainfall_matching_diagnostics.json",
    "event_antecedent_rainfall.csv",
    "rainfall_controls.csv",
    "rainfall_threshold_metrics.csv",
    "rainfall_sensitivity_summary.csv",
    "rainfall_primary_test_roc.csv",
    "rainfall_conditional_models.csv",
    "rainfall_resampled_validation.csv",
    "rainfall_season_stratified.csv",
    "rainfall_case_control_distributions.csv",
    "district_month_rainfall_association.csv",
    "inventory_reporting_composition.csv",
    "inventory_district_summary.csv",
    "inventory_province_summary.csv",
    "inventory_month_summary.csv",
    "rainfall_analysis_report.json",
    "rainfall_analysis_report.md",
    "rainfall_case_integrity_audit.csv",
    "rainfall_case_integrity_audit.json",
    "rainfall_case_integrity_audit_excludable_case_days.csv",
    "rainfall_integrity_sensitivity.json",
    "rainfall_results_figure.svg",
    "inventory_map_figure.svg",
    "rainfall_distributions_figure.svg",
    "rainfall_validation_figure.svg",
]
DOCUMENT_FILES = [
    "RAINFALL_ANALYSIS.md",
    "RAINFALL_MANUSCRIPT_DRAFT_V15.md",
    "RAINFALL_MANUSCRIPT_TABLES.md",
    "RAINFALL_CHANGELOG.md",
    "V15_PAPER_SUMMARY.md",
]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _copy_and_describe(source: Path, destination: Path) -> dict[str, object]:
    if not source.exists():
        raise FileNotFoundError(f"Rainfall release input is missing: {source}")
    shutil.copy2(source, destination)
    return {
        "file": destination.name,
        "bytes": destination.stat().st_size,
        "sha256": _sha256(destination),
    }


def run_rainfall_release_stage(config: AppConfig) -> None:
    """Copy the complete rainfall analysis into a locked release directory."""

    root = config.config_path.parent
    settings = dict(config.raw.get("analysis", {}))
    version = str(settings.get("release_version", "0.1.0"))
    release_date = str(settings.get("release_date", "20260813"))
    release_id = f"nepal_landslide_rainfall_v{version}_{release_date}"
    release_dir = root / "data" / "releases" / release_id
    release_dir.mkdir(parents=True, exist_ok=True)

    sources: list[tuple[Path, str]] = []
    output_dir = config.resolve_path("outputs_dir")
    sources.extend((output_dir / name, name) for name in OUTPUT_FILES)
    sources.extend((root / "docs" / name, name) for name in DOCUMENT_FILES)
    rainfall_path = root / str(
        settings.get("chirps_daily_district_path", "data/external/chirps_daily_districts.csv")
    )
    boundary_path = root / str(
        settings.get("district_boundaries_path", "data/reference/nepal_districts_77.geojson")
    )
    inventory_release_id = str(
        settings.get(
            "inventory_release_id",
            "nepal_landslide_inventory_v0.4.0_v6_20260810",
        )
    )
    inventory_manifest = (
        root
        / "data"
        / "releases"
        / inventory_release_id
        / "release_manifest.json"
    )
    sources.extend(
        [
            (rainfall_path, "chirps_daily_districts.csv"),
            (boundary_path, "nepal_districts_77.geojson"),
            (inventory_manifest, "inventory_release_manifest.json"),
        ]
    )
    files = [
        _copy_and_describe(source.resolve(), release_dir / destination)
        for source, destination in sources
    ]
    quality = json.loads((output_dir / "rainfall_daily_quality.json").read_text(encoding="utf-8"))
    report = json.loads((output_dir / "rainfall_analysis_report.json").read_text(encoding="utf-8"))
    inventory = json.loads(inventory_manifest.read_text(encoding="utf-8"))
    inventory_status = str(inventory.get("status", "unknown"))
    inventory_canonical_hash = inventory.get("canonical_summary", {}).get("sha256")
    analysis_canonical_hash = report.get("canonical_input_sha256")
    if not inventory_canonical_hash or inventory_canonical_hash != analysis_canonical_hash:
        raise ValueError(
            "Rainfall analysis canonical input does not match the configured "
            f"inventory release: analysis={analysis_canonical_hash}, "
            f"inventory={inventory_canonical_hash}"
        )
    lock_payload = "\n".join(f"{item['file']}:{item['sha256']}" for item in files)
    bundle_lock = hashlib.sha256(lock_payload.encode("utf-8")).hexdigest()
    manifest = {
        "release_id": release_id,
        "generated_at": utc_now_iso(),
        "status": (
            "analysis_complete_inventory_event_detection_validated"
            if inventory_status == "validated_event_detection_only"
            else "analysis_complete_inventory_candidate_pending_validation"
        ),
        "inventory_release": inventory_release_id,
        "inventory_validation_status": inventory_status,
        "rainfall_product": settings.get("rainfall_product", "UCSB CHIRPS v2.0 Final"),
        "analysis_period": {"start": quality["start"], "end": quality["end"]},
        "rainfall_rows": quality["rows"],
        "districts": quality["observed_districts"],
        "primary_cases": report["variants"]["primary_conf_ge_0.78"]["cases"],
        "primary_controls": report["variants"]["primary_conf_ge_0.78"]["controls"],
        "primary_temporal_test_result": report["primary_temporal_test_result"],
        "primary_selected_by_exposure": report.get("primary_selected_by_exposure", {}),
        "matching_diagnostics": report.get("matching_diagnostics", {}),
        "resampled_validation": report.get("resampled_validation", {}),
        "inputs": {
            "rainfall": {
                "path": report.get("rainfall_input"),
                "sha256": report.get("rainfall_input_sha256"),
            },
            "canonical_events": {
                "path": report.get("canonical_input"),
                "sha256": report.get("canonical_input_sha256"),
            },
        },
        "supersedes": settings.get("supersedes_release"),
        "checks": {
            "rainfall_coverage_complete": quality["coverage_fraction"] == 1.0,
            "all_77_districts_present": quality["observed_districts"] == 77,
            "no_incomplete_days": quality["incomplete_days"] == 0,
            "temporal_holdout_not_empty": report["primary_temporal_test_result"] is not None,
            "co_primary_present": "strictly_antecedent_excl_event_day"
            in report.get("primary_selected_by_exposure", {}),
            "input_paths_are_repository_relative": not str(
                report.get("rainfall_input", "")
            ).startswith("/"),
            "conditional_models_converged": all(
                bool(row.get("converged"))
                for row in report.get("conditional_models", [])
            ),
            "inventory_canonical_hash_matches": True,
            "inventory_fresh_event_detection_validation_complete": inventory.get(
                "checks", {}
            ).get("fresh_locked_event_detection_validation_complete", False),
            "inventory_fresh_full_record_validation_complete": inventory.get(
                "checks", {}
            ).get("fresh_locked_full_record_validation_complete", False),
        },
        "files": files,
        "bundle_lock_hash": bundle_lock,
        "notes": (
            f"This is an analysis release linked to {inventory_release_id}. "
            "It is not an operational landslide-warning threshold. The headline "
            "cutpoint uses a window that includes the reported event day; the "
            "strictly antecedent co-primary result bounds the signal available "
            "before failure. Read the single temporal-test AUC against the "
            "leave-one-year-out distribution in resampled_validation."
            " Exact-date accuracy did not pass the inventory validation threshold; "
            "interpret results with the confidence and +/-1/+/-3-day sensitivities."
        ),
    }
    (release_dir / "release_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    LOGGER.info("Rainfall analysis release written to %s; lock %s", release_dir, bundle_lock[:12])
