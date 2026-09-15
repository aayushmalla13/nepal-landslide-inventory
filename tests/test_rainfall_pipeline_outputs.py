"""End-to-end checks on the rainfall analysis stage outputs.

These run the whole stage on a small synthetic study area, so they verify the
contract of the emitted files -- roles, columns, provenance and reproducibility
-- without depending on the real 24 MB rainfall input.
"""

from __future__ import annotations

import csv
import json
from datetime import date, timedelta
from pathlib import Path

import pytest
import yaml

from landslide_inventory.analysis.figures import run_rainfall_figures_stage
from landslide_inventory.analysis.pipeline import (
    ANTECEDENT,
    CONCURRENT,
    PRIMARY_VARIANT,
    run_rainfall_analysis_stage,
)
from landslide_inventory.config import load_config

DISTRICTS = ("Achham", "Baglung", "Chitwan", "Dhading", "Gorkha", "Kaski")
START = date(2019, 1, 1)
END = date(2024, 12, 31)


def _rain_for(district: str, day: date) -> float:
    """Deterministic pseudo-rainfall with a monsoon season and district offsets."""

    seasonal = 12.0 if day.month in (6, 7, 8, 9) else 1.0
    wobble = ((day.toordinal() * 7 + len(district) * 13) % 23) / 4.0
    return round(seasonal * (0.5 + wobble / 10.0), 4)


def _write_rainfall(path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["date", "district", "rain_mm"])
        day = START
        while day <= END:
            for district in DISTRICTS:
                writer.writerow([day.isoformat(), district, _rain_for(district, day)])
            day += timedelta(days=1)


def _write_events(path: Path) -> None:
    """Place events on the wettest day of each month so a signal exists."""

    columns = [
        "event_id",
        "event_date_ad",
        "district",
        "province",
        "conf_date",
        "event_type",
        "trigger",
        "event_granularity",
        "representative_source",
    ]
    rows = []
    counter = 0
    for year in range(2019, 2025):
        for month in (5, 6, 7, 8, 9, 10):
            for index, district in enumerate(DISTRICTS):
                candidates = []
                day = date(year, month, 1)
                while day.month == month:
                    candidates.append((_rain_for(district, day), day))
                    day += timedelta(days=1)
                candidates.sort(reverse=True)
                chosen = candidates[index % 3][1]
                counter += 1
                rows.append(
                    {
                        "event_id": f"event_{counter}",
                        "event_date_ad": chosen.isoformat(),
                        "district": district,
                        "province": "Test",
                        "conf_date": "0.88" if counter % 5 else "0.60",
                        "event_type": "road_obstruction" if counter % 7 == 0 else "landslide",
                        "trigger": "earthquake" if counter % 23 == 0 else "rainfall",
                        "event_granularity": "single",
                        "representative_source": "steady" if counter % 2 else "shifting",
                    }
                )
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _base_config() -> dict:
    """Reuse the repository's own valid config skeleton for the stage test."""

    import tests.conftest as conftest  # noqa: PLC0415

    return conftest.config_payload.__wrapped__()


@pytest.fixture(scope="module")
def analysis_root(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("rainfall_stage")
    (root / "data" / "external").mkdir(parents=True)
    (root / "data" / "outputs").mkdir(parents=True)
    (root / "data" / "reference").mkdir(parents=True)
    (root / "resources").mkdir()
    with (root / "resources" / "districts_en.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["district", "province", "variants_en"])
        for district in DISTRICTS:
            writer.writerow([district, "Test", district])
    _write_rainfall(root / "data" / "external" / "chirps_daily_districts.csv")
    _write_events(root / "data" / "outputs" / "canonical_events_final.csv")
    (root / "data" / "reference" / "nepal_districts_77.geojson").write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"DISTRICT": district.upper()},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [
                                [
                                    [80.0 + index, 28.0],
                                    [80.5 + index, 28.0],
                                    [80.5 + index, 28.5],
                                    [80.0 + index, 28.5],
                                    [80.0 + index, 28.0],
                                ]
                            ],
                        },
                    }
                    for index, district in enumerate(DISTRICTS)
                ],
            }
        ),
        encoding="utf-8",
    )
    config = _base_config()
    config["paths"]["outputs_dir"] = "data/outputs"
    config["analysis"] = {
            "chirps_daily_district_path": "data/external/chirps_daily_districts.csv",
            "district_boundaries_path": "data/reference/nepal_districts_77.geojson",
            "canonical_events_path": "data/outputs/canonical_events_final.csv",
            "antecedent_windows_days": [1, 3, 5],
            "min_date_confidence": 0.78,
            "high_date_confidence": 0.80,
            "controls_per_event": 3,
            "control_exclusion_buffer_days": 7,
            "development_end": "2022-12-31",
            "bootstrap_iterations": 20,
            "random_seed": 20260814,
            "balanced_panel_min_events": 5,
    }
    (root / "config.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")
    run_rainfall_analysis_stage(load_config(root / "config.yaml", allow_placeholder=True))
    return root


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_report_records_relative_paths_and_input_checksums(analysis_root: Path) -> None:
    report = json.loads(
        (analysis_root / "data" / "outputs" / "rainfall_analysis_report.json").read_text()
    )
    assert report["rainfall_input"] == "data/external/chirps_daily_districts.csv"
    assert report["canonical_input"] == "data/outputs/canonical_events_final.csv"
    assert not Path(report["rainfall_input"]).is_absolute()
    assert len(report["rainfall_input_sha256"]) == 64
    assert len(report["canonical_input_sha256"]) == 64


def test_report_declares_analysis_roles_including_what_is_not_reported(
    analysis_root: Path,
) -> None:
    report = json.loads(
        (analysis_root / "data" / "outputs" / "rainfall_analysis_report.json").read_text()
    )
    roles = report["analysis_roles"]
    assert "co_primary" in roles
    assert "calibration" in roles["not_reported"]
    assert "decision-curve" in roles["not_reported"]


def test_metrics_cover_both_exposures_and_label_the_threshold_split(
    analysis_root: Path,
) -> None:
    rows = _rows(analysis_root / "data" / "outputs" / "rainfall_threshold_metrics.csv")
    exposures = {row["exposure"] for row in rows}
    assert exposures == {CONCURRENT, ANTECEDENT}
    assert all(row["threshold_fitted_on"] == "development" for row in rows)
    with_interval = [row for row in rows if row["threshold_ci_low"]]
    assert with_interval, "the primary variant must carry a bootstrap threshold interval"
    assert all(row["threshold_ci_split"] == "development" for row in with_interval)
    assert all(row["variant"] == PRIMARY_VARIANT for row in with_interval)


def test_threshold_is_fitted_on_development_and_reused_in_the_test_split(
    analysis_root: Path,
) -> None:
    """Guards against retuning on the holdout: one cutpoint per variant/window."""

    rows = _rows(analysis_root / "data" / "outputs" / "rainfall_threshold_metrics.csv")
    grouped: dict[tuple[str, str, str], set[str]] = {}
    for row in rows:
        key = (row["variant"], row["exposure"], row["window_days"])
        grouped.setdefault(key, set()).add(row["threshold_mm"])
    assert all(len(values) == 1 for values in grouped.values())


def test_sensitivity_summary_includes_the_new_prespecified_variants(
    analysis_root: Path,
) -> None:
    rows = _rows(analysis_root / "data" / "outputs" / "rainfall_sensitivity_summary.csv")
    variants = {row["variant"] for row in rows}
    assert "balanced_source_panel" in variants
    assert "strict_matched_sets" in variants
    assert {row["exposure"] for row in rows} == {CONCURRENT, ANTECEDENT}
    assert all(row["development_auc"] for row in rows)


def test_matching_diagnostics_are_emitted(analysis_root: Path) -> None:
    diagnostics = json.loads(
        (analysis_root / "data" / "outputs" / "rainfall_matching_diagnostics.json").read_text()
    )
    assert diagnostics["strata"] > 0
    assert diagnostics["control_rows"] >= diagnostics["distinct_control_district_days"]
    assert 0.0 <= diagnostics["duplicate_control_row_fraction"] <= 1.0
    assert 0.0 <= diagnostics["strata_without_controls_fraction"] <= 1.0


def test_conditional_models_report_an_odds_ratio_and_never_an_absolute_risk(
    analysis_root: Path,
) -> None:
    rows = _rows(analysis_root / "data" / "outputs" / "rainfall_conditional_models.csv")
    assert rows
    assert {row["split"] for row in rows} == {"all_years", "development", "temporal_test"}
    for row in rows:
        low = float(row["odds_ratio_ci_low"])
        high = float(row["odds_ratio_ci_high"])
        assert low <= float(row["odds_ratio_per_10mm"]) <= high
        assert float(row["within_stratum_concordance"]) >= 0.0
    header = set(rows[0])
    assert not header & {"absolute_risk", "calibration_slope", "net_benefit"}


def test_resampled_validation_covers_years_and_district_folds(analysis_root: Path) -> None:
    rows = _rows(analysis_root / "data" / "outputs" / "rainfall_resampled_validation.csv")
    schemes = {row["scheme"] for row in rows}
    assert schemes == {"leave_one_year_out", "spatial_holdout"}
    assert {row["exposure"] for row in rows} == {CONCURRENT, ANTECEDENT}
    years = {row["fold"] for row in rows if row["scheme"] == "leave_one_year_out"}
    assert len(years) >= 5


def test_season_stratification_separates_monsoon_from_the_rest_of_the_year(
    analysis_root: Path,
) -> None:
    rows = _rows(analysis_root / "data" / "outputs" / "rainfall_season_stratified.csv")
    assert {row["season"] for row in rows} == {"monsoon_JJAS", "non_monsoon"}


def test_reporting_composition_flags_publishers_present_in_only_one_period(
    analysis_root: Path,
) -> None:
    rows = _rows(analysis_root / "data" / "outputs" / "inventory_reporting_composition.csv")
    assert rows
    assert {"development_events", "temporal_test_events"} <= set(rows[0])
    assert any(row["source"] == "steady" for row in rows)


def test_descriptive_tables_are_written(analysis_root: Path) -> None:
    outputs = analysis_root / "data" / "outputs"
    district = _rows(outputs / "inventory_district_summary.csv")
    assert {row["district"] for row in district} == set(DISTRICTS)
    assert _rows(outputs / "inventory_province_summary.csv")
    months = _rows(outputs / "inventory_month_summary.csv")
    assert len(months) == 12
    distributions = _rows(outputs / "rainfall_case_control_distributions.csv")
    assert {row["group"] for row in distributions} == {"case", "control"}
    assert {row["period"] for row in distributions} == {
        "all_years",
        "development",
        "temporal_test",
    }


def test_emitted_numbers_are_rounded_so_release_hashes_reproduce(
    analysis_root: Path,
) -> None:
    rows = _rows(analysis_root / "data" / "outputs" / "event_antecedent_rainfall.csv")
    for row in rows[:50]:
        for key, value in row.items():
            if key.endswith("_mm") and value:
                decimals = value.split(".")[1] if "." in value else ""
                assert len(decimals) <= 6, f"{key}={value} is not rounded for emission"


def test_stage_is_deterministic_when_rerun(analysis_root: Path, tmp_path: Path) -> None:
    outputs = analysis_root / "data" / "outputs"
    before = {
        name: (outputs / name).read_text(encoding="utf-8")
        for name in (
            "rainfall_threshold_metrics.csv",
            "rainfall_sensitivity_summary.csv",
            "rainfall_conditional_models.csv",
            "rainfall_resampled_validation.csv",
        )
    }
    run_rainfall_analysis_stage(load_config(analysis_root / "config.yaml", allow_placeholder=True))
    for name, content in before.items():
        assert (outputs / name).read_text(encoding="utf-8") == content


def test_figures_render_from_the_analysis_outputs(analysis_root: Path) -> None:
    run_rainfall_figures_stage(load_config(analysis_root / "config.yaml", allow_placeholder=True))
    outputs = analysis_root / "data" / "outputs"
    for name in (
        "rainfall_results_figure.svg",
        "inventory_map_figure.svg",
        "rainfall_distributions_figure.svg",
        "rainfall_validation_figure.svg",
    ):
        svg = (outputs / name).read_text(encoding="utf-8")
        assert svg.startswith("<svg")
        assert svg.rstrip().endswith("</svg>")
