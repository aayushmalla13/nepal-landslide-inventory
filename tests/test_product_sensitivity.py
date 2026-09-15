"""Tests for the CHIRPS-vs-IMERG product sensitivity machinery.

Two scripts are covered:

* ``scripts/run_product_sensitivity.py`` -- derives the two run configs and
  truncates CHIRPS so that period is held fixed and only product varies.
* ``scripts/paired_product_auc.py`` -- compares discrimination between the two
  runs with a paired, district-clustered bootstrap.

The failure modes these guard against are both silent. A derived config that
drifts from the primary one reports a settings difference as a product effect.
A "paired" comparison run over two designs that are not actually paired reports
control-draw noise as a product effect.
"""

from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


def load(name: str):
    sys.path.insert(0, str(ROOT / "src"))
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def sensitivity():
    return load("run_product_sensitivity")


@pytest.fixture()
def paired():
    return load("paired_product_auc")


# ---------------------------------------------------------------------------
# Holding the period fixed
# ---------------------------------------------------------------------------


def test_truncation_keeps_the_end_date_itself(sensitivity, tmp_path) -> None:
    """An off-by-one here silently drops a day from the control run only."""

    source = tmp_path / "in.csv"
    with source.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["date", "district", "rain_mm", "source", "product_version"])
        for day in ("2025-09-29", "2025-09-30", "2025-10-01"):
            writer.writerow([day, "Kaski", "1.0", "s", "v"])

    kept, dropped = sensitivity.truncate_series(source, tmp_path / "out.csv", "2025-09-30")
    assert (kept, dropped) == (2, 1)
    days = [row["date"] for row in csv.DictReader((tmp_path / "out.csv").open())]
    assert days == ["2025-09-29", "2025-09-30"]


def test_series_end_reads_the_last_date_not_the_last_row(sensitivity, tmp_path) -> None:
    """The IMERG file is sorted by district then date, so the last row is not the last day."""

    source = tmp_path / "in.csv"
    with source.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["date", "district", "rain_mm", "source", "product_version"])
        writer.writerow(["2025-09-30", "Achham", "1.0", "s", "v"])
        writer.writerow(["2015-01-01", "Zzz", "1.0", "s", "v"])  # last row, earliest day
    assert sensitivity.series_end(source) == "2025-09-30"


# ---------------------------------------------------------------------------
# The derived configs
# ---------------------------------------------------------------------------


def test_a_derived_config_changes_only_what_identifies_the_product(sensitivity) -> None:
    """Any other changed analysis key would masquerade as a product effect."""

    primary = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    derived = sensitivity.derive_config(
        primary,
        rainfall_path="data/external/imerg_daily_districts.csv",
        rainfall_product="NASA IMERG Final Run v07",
        outputs_dir="data/sensitivity/product/imerg",
        label="imerg",
    )

    changed = {
        key
        for key in set(primary["analysis"]) | set(derived["analysis"])
        if primary["analysis"].get(key) != derived["analysis"].get(key)
    }
    assert changed <= sensitivity.OVERRIDDEN_ANALYSIS_KEYS, (
        f"a derived config changed {changed - sensitivity.OVERRIDDEN_ANALYSIS_KEYS}, "
        "which would show up in the result as a product difference"
    )
    # The settings that define the method must be inherited verbatim.
    for key in (
        "random_seed",
        "antecedent_windows_days",
        "min_date_confidence",
        "controls_per_event",
        "control_exclusion_buffer_days",
        "development_end",
        "bootstrap_iterations",
    ):
        assert derived["analysis"][key] == primary["analysis"][key]


def test_a_derived_config_is_not_mistakable_for_a_release(sensitivity) -> None:
    primary = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    derived = sensitivity.derive_config(
        primary,
        rainfall_path="x.csv",
        rainfall_product="X",
        outputs_dir="data/sensitivity/product/x",
        label="x",
    )
    assert derived["analysis"]["release_version"].startswith("sensitivity-")
    assert "supersedes_release" not in derived["analysis"]
    assert derived["paths"]["outputs_dir"] == "data/sensitivity/product/x"


def test_deriving_a_config_does_not_mutate_the_primary_one(sensitivity) -> None:
    primary = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    before = json.dumps(primary, sort_keys=True, default=str)
    sensitivity.derive_config(
        primary, rainfall_path="x.csv", rainfall_product="X", outputs_dir="d", label="x"
    )
    assert json.dumps(primary, sort_keys=True, default=str) == before


# ---------------------------------------------------------------------------
# The paired comparison
# ---------------------------------------------------------------------------


def make_records(
    n_districts: int = 12, per_district: int = 20, *, score_key: str = "r5_mm"
) -> list[dict[str, str]]:
    """A small paired design: half cases, half controls, in a fixed order."""

    import random

    rng = random.Random(11)
    records = []
    for d in range(n_districts):
        district = f"District{d:02d}"
        for i in range(per_district):
            label = 1 if i % 2 == 0 else 0
            # 2019 dates fall in development; 2024 dates in the temporal test.
            year = 2019 if i < per_district // 2 else 2024
            records.append(
                {
                    "record_id": f"{district}:{i}",
                    "matched_event_id": f"case:{district}:{i}",
                    "date": f"{year}-07-{(i % 28) + 1:02d}",
                    "district": district,
                    "label": str(label),
                    score_key: f"{rng.uniform(0, 100):.4f}",
                }
            )
    return records


def test_the_comparison_refuses_two_designs_that_are_not_the_same(paired) -> None:
    """The whole point of pairing is lost if the designs differ."""

    a = make_records()
    b = [dict(row) for row in a]
    b[7]["record_id"] = "somethingelse"
    with pytest.raises(paired.DesignMismatch, match="diverge at position 7"):
        paired.assert_same_design(a, b)

    with pytest.raises(paired.DesignMismatch, match="different record counts"):
        paired.assert_same_design(a, b[:-1])


def test_identical_products_give_a_zero_difference_and_an_interval_around_zero(
    paired,
) -> None:
    """The paired design must cancel; an unpaired bootstrap would not."""

    records = make_records()
    result = paired.paired_auc_difference(
        records, records, column="r5_mm", split="development", iterations=200, seed=7
    )
    assert result["auc_difference_b_minus_a"] == pytest.approx(0.0)
    assert result["difference_ci_low"] == pytest.approx(0.0)
    assert result["difference_ci_high"] == pytest.approx(0.0)
    assert result["interval_excludes_zero"] is False


def test_a_strictly_better_product_is_detected(paired) -> None:
    """Product B is informative about the label; product A is noise."""

    import random

    rng = random.Random(3)
    a = make_records()
    b = []
    for row in a:
        copy = dict(row)
        # B separates cases from controls; A does not.
        copy["r5_mm"] = f"{rng.uniform(50, 100) if row['label'] == '1' else rng.uniform(0, 50):.4f}"
        b.append(copy)

    result = paired.paired_auc_difference(
        a, b, column="r5_mm", split="development", iterations=300, seed=7
    )
    assert result["auc_difference_b_minus_a"] > 0.2
    assert result["difference_ci_low"] > 0
    assert result["interval_excludes_zero"] is True
    assert result["share_of_iterations_favouring_b"] == pytest.approx(1.0)


def test_the_bootstrap_resamples_districts_not_records(paired, monkeypatch) -> None:
    """Records within a district are not independent; clustering must be honoured."""

    records = make_records(n_districts=6, per_district=10)
    result = paired.paired_auc_difference(
        records, records, column="r5_mm", split="development", iterations=50, seed=1
    )
    assert result["n_districts"] == 6
    # Every drawn cluster contributes all of its records, so a resample is a
    # multiple of the per-district block size rather than an arbitrary count.
    assert result["n"] == 6 * 5, "five development rows per district"


def test_the_comparison_is_deterministic_under_a_fixed_seed(paired) -> None:
    a = make_records()
    b = [dict(row, r5_mm=f"{float(row['r5_mm']) * 1.15:.4f}") for row in a]
    first = paired.paired_auc_difference(
        a, b, column="r5_mm", split="development", iterations=120, seed=20260904
    )
    second = paired.paired_auc_difference(
        a, b, column="r5_mm", split="development", iterations=120, seed=20260904
    )
    assert first == second


def test_a_monotone_rescaling_does_not_change_discrimination(paired) -> None:
    """AUC is rank-based, so a uniformly wetter product is not a better one.

    This is the distinction the whole analysis turns on: if IMERG were only
    CHIRPS x 1.15, the cutpoint would move and the AUC would not.
    """

    a = make_records()
    b = [dict(row, r5_mm=f"{float(row['r5_mm']) * 1.152:.6f}") for row in a]
    result = paired.paired_auc_difference(
        a, b, column="r5_mm", split="temporal_test", iterations=100, seed=5
    )
    assert result["auc_difference_b_minus_a"] == pytest.approx(0.0, abs=1e-9)


def test_the_split_boundary_matches_the_configured_development_end(paired) -> None:
    assert paired.DEV_END == "2022-12-31"
    assert paired.split_of({"date": "2022-12-31"}) == "development"
    assert paired.split_of({"date": "2023-01-01"}) == "temporal_test"


# ---------------------------------------------------------------------------
# The committed artefacts
# ---------------------------------------------------------------------------

SUMMARY = ROOT / "data" / "outputs" / "rainfall_product_sensitivity.json"
PAIRED = ROOT / "data" / "outputs" / "rainfall_product_paired_auc.json"


@pytest.mark.skipif(not SUMMARY.exists(), reason="sensitivity not run in this checkout")
def test_the_committed_runs_cover_the_same_period_and_the_same_design() -> None:
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    control = summary["runs"]["chirps_truncated"]
    test = summary["runs"]["imerg"]
    assert control["available_rainfall_end"] == test["available_rainfall_end"], (
        "period must be held fixed; otherwise product and period are confounded"
    )
    for field in ("development_n_cases", "development_n_controls", "test_n_cases", "test_n_controls"):
        assert control[field] == test[field], f"{field} differs, so the runs are not paired"
    assert control["rainfall_input_sha256"] != test["rainfall_input_sha256"], (
        "the two runs must actually use different rainfall inputs"
    )


@pytest.mark.skipif(not PAIRED.exists(), reason="paired comparison not run in this checkout")
def test_the_committed_paired_comparison_reports_every_window_and_both_splits() -> None:
    result = json.loads(PAIRED.read_text(encoding="utf-8"))
    for window in (1, 3, 5, 7):
        for split in ("development", "temporal_test"):
            key = f"R{window}_{split}"
            assert key in result["comparisons"], f"missing {key}"
            stats = result["comparisons"][key]
            assert stats["difference_ci_low"] <= stats["auc_difference_b_minus_a"]
            assert stats["auc_difference_b_minus_a"] <= stats["difference_ci_high"]
