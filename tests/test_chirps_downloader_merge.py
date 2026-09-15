"""The CHIRPS downloader must extend the series, never truncate it.

Regression: an incremental run with ``--start 2026-06-01`` replaced a
2015-2026 file holding 323,323 district-day rows with the 4,697 rows of the
requested window. The output opened with mode ``"w"`` and only the fetched rows
were written. Nothing warned; eleven years of matched controls simply vanished,
and the loss would only surface as an unexplained drop in case count.
"""

from __future__ import annotations

import csv
import importlib.util
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load_downloader():
    sys.path.insert(0, str(ROOT / "src"))
    spec = importlib.util.spec_from_file_location(
        "chirps_downloader", ROOT / "scripts" / "download_chirps_climateserv.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_series(path: Path, rows: list[tuple[str, str, str]]) -> None:
    columns = ["date", "district", "rain_mm", "source", "product_version"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for day, district, rain in rows:
            writer.writerow(
                {
                    "date": day,
                    "district": district,
                    "rain_mm": rain,
                    "source": "NASA SERVIR ClimateSERV",
                    "product_version": "UCSB CHIRPS v2.0 Final",
                }
            )


def read_series(path: Path) -> dict[tuple[str, str], str]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return {(row["date"], row["district"]): row["rain_mm"] for row in csv.DictReader(handle)}


@pytest.fixture()
def downloader():
    return load_downloader()


def run_write(module, output_path: Path, results, replace: bool = False):
    """Call the shipped function, so the test covers the code that runs."""

    return module.merge_and_write(output_path, results, replace=replace)


def test_the_writer_merges_rather_than_truncating(downloader, tmp_path: Path) -> None:
    output = tmp_path / "chirps_daily_districts.csv"
    write_series(
        output,
        [("2015-01-01", "Kaski", "1.000000"), ("2015-01-02", "Kaski", "2.000000")],
    )
    run_write(downloader, output, {"Kaski": [(date(2026, 7, 1), 9.5)]})

    series = read_series(output)
    assert ("2015-01-01", "Kaski") in series, "the historical series must survive"
    assert ("2015-01-02", "Kaski") in series
    assert series[("2026-07-01", "Kaski")] == "9.500000"
    assert len(series) == 3


def test_a_refetched_day_replaces_the_stored_value(downloader, tmp_path: Path) -> None:
    """So a Prelim day later superseded by Final is corrected by re-running."""

    output = tmp_path / "chirps_daily_districts.csv"
    write_series(output, [("2026-07-01", "Kaski", "1.000000")])
    run_write(downloader, output, {"Kaski": [(date(2026, 7, 1), 4.25)]})

    series = read_series(output)
    assert series == {("2026-07-01", "Kaski"): "4.250000"}


def test_replace_discards_the_existing_series_only_when_asked(
    downloader, tmp_path: Path
) -> None:
    output = tmp_path / "chirps_daily_districts.csv"
    write_series(output, [("2015-01-01", "Kaski", "1.000000")])
    run_write(downloader, output, {"Kaski": [(date(2026, 7, 1), 9.5)]}, replace=True)

    series = read_series(output)
    assert ("2015-01-01", "Kaski") not in series
    assert len(series) == 1


def test_the_parser_defaults_to_merging(downloader) -> None:
    args = downloader.build_parser().parse_args([])
    assert args.replace is False
