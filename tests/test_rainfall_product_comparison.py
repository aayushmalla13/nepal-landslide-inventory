"""Tests for the CHIRPS-IMERG product comparison.

The comparison exists to answer whether the cutpoint is a property of Nepali
landslides or of CHIRPS. It can only answer that if it is computed on identical
district-days: CHIRPS runs ten months past the end of the IMERG Final record,
and those ten months are a seasonally non-random slice. A comparison over the
union of the two records would report a difference that is partly period and
report it as though it were product.

These tests pin that restriction, and the statistics that rest on it.
"""

from __future__ import annotations

import csv
import importlib.util
import math
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load_module():
    sys.path.insert(0, str(ROOT / "src"))
    spec = importlib.util.spec_from_file_location(
        "compare_rainfall_products", ROOT / "scripts" / "compare_rainfall_products.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def compare():
    return load_module()


def write_series(path: Path, values: dict[tuple[str, date], float], label: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["date", "district", "rain_mm", "source", "product_version"])
        for (district, day), value in sorted(values.items(), key=lambda item: item[0][::-1]):
            writer.writerow([day.isoformat(), district, f"{value:.6f}", "test", label])


def constant_series(
    districts: list[str], start: date, days: int, value_for
) -> dict[tuple[str, date], float]:
    return {
        (district, start + timedelta(days=offset)): value_for(district, offset)
        for district in districts
        for offset in range(days)
    }


# ---------------------------------------------------------------------------
# The restriction to common support
# ---------------------------------------------------------------------------


def test_the_comparison_uses_only_district_days_present_in_both_products(
    compare, tmp_path
) -> None:
    """The central guarantee. A longer record must not widen the comparison."""

    districts = ["Kaski", "Dolakha", "Rasuwa", "Sindhupalchok"]
    start = date(2020, 1, 1)
    # Product A runs 400 days; the last 100 are torrential and have no
    # counterpart in B. If they leak in, every statistic below shifts.
    a_values = constant_series(
        districts, start, 400, lambda district, offset: 5.0 if offset < 300 else 500.0
    )
    b_values = constant_series(districts, start, 300, lambda district, offset: 6.0)
    write_series(tmp_path / "a.csv", a_values, "A")
    write_series(tmp_path / "b.csv", b_values, "B")

    result = compare.compare_products(
        tmp_path / "a.csv",
        tmp_path / "b.csv",
        windows=[1, 5],
        cutpoint_mm=25.0,
        cutpoint_window=5,
        label_a="A",
        label_b="B",
    )

    overlap = result["overlap"]
    assert overlap["common_district_days"] == 1200, "300 days x 4 districts"
    assert overlap["common_end"] == "2020-10-26"
    assert overlap["district_days_only_in_a"] == 400

    daily = result["by_exposure"]["daily"]
    assert daily["n"] == 1200
    assert daily["mean_a"] == pytest.approx(5.0), (
        "the 500 mm tail must not enter the comparison at all"
    )
    assert daily["mean_b"] == pytest.approx(6.0)
    assert daily["ratio_of_means_b_over_a"] == pytest.approx(1.2)


def test_a_thin_overlap_is_reported_rather_than_summarised(compare, tmp_path) -> None:
    """Ten district-days is not evidence about a product."""

    districts = ["Kaski"]
    a_values = constant_series(districts, date(2020, 1, 1), 10, lambda d, o: 1.0)
    b_values = constant_series(districts, date(2020, 1, 1), 10, lambda d, o: 2.0)
    write_series(tmp_path / "a.csv", a_values, "A")
    write_series(tmp_path / "b.csv", b_values, "B")

    result = compare.compare_products(
        tmp_path / "a.csv",
        tmp_path / "b.csv",
        windows=[1],
        cutpoint_mm=25.0,
        cutpoint_window=1,
        label_a="A",
        label_b="B",
    )
    assert result["insufficient_overlap"] is True
    assert "by_exposure" not in result, "no statistics may be reported on a thin overlap"
    assert "too small to support a comparison" in compare.markdown_report(result)


def test_common_support_is_an_intersection_not_a_date_range(compare) -> None:
    """A district missing from one product must drop out, not be range-filled."""

    a = {("Kaski", date(2020, 1, 1)): 1.0, ("Mustang", date(2020, 1, 1)): 1.0}
    b = {("Kaski", date(2020, 1, 1)): 2.0}
    assert compare.common_support(a, b) == [("Kaski", date(2020, 1, 1))]


# ---------------------------------------------------------------------------
# Window accumulation must not silently shorten
# ---------------------------------------------------------------------------


def test_an_incomplete_window_is_dropped_not_partially_summed(compare) -> None:
    """A five-day total built from three days would understate the exposure."""

    start = date(2020, 1, 1)
    values = {("Kaski", start + timedelta(days=offset)): 10.0 for offset in range(5)}
    keys = [("Kaski", start + timedelta(days=offset)) for offset in range(5)]
    series = compare.window_series(values, keys, 5)
    assert series[:4] == [None, None, None, None], "the first four days lack history"
    assert series[4] == pytest.approx(50.0)


def test_a_position_is_dropped_when_either_product_lacks_the_window(compare) -> None:
    a_series = [1.0, None, 3.0, 4.0]
    b_series = [1.0, 2.0, None, 4.0]
    a_out, b_out, kept = compare.paired(a_series, b_series)
    assert a_out == [1.0, 4.0]
    assert b_out == [1.0, 4.0]
    assert kept == [0, 3]


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------


def test_exceedance_agreement_counts_the_four_cells_correctly(compare) -> None:
    a = [10.0, 60.0, 60.0, 10.0]
    b = [10.0, 60.0, 10.0, 60.0]
    stats = compare.agreement_statistics(a, b, cutpoint_mm=51.6)
    exceedance = stats["exceedance"]
    assert exceedance["both"] == 1
    assert exceedance["a_only"] == 1
    assert exceedance["b_only"] == 1
    assert exceedance["neither"] == 1
    assert exceedance["percent_agreement"] == pytest.approx(0.5)


def test_kappa_is_undefined_rather_than_perfect_when_no_one_ever_exceeds(compare) -> None:
    """Reporting kappa = 1.0 here would claim agreement no data supports."""

    flags = [0, 0, 0, 0]
    assert math.isnan(compare.cohen_kappa(flags, flags))


def test_kappa_is_zero_for_independent_calls(compare) -> None:
    a_flags = [1, 1, 0, 0]
    b_flags = [1, 0, 1, 0]
    assert compare.cohen_kappa(a_flags, b_flags) == pytest.approx(0.0)


def test_a_uniform_scaling_shows_up_as_a_constant_ratio_of_means(compare, tmp_path) -> None:
    """The signature this comparison is designed to detect.

    If product B is product A times a constant, the ratio of means is that
    constant at *every* window and the rank correlation is 1. Real products
    never look exactly like this, but the closer they do, the more a shifted
    cutpoint is a units difference rather than a different physical signal.
    """

    import random

    rng = random.Random(20260904)  # deterministic: a fixed seed, per the project rules
    districts = ["Kaski", "Dolakha", "Rasuwa"]
    start = date(2020, 1, 1)
    a_values = {
        (district, start + timedelta(days=offset)): rng.expovariate(1 / 5.0)
        for district in districts
        for offset in range(400)
    }
    b_values = {key: value * 1.15 for key, value in a_values.items()}
    write_series(tmp_path / "a.csv", a_values, "A")
    write_series(tmp_path / "b.csv", b_values, "B")

    result = compare.compare_products(
        tmp_path / "a.csv",
        tmp_path / "b.csv",
        windows=[1, 3, 5, 7],
        cutpoint_mm=25.0,
        cutpoint_window=5,
        label_a="A",
        label_b="B",
    )
    for name in ("R1", "R3", "R5", "R7"):
        stats = result["by_exposure"][name]
        assert stats["ratio_of_means_b_over_a"] == pytest.approx(1.15, abs=0.001)
        assert stats["spearman"] == pytest.approx(1.0, abs=1e-9)


def test_sparse_support_districts_are_flagged_and_reported_separately(
    compare, tmp_path
) -> None:
    districts = ["Kaski", "Bhaktapur", "Kathmandu"]
    a_values = constant_series(districts, date(2020, 1, 1), 400, lambda d, o: 5.0)
    b_values = constant_series(
        districts,
        date(2020, 1, 1),
        400,
        lambda d, o: 50.0 if d in ("Bhaktapur", "Kathmandu") else 5.0,
    )
    write_series(tmp_path / "a.csv", a_values, "A")
    write_series(tmp_path / "b.csv", b_values, "B")

    result = compare.compare_products(
        tmp_path / "a.csv",
        tmp_path / "b.csv",
        windows=[5],
        cutpoint_mm=25.0,
        cutpoint_window=5,
        label_a="A",
        label_b="B",
    )
    per_district = result["per_district_at_cutpoint_window"]["districts"]
    assert per_district["Bhaktapur"]["sparse_grid_support"] is True
    assert per_district["Kaski"]["sparse_grid_support"] is False

    # With the two sparse districts removed, the remaining product agrees exactly.
    dense = result["excluding_sparse_support_districts"]
    assert dense["ratio_of_means_b_over_a"] == pytest.approx(1.0)
    assert result["by_exposure"]["R5"]["ratio_of_means_b_over_a"] > 1.0, (
        "the full comparison must still include them, not quietly drop them"
    )


# ---------------------------------------------------------------------------
# The generated report
# ---------------------------------------------------------------------------


def test_the_generated_report_states_the_common_support_and_is_marked_generated(
    compare, tmp_path
) -> None:
    districts = ["Kaski", "Dolakha", "Rasuwa", "Sindhupalchok"]
    a_values = constant_series(districts, date(2020, 1, 1), 400, lambda d, o: 5.0)
    b_values = constant_series(districts, date(2020, 1, 1), 300, lambda d, o: 6.0)
    write_series(tmp_path / "a.csv", a_values, "A")
    write_series(tmp_path / "b.csv", b_values, "B")
    result = compare.compare_products(
        tmp_path / "a.csv",
        tmp_path / "b.csv",
        windows=[1, 5],
        cutpoint_mm=25.0,
        cutpoint_window=5,
        label_a="A",
        label_b="B",
    )
    report = compare.markdown_report(result)
    assert "do not edit by hand" in report
    assert "Common support" in report
    assert "1,200 district-days" in report
    assert "aggregation" in report.lower(), "the aggregation caveat must survive into the report"


def test_the_committed_comparison_was_computed_on_the_common_support_only() -> None:
    """Guard the artefact itself, not just the code that made it."""

    import json

    path = ROOT / "data" / "outputs" / "rainfall_product_comparison.json"
    if not path.exists():
        pytest.skip("comparison not generated in this checkout")
    result = json.loads(path.read_text(encoding="utf-8"))
    overlap = result["overlap"]
    assert result["comparison_is_restricted_to_common_support"] is True
    assert overlap["common_end"] == overlap["product_b"]["end"], (
        "the comparison must end where the shorter product ends"
    )
    assert overlap["common_district_days"] == overlap["product_b"]["district_days"]
    assert overlap["district_days_only_in_a"] > 0, (
        "CHIRPS runs past IMERG; if this is zero the truncation was applied to the "
        "wrong file and the comparison is not testing what it claims"
    )
