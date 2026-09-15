"""Tests for the IMERG district-mean downloader.

The network path cannot be exercised here (the analysis environment has no route
to GES DISC, and the download needs a credential). Everything that decides
*which numbers end up in which district* is pure and is tested: the
point-in-polygon assignment, the OPeNDAP ASCII parser, the aggregation, and the
merge-not-truncate writer.
"""

from __future__ import annotations

import csv
import importlib.util
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BOUNDARIES = ROOT / "data" / "reference" / "nepal_districts_77.geojson"


def load_module():
    sys.path.insert(0, str(ROOT / "src"))
    spec = importlib.util.spec_from_file_location(
        "imerg_gesdisc", ROOT / "scripts" / "download_imerg_gesdisc.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def imerg():
    return load_module()


SQUARE = [[[0.0, 0.0], [2.0, 0.0], [2.0, 2.0], [0.0, 2.0], [0.0, 0.0]]]
WITH_HOLE = SQUARE + [[[0.5, 0.5], [1.5, 0.5], [1.5, 1.5], [0.5, 1.5], [0.5, 0.5]]]


@pytest.mark.parametrize(
    ("lon", "lat", "expected"),
    [(1.0, 1.0, True), (0.1, 0.1, True), (2.5, 1.0, False), (1.0, -0.1, False)],
)
def test_point_in_ring(imerg, lon: float, lat: float, expected: bool) -> None:
    assert imerg.point_in_ring(lon, lat, SQUARE[0]) is expected


def test_a_hole_excludes_points_inside_it(imerg) -> None:
    assert imerg.point_in_geometry(0.2, 0.2, WITH_HOLE) is True
    assert imerg.point_in_geometry(1.0, 1.0, WITH_HOLE) is False


def test_cell_index_and_centre_round_trip(imerg) -> None:
    for value in (-179.95, 0.05, 84.05, 179.95):
        index = imerg.cell_index(value, imerg.LON_ORIGIN)
        assert abs(imerg.cell_centre(index, imerg.LON_ORIGIN) - value) < 1e-6


def test_every_district_gets_at_least_one_cell(imerg) -> None:
    """A district that resolves to no cells would vanish from the comparison."""

    if not BOUNDARIES.exists():
        pytest.skip("district boundaries not present")
    import json

    features = json.loads(BOUNDARIES.read_text(encoding="utf-8"))["features"]
    from landslide_inventory.analysis.rainfall import normalize_district

    cells = imerg.district_grid_cells(features, normalize_district)
    assert len(cells) == 77
    assert all(len(value) >= 1 for value in cells.values())
    # The cell count is a physical check, not a magic number. Nepal covers about
    # 147,000 km2; a 0.1-degree cell near 28N is roughly 11.1 x 9.8 km, so about
    # 109 km2, which puts the expected count near 1,350. A transposition of
    # longitude and latitude, or a wrong grid origin, would land far outside
    # this band -- which is the failure this guards against. (The 3,444 cells of
    # the bounding box are not the answer: Nepal is not a rectangle.)
    distinct = {cell for value in cells.values() for cell in value}
    assert 1_100 < len(distinct) < 1_700, len(distinct)

    # Districts must not overlap each other's cells wholesale either.
    assigned = sum(len(value) for value in cells.values())
    assert assigned == len(distinct), "a cell centre belongs to exactly one district"


# A verbatim excerpt of what GES DISC actually returns, captured from a real
# probe run. The first version of this parser was written against an assumed
# format -- lines beginning "[0][0]," with integer offsets -- which this response
# does not use, so it silently parsed to nothing.
REAL_RESPONSE = (
    "Dataset: 3B-DAY.MS.MRG.3IMERG.20240715-S000000-E235959.V07B.nc4\n"
    "precipitation.lat, 26.45, 26.55, 26.65\n"
    "precipitation.precipitation[precipitation.time=16262][precipitation.lon=80.15], 0, 1.815, 0.57\n"
    "precipitation.precipitation[precipitation.time=16262][precipitation.lon=80.25], 0, 0.07, -9999.9\n"
)


def test_the_parser_reads_the_real_gesdisc_response(imerg) -> None:
    assert imerg.looks_like_dap_ascii(REAL_RESPONSE) is True
    grid = imerg.parse_ascii_grid(REAL_RESPONSE)

    # Coordinates are converted to absolute IMERG grid indices.
    lon_80_15 = imerg.cell_index(80.15, imerg.LON_ORIGIN)
    lon_80_25 = imerg.cell_index(80.25, imerg.LON_ORIGIN)
    lat_26_45 = imerg.cell_index(26.45, imerg.LAT_ORIGIN)
    lat_26_55 = imerg.cell_index(26.55, imerg.LAT_ORIGIN)
    lat_26_65 = imerg.cell_index(26.65, imerg.LAT_ORIGIN)

    assert grid[(lon_80_15, lat_26_45)] == 0.0
    assert grid[(lon_80_15, lat_26_55)] == 1.815
    assert grid[(lon_80_15, lat_26_65)] == 0.57
    assert grid[(lon_80_25, lat_26_55)] == 0.07
    assert (lon_80_25, lat_26_65) not in grid, "IMERG fill must not become rainfall"


def test_the_probe_indices_match_what_was_requested(imerg) -> None:
    """The probe confirmed lon 2601 -> 80.15 and lat 1164 -> 26.45."""

    assert imerg.cell_index(80.15, imerg.LON_ORIGIN) == 2601
    assert imerg.cell_index(26.45, imerg.LAT_ORIGIN) == 1164


def test_a_row_that_does_not_match_the_latitude_axis_is_refused(imerg) -> None:
    """A silent misalignment would move rainfall between districts."""

    broken = (
        "precipitation.lat, 26.45, 26.55, 26.65\n"
        "precipitation.precipitation[precipitation.lon=80.15], 1.0, 2.0\n"
    )
    with pytest.raises(imerg.NotDapAscii):
        imerg.parse_ascii_grid(broken)


def test_data_rows_without_a_latitude_axis_are_refused(imerg) -> None:
    orphan = "precipitation.precipitation[precipitation.lon=80.15], 1.0, 2.0\n"
    with pytest.raises(imerg.NotDapAscii):
        imerg.parse_ascii_grid(orphan)


def test_district_means_average_only_the_cells_inside(imerg) -> None:
    grid = {(5, 5): 10.0, (5, 6): 20.0, (6, 5): 100.0}
    cells = {"Alpha": [(5, 5), (5, 6)], "Beta": [(6, 5)]}
    means = imerg.district_means(grid, cells)
    assert means["Alpha"] == pytest.approx(15.0)
    assert means["Beta"] == pytest.approx(100.0)


def test_a_district_with_no_data_is_omitted_not_zeroed(imerg) -> None:
    """A missing value must never be recorded as no rain."""

    means = imerg.district_means({}, {"Alpha": [(5, 5)]})
    assert means == {}


def test_writer_merges_rather_than_truncating(imerg, tmp_path: Path) -> None:
    output = tmp_path / "imerg_daily_districts.csv"
    first = {
        ("2015-01-01", "Kaski"): {
            "date": "2015-01-01",
            "district": "Kaski",
            "rain_mm": "1.000000",
            "source": imerg.SOURCE,
            "product_version": imerg.PRODUCT_VERSION,
        }
    }
    imerg.merge_and_write(output, first)
    second = {
        ("2026-07-01", "Kaski"): {
            "date": "2026-07-01",
            "district": "Kaski",
            "rain_mm": "9.500000",
            "source": imerg.SOURCE,
            "product_version": imerg.PRODUCT_VERSION,
        }
    }
    written, total = imerg.merge_and_write(output, second)
    assert (written, total) == (1, 2)

    with output.open(encoding="utf-8", newline="") as handle:
        rows = {(row["date"], row["district"]) for row in csv.DictReader(handle)}
    assert ("2015-01-01", "Kaski") in rows


def test_the_output_schema_matches_the_chirps_downloader(imerg, tmp_path: Path) -> None:
    """The comparison needs no new analysis code only if the schemas agree."""

    output = tmp_path / "imerg.csv"
    imerg.merge_and_write(
        output,
        {
            ("2020-07-01", "Kaski"): {
                "date": "2020-07-01",
                "district": "Kaski",
                "rain_mm": "3.000000",
                "source": imerg.SOURCE,
                "product_version": imerg.PRODUCT_VERSION,
            }
        },
    )
    with output.open(encoding="utf-8", newline="") as handle:
        assert csv.DictReader(handle).fieldnames == [
            "date",
            "district",
            "rain_mm",
            "source",
            "product_version",
        ]


def test_granule_url_keeps_imerg_lon_before_lat(imerg) -> None:
    """IMERG stores (time, lon, lat); transposing it would move the rainfall."""

    from datetime import date

    url = imerg.granule_url(date(2024, 7, 15), (100, 181), (1163, 1204))
    assert "GPM_3IMERGDF.07/2024/07/" in url
    assert "3B-DAY.MS.MRG.3IMERG.20240715-S000000-E235959.V07B.nc4.ascii" in url
    assert "precipitation[0:0][100:181][1163:1204]" in url


def test_certificate_help_names_the_exact_macos_fix(imerg, monkeypatch) -> None:
    """The raw traceback is sixty lines that never mention the actual remedy."""

    monkeypatch.setattr(imerg.sys, "platform", "darwin")
    message = imerg.certificate_help()
    # The path is shell-escaped, because the user pastes it into a shell:
    # /Applications/Python\ 3.13/Install\ Certificates.command
    assert "Install\\ Certificates.command" in message
    assert "/Applications/Python\\ " in message
    assert "Earthdata password" in message, "must say why verification is not skippable"


def test_certificate_help_is_platform_appropriate(imerg, monkeypatch) -> None:
    monkeypatch.setattr(imerg.sys, "platform", "linux")
    message = imerg.certificate_help()
    assert "Certificates.command" not in message
    assert "--ca-bundle" in message


def test_ssl_context_always_verifies(imerg) -> None:
    """Verification must never be disabled: this request carries a password."""

    import ssl as ssl_module

    context = imerg.ssl_context(None)
    assert context.verify_mode == ssl_module.CERT_REQUIRED
    assert context.check_hostname is True


def test_an_explicit_ca_bundle_is_honoured(imerg, tmp_path) -> None:
    import ssl as ssl_module

    try:
        import certifi
    except ImportError:
        pytest.skip("no PEM bundle available to point at")
    context = imerg.ssl_context(Path(certifi.where()))
    assert context.verify_mode == ssl_module.CERT_REQUIRED


def test_there_is_no_way_to_turn_verification_off(imerg) -> None:
    """A --insecure escape hatch would leak the Earthdata password."""

    options = {action.dest for action in imerg.build_parser()._actions}
    assert not ({"insecure", "no_verify", "skip_verify"} & options)
    source = (ROOT / "scripts" / "download_imerg_gesdisc.py").read_text(encoding="utf-8")
    assert "_create_unverified_context" not in source
    assert "CERT_NONE" not in source


LOGIN_PAGE = (
    "<!DOCTYPE html>\n<html><head><title>Earthdata Login</title></head>\n"
    "<body><form action='https://urs.earthdata.nasa.gov/login'></form></body></html>"
)
DAP_ERROR = 'Error {\n    code = 404;\n    message = "granule not found";\n}'
REAL_ASCII = REAL_RESPONSE


def test_a_login_page_is_not_mistaken_for_an_empty_grid(imerg) -> None:
    """This is the bug that produced '0 rows so far' for nine years."""

    assert imerg.looks_like_dap_ascii(LOGIN_PAGE) is False
    assert imerg.parse_ascii_grid(LOGIN_PAGE) == {}, "and it parses to nothing, hence the trap"


def test_a_dap_error_document_is_rejected(imerg) -> None:
    assert imerg.looks_like_dap_ascii(DAP_ERROR) is False


def test_a_real_grid_is_accepted(imerg) -> None:
    assert imerg.looks_like_dap_ascii(REAL_ASCII) is True
    assert len(imerg.parse_ascii_grid(REAL_ASCII)) == 5  # 6 cells, one is fill


def test_the_redirect_handler_reattaches_auth_only_for_earthdata(imerg) -> None:
    """urllib strips Authorization across hosts; URS then serves a login page."""

    import urllib.request

    handler = imerg.EarthdataRedirectHandler("Basic dGVzdDp0ZXN0")

    class Fp:
        def read(self, *_):
            return b""

    def redirect_to(url: str):
        request = urllib.request.Request("https://gpm1.gesdisc.eosdis.nasa.gov/x")
        return handler.redirect_request(
            request, Fp(), 302, "Found", {"location": url}, url
        )

    to_urs = redirect_to(f"https://{imerg.EARTHDATA_HOST}/oauth/authorize")
    assert to_urs is not None
    assert to_urs.get_header("Authorization") == "Basic dGVzdDp0ZXN0"

    elsewhere = redirect_to("https://example.com/somewhere")
    assert elsewhere is not None
    assert elsewhere.get_header("Authorization") is None, (
        "the credential must never follow an arbitrary redirect"
    )


def test_the_run_stops_early_when_nothing_is_being_collected(imerg) -> None:
    """A long unattended job must refuse to continue when it is not working."""

    args = imerg.build_parser().parse_args([])
    assert args.max_empty_days == 5, "the guard must be on by default"
    assert args.probe is False


def test_granule_url_accepts_alternative_version_suffixes(imerg) -> None:
    """NASA revises the trailing letter as parts of the record are reprocessed.

    One hard-coded suffix 404s silently on whichever stretch carries a different
    one, which reads as "granule not published" and quietly truncates the record.
    """

    from datetime import date

    for suffix in imerg.GRANULE_VERSION_SUFFIXES:
        url = imerg.granule_url(date(2025, 10, 1), (2601, 2681), (1164, 1203), suffix)
        assert f".{suffix}.nc4.ascii" in url

    default_url = imerg.granule_url(date(2025, 10, 1), (2601, 2681), (1164, 1203))
    assert f".{imerg.GRANULE_VERSION_SUFFIXES[0]}.nc4.ascii" in default_url


def test_the_suffix_list_stays_within_one_product_version(imerg) -> None:
    """Mixing V06 and V07 would silently blend two different products."""

    assert all(s.startswith("V07") for s in imerg.GRANULE_VERSION_SUFFIXES)
    assert len(set(imerg.GRANULE_VERSION_SUFFIXES)) == len(imerg.GRANULE_VERSION_SUFFIXES)


# ---------------------------------------------------------------------------
# Early termination must never destroy collected data.
#
# These are regression tests for a real, expensive loss. The empty-day guard
# raised SystemExit from inside the day loop, which fired before the caller
# reached merge_and_write. A fourteen-hour run had correctly collected 302,302
# rows -- 3,926 days x 77 districts, no gaps -- reached the end of the published
# record, tripped the guard, and exited leaving a 46-byte header-only file.
#
# The guard was right. Losing the data was not.
# ---------------------------------------------------------------------------


class FakeClock:
    """collect_days sleeps between days; nothing here should wait for real."""

    def __init__(self) -> None:
        self.slept = 0.0

    def sleep(self, seconds: float) -> None:
        self.slept += seconds


@pytest.fixture()
def collector(imerg, monkeypatch):
    """Drive collect_days with a scripted fetch_day, no network involved."""

    clock = FakeClock()
    monkeypatch.setattr(imerg.time, "sleep", clock.sleep)

    def run(responses, **kwargs):
        """`responses` maps ISO date -> grid dict, or an exception to raise."""

        calls: list[str] = []

        def fake_fetch_day(opener, day, lon_slice, lat_slice, *, timeout, retries):
            calls.append(day.isoformat())
            outcome = responses.get(day.isoformat(), {})
            if isinstance(outcome, BaseException):  # KeyboardInterrupt is not an Exception
                raise outcome
            return outcome

        monkeypatch.setattr(imerg, "fetch_day", fake_fetch_day)
        result = imerg.collect_days(
            object(),
            date(2025, 9, 28),
            date(2025, 10, 10),
            (0, 1),
            (0, 1),
            {"Kaski": [(0, 0)]},
            sleep_seconds=0.0,
            **kwargs,
        )
        return result + (calls,)

    return run


def test_the_empty_day_guard_keeps_everything_it_collected(collector) -> None:
    """The exact failure: stop at the end of the record, keep the record."""

    rows, missing, stop_reason, calls = collector(
        {
            "2025-09-28": {(0, 0): 12.0},
            "2025-09-29": {(0, 0): 3.0},
            "2025-09-30": {(0, 0): 0.0},
        },
        max_empty_days=3,
    )

    assert stop_reason is not None and "3 days in a row" in stop_reason
    assert missing == ["2025-10-01", "2025-10-02", "2025-10-03"]
    assert calls[-1] == "2025-10-03", "the guard must stop the loop, not merely warn"

    # The point of the whole test: the good days survived the stop.
    assert len(rows) == 3
    assert rows[("2025-09-28", "Kaski")]["rain_mm"] == "12.000000"
    assert sorted({key[0] for key in rows}) == ["2025-09-28", "2025-09-29", "2025-09-30"]


def test_a_non_data_response_keeps_everything_it_collected(imerg, collector) -> None:
    """An Earthdata login page instead of a grid must not cost the run either."""

    rows, _missing, stop_reason, _calls = collector(
        {
            "2025-09-28": {(0, 0): 5.0},
            "2025-09-29": imerg.NotDapAscii("<html>Earthdata Login</html>"),
        }
    )

    assert stop_reason is not None
    assert "not rainfall data" in stop_reason
    assert "Earthdata Login" in stop_reason, "the reason must quote what came back"
    assert len(rows) == 1


def test_an_interrupted_run_keeps_everything_it_collected(imerg, collector) -> None:
    rows, _missing, stop_reason, _calls = collector(
        {
            "2025-09-28": {(0, 0): 5.0},
            "2025-09-29": {(0, 0): 6.0},
            "2025-09-30": KeyboardInterrupt(),
        }
    )

    assert stop_reason is not None and "Interrupted at 2025-09-30" in stop_reason
    assert len(rows) == 2


def test_no_exit_path_out_of_the_day_loop_raises(imerg) -> None:
    """Structural guard: collect_days must not contain a raise at all.

    A future edit that reintroduces `raise SystemExit(...)` inside the loop
    would reintroduce the data loss without failing any behavioural test that
    happens not to cover that branch.
    """

    import ast

    source = (ROOT / "scripts" / "download_imerg_gesdisc.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "collect_days"
    )
    raises = [node for node in ast.walk(function) if isinstance(node, ast.Raise)]
    assert not raises, "collect_days must set stop_reason and break, never raise"


def test_checkpointing_writes_before_the_run_ends(collector) -> None:
    """A fourteen-hour run must not hold fourteen hours of data in memory only."""

    written: list[int] = []
    rows, _missing, _stop, _calls = collector(
        {
            "2025-09-28": {(0, 0): 1.0},
            "2025-09-29": {(0, 0): 2.0},
            "2025-09-30": {(0, 0): 3.0},
            "2025-10-01": {(0, 0): 4.0},
        },
        checkpoint_days=2,
        checkpoint=lambda collected: written.append(len(collected)),
        max_empty_days=99,
    )
    assert written[:2] == [2, 4], "a checkpoint every two fetched days"
    assert len(rows) == 4


def test_days_already_complete_are_skipped_on_a_resumed_run(collector) -> None:
    _rows, _missing, _stop, calls = collector(
        {"2025-09-30": {(0, 0): 7.0}},
        skip_days={"2025-09-28", "2025-09-29"},
        max_empty_days=99,
    )
    assert "2025-09-28" not in calls and "2025-09-29" not in calls
    assert calls[0] == "2025-09-30"


def test_complete_days_only_counts_fully_covered_dates(imerg, tmp_path) -> None:
    path = tmp_path / "imerg.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["date", "district", "rain_mm", "source", "product_version"])
        writer.writerow(["2025-09-28", "Kaski", "1.0", "s", "v"])
        writer.writerow(["2025-09-28", "Dolakha", "2.0", "s", "v"])
        writer.writerow(["2025-09-29", "Kaski", "3.0", "s", "v"])  # half a day

    assert imerg.complete_days(path, 2) == {"2025-09-28"}
    assert imerg.complete_days(tmp_path / "absent.csv", 2) == set()


def test_resume_is_on_by_default_but_can_be_turned_off(imerg) -> None:
    args = imerg.build_parser().parse_args([])
    assert args.refetch_complete_days is False
    assert args.checkpoint_days == 100
    assert imerg.build_parser().parse_args(["--refetch-complete-days"]).refetch_complete_days
