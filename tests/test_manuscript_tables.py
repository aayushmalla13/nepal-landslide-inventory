"""The generated manuscript tables must agree with the analysis report.

The tables document used to be maintained by hand and had drifted a whole
release behind by v0.5.0 — it still quoted a 45.4 mm cutpoint. Generating it
removes that drift, but only if the generator reads the right rows: the metrics
CSV holds every sensitivity variant, and an unfiltered read silently reported
whichever variant happened to come last.
"""

from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "data" / "outputs"
REPORT = OUTPUTS / "rainfall_analysis_report.json"
METRICS = OUTPUTS / "rainfall_threshold_metrics.csv"

pytestmark = pytest.mark.skipif(
    not (REPORT.exists() and METRICS.exists()),
    reason="analysis outputs are not present in this checkout",
)


def load_builder():
    sys.path.insert(0, str(ROOT / "src"))
    spec = importlib.util.spec_from_file_location(
        "manuscript_tables", ROOT / "scripts" / "build_manuscript_tables.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_the_window_table_reports_the_primary_variant_not_a_sensitivity_run() -> None:
    builder = load_builder()
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    with METRICS.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    primary = report["primary_selected_by_exposure"][builder.CONCURRENT]
    expected_threshold = primary["temporal_test"]["threshold_mm"]
    expected_auc = primary["temporal_test"]["auc"]

    selected = None
    for row in rows:
        if (
            row["split"] == "temporal_test"
            and row["exposure"] == builder.CONCURRENT
            and row["variant"] == builder.PRIMARY_VARIANT
            and abs(float(row["threshold_mm"]) - expected_threshold) < 1e-6
        ):
            selected = int(float(row["window_days"]))
    assert selected is not None, "the primary window must be identifiable in the metrics file"

    table = "\n".join(builder.window_table(rows, builder.CONCURRENT, selected))
    assert f"**{selected} days (selected)**" in table
    assert f"{expected_threshold:.1f}" in table
    assert f"{expected_auc:.3f}" in table

    # A sensitivity variant with a different threshold must not appear in the
    # selected row -- this is exactly the bug the filter prevents.
    other_thresholds = {
        round(float(row["threshold_mm"]), 6)
        for row in rows
        if row["split"] == "temporal_test"
        and row["exposure"] == builder.CONCURRENT
        and row["variant"] != builder.PRIMARY_VARIANT
        and int(float(row["window_days"])) == selected
        and abs(float(row["threshold_mm"]) - expected_threshold) > 1e-6
    }
    selected_line = next(
        line for line in table.splitlines() if "(selected)" in line
    )
    for value in other_thresholds:
        assert f"| {value:.1f} |" not in selected_line


def test_every_window_row_comes_from_one_variant() -> None:
    builder = load_builder()
    with METRICS.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    table = builder.window_table(rows, builder.CONCURRENT, None)
    # header + separator + one row per distinct window in the primary variant
    windows = {
        int(float(row["window_days"]))
        for row in rows
        if row["exposure"] == builder.CONCURRENT and row["variant"] == builder.PRIMARY_VARIANT
    }
    assert len(table) == 2 + len(windows)


def test_the_generated_file_is_marked_as_generated() -> None:
    path = ROOT / "docs" / "RAINFALL_MANUSCRIPT_TABLES.md"
    if not path.exists():
        pytest.skip("tables not generated in this checkout")
    head = path.read_text(encoding="utf-8")[:400]
    assert "do not edit by hand" in head.lower()


def test_the_manuscript_identifies_and_summarizes_the_current_release() -> None:
    """Guard the hand-written narrative against release-level number drift."""

    import yaml

    draft_path = ROOT / "docs" / "RAINFALL_MANUSCRIPT_DRAFT_V15.md"
    if not draft_path.exists():
        pytest.skip("manuscript draft absent in this checkout")
    draft = draft_path.read_text(encoding="utf-8")
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    settings = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))["analysis"]
    version = str(settings["release_version"])
    release_date = str(settings["release_date"])
    release_id = f"nepal_landslide_rainfall_v{version}_{release_date}"

    concurrent = report["primary_selected_by_exposure"]["concurrent_incl_event_day"]
    development = concurrent["development"]
    temporal_test = concurrent["temporal_test"]

    assert f"**Analysis version:** {version}" in draft
    assert f"`{release_id}`" in draft
    assert (
        f"The primary development sample contained {development['n_cases']:,} case-days "
        f"and {development['n_controls']:,} matched controls."
    ) in draft
    assert (
        f"The temporal test set contained {temporal_test['n_cases']:,} case-days "
        f"and {temporal_test['n_controls']:,} controls."
    ) in draft
    assert f"{temporal_test['threshold_mm']:.1f} mm threshold" in draft
    assert f"Test AUC was {temporal_test['auc']:.3f}" in draft
