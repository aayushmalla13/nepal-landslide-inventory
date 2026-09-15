#!/usr/bin/env python3
"""Download daily district-mean IMERG rainfall from NASA GES DISC.

Purpose
-------
Every result in this study rests on one rainfall product, CHIRPS. The obvious
reviewer question is whether the cutpoint is a property of Nepali landslides or
an artefact of that product. Repeating the analysis on NASA IMERG answers it.

Output is deliberately schema-identical to
``scripts/download_chirps_climateserv.py``::

    date,district,rain_mm,source,product_version

so the comparison needs no new analysis code: point
``analysis.chirps_daily_district_path`` at this file, set a distinct
``analysis.rainfall_product``, and run the stage.

Why this has no new dependencies
--------------------------------
The natural way to do zonal statistics on a gridded product is numpy plus a
NetCDF/HDF5 reader plus a rasteriser. This project is deliberately built on the
standard library plus PyYAML, and three heavy dependencies for one sensitivity
analysis is a bad trade.

It is also unnecessary here. IMERG is a 0.1-degree grid and Nepal spans about
82 x 42 cells -- 3,444 in total. Deciding which cells fall in which district is
a point-in-polygon test over a few thousand points, done once and cached, which
pure Python does in well under a second. The daily values are fetched as text
through OPeNDAP rather than as binary NetCDF, so nothing has to parse HDF5.

Method note that matters for comparability
------------------------------------------
CHIRPS district means come from ClimateSERV, which computes an area-weighted
mean server-side over the same polygons. This script computes an unweighted mean
of the 0.1-degree cell centres falling inside each district. The two are not
identical estimators. For districts many cells across the difference is small,
but Nepal has small districts: any district covered by only a handful of cells
is flagged in the manifest, and the manuscript should report the comparison as
product *and* aggregation differing, not product alone.

Credentials
-----------
Earthdata Login, read from ``~/.netrc`` (or ``--netrc``). The password is never
passed on the command line and never printed. Register free at
<https://urs.earthdata.nasa.gov>, then authorise the application
"NASA GESDISC DATA ARCHIVE" -- downloads fail with an opaque redirect error if
that authorisation is missing.

Usage::

    PYTHONPATH=src python3 scripts/download_imerg_gesdisc.py \\
        --start 2015-01-01 --end 2026-07-31
"""

from __future__ import annotations

import argparse
import base64
import csv
import http.cookiejar
import json
import logging
import netrc
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable, Sequence

LOGGER = logging.getLogger("imerg_gesdisc")

EARTHDATA_HOST = "urs.earthdata.nasa.gov"
OPENDAP_ROOT = "https://gpm1.gesdisc.eosdis.nasa.gov/opendap/GPM_L3/GPM_3IMERGDF.07"
PRODUCT_VERSION = "NASA IMERG Final Run v07 (GPM_3IMERGDF)"

# NASA revises the trailing letter within a product version as parts of the
# record are reprocessed, so one hard-coded suffix silently 404s on the stretches
# that carry a different one. Ordered by how common each is; the first that
# answers for a given day is remembered and tried first thereafter, so this costs
# one extra request per changeover rather than per day.
GRANULE_VERSION_SUFFIXES = ("V07B", "V07A", "V07C", "V07D")
SOURCE = "NASA GES DISC OPeNDAP"

# IMERG global grid, 0.1 degrees. Cell centres run from -179.95 and -89.95.
GRID_RESOLUTION = 0.1
LON_ORIGIN = -179.95
LAT_ORIGIN = -89.95
LON_CELLS = 3600
LAT_CELLS = 1800


# --------------------------------------------------------------------------
# Geometry: which grid cells belong to which district
# --------------------------------------------------------------------------


def _rings(geometry: dict) -> list[list[Sequence[float]]]:
    """Flatten Polygon or MultiPolygon into a list of exterior/interior rings."""

    kind = geometry.get("type")
    coordinates = geometry.get("coordinates") or []
    if kind == "Polygon":
        return [list(ring) for ring in coordinates]
    if kind == "MultiPolygon":
        return [list(ring) for polygon in coordinates for ring in polygon]
    raise ValueError(f"Unsupported geometry type: {kind!r}")


def point_in_ring(lon: float, lat: float, ring: Sequence[Sequence[float]]) -> bool:
    """Ray-casting point-in-polygon test for a single ring.

    Standard crossing-number algorithm. Points exactly on an edge are not
    guaranteed either way, which is immaterial for 0.1-degree cell centres
    against administrative boundaries.
    """

    inside = False
    count = len(ring)
    for index in range(count):
        x1, y1 = ring[index][0], ring[index][1]
        x2, y2 = ring[(index + 1) % count][0], ring[(index + 1) % count][1]
        if (y1 > lat) != (y2 > lat):
            if y2 != y1:
                crossing_x = x1 + (lat - y1) * (x2 - x1) / (y2 - y1)
                if lon < crossing_x:
                    inside = not inside
    return inside


def point_in_geometry(lon: float, lat: float, rings: list[list[Sequence[float]]]) -> bool:
    """True when the point is inside the geometry.

    A GeoJSON polygon's first ring is the exterior and any further rings are
    holes. Nepal's district file has no holes, but honouring them costs nothing
    and stops this being wrong if the boundary source is ever replaced.
    """

    if not rings:
        return False
    if not point_in_ring(lon, lat, rings[0]):
        return False
    for hole in rings[1:]:
        if point_in_ring(lon, lat, hole):
            return False
    return True


def bounding_box(rings: Iterable[Sequence[Sequence[float]]]) -> tuple[float, float, float, float]:
    lons: list[float] = []
    lats: list[float] = []
    for ring in rings:
        for point in ring:
            lons.append(point[0])
            lats.append(point[1])
    return min(lons), min(lats), max(lons), max(lats)


def cell_index(value: float, origin: float) -> int:
    return int(round((value - origin) / GRID_RESOLUTION))


def cell_centre(index: int, origin: float) -> float:
    return origin + index * GRID_RESOLUTION


def district_grid_cells(
    features: Sequence[dict],
    normalize,
) -> dict[str, list[tuple[int, int]]]:
    """Map each district to the (lon_index, lat_index) cells inside it.

    Districts too small to contain any cell centre fall back to the single cell
    containing their centroid, so that no district silently disappears from the
    comparison. Those districts are reported by the caller.
    """

    assignment: dict[str, list[tuple[int, int]]] = {}
    for feature in features:
        properties = feature.get("properties", {})
        raw_name = str(properties.get("DISTRICT") or properties.get("district") or "")
        district = normalize(raw_name)
        rings = _rings(feature["geometry"])
        min_lon, min_lat, max_lon, max_lat = bounding_box(rings)
        cells: list[tuple[int, int]] = []
        for lon_index in range(cell_index(min_lon, LON_ORIGIN), cell_index(max_lon, LON_ORIGIN) + 1):
            lon = cell_centre(lon_index, LON_ORIGIN)
            for lat_index in range(
                cell_index(min_lat, LAT_ORIGIN), cell_index(max_lat, LAT_ORIGIN) + 1
            ):
                lat = cell_centre(lat_index, LAT_ORIGIN)
                if point_in_geometry(lon, lat, rings):
                    cells.append((lon_index, lat_index))
        if not cells:
            centre_lon = (min_lon + max_lon) / 2
            centre_lat = (min_lat + max_lat) / 2
            cells = [(cell_index(centre_lon, LON_ORIGIN), cell_index(centre_lat, LAT_ORIGIN))]
            LOGGER.warning(
                "%s contains no 0.1-degree cell centre; using its centroid cell", district
            )
        assignment[district] = sorted(cells)
    return assignment


# --------------------------------------------------------------------------
# Fetching
# --------------------------------------------------------------------------


def ssl_context(ca_bundle: Path | None) -> ssl.SSLContext:
    """A verifying TLS context, with the most reliable trust store available.

    Certificate verification is never disabled. This download sends an Earthdata
    password, and an unverified connection would hand that password to whatever
    answered. If the trust store cannot be found the run stops with instructions
    rather than continuing insecurely.

    Order of preference: an explicitly supplied bundle, then ``certifi`` if it
    happens to be installed, then the interpreter's default.
    """

    if ca_bundle is not None:
        return ssl.create_default_context(cafile=str(ca_bundle))
    try:  # optional; absent on a bare interpreter, which is the normal case
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def certificate_help() -> str:
    """Actionable remediation for the macOS python.org trust-store gap.

    A Python installed from python.org on macOS does not use the system
    keychain, so out of the box it trusts nothing and every HTTPS request fails
    with ``CERTIFICATE_VERIFY_FAILED``. The installer ships a script to fix it.
    The raw traceback is sixty lines that do not mention this anywhere.
    """

    version = f"{sys.version_info.major}.{sys.version_info.minor}"
    lines = [
        "TLS certificate verification failed: this Python has no trusted "
        "certificate authorities, so it cannot confirm it is talking to NASA.",
        "",
    ]
    if sys.platform == "darwin":
        lines += [
            "On macOS with a python.org install, run this once:",
            "",
            f"    /Applications/Python\\ {version}/Install\\ Certificates.command",
            "",
            "then run this script again.",
        ]
    else:
        lines += [
            "Install your distribution's CA bundle (for example `ca-certificates`),",
            "or pass --ca-bundle /path/to/cacert.pem.",
        ]
    lines += [
        "",
        "Alternatively: pip install certifi (this script uses it automatically),",
        "or pass --ca-bundle explicitly.",
        "",
        "Verification is deliberately not skippable: this request sends your "
        "Earthdata password.",
    ]
    return "\n".join(lines)


class EarthdataRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Keep the Earthdata Basic credential across the login redirect.

    Earthdata Login does not challenge you on the data host. It answers with a
    302 to ``urs.earthdata.nasa.gov``, authenticates there, and redirects back
    with a session cookie. ``urllib`` strips the ``Authorization`` header when a
    redirect crosses hosts -- correct in general, since you do not want your
    credential following an arbitrary hop -- but it means the URS hop is
    unauthenticated, and URS answers **200 with an HTML login page** rather than
    an error.

    That is the failure this class exists to prevent: a login page parsed as
    "a day with no rainfall", repeated for every day in the record, producing a
    run that looks healthy and collects nothing.

    The header is re-attached only for the Earthdata login host, never for an
    arbitrary redirect target.
    """

    def __init__(self, authorization: str) -> None:
        self._authorization = authorization

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        new_request = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new_request is None:
            return None
        host = urllib.parse.urlsplit(newurl).hostname or ""
        if host == EARTHDATA_HOST:
            new_request.add_unredirected_header("Authorization", self._authorization)
        return new_request


def build_opener(
    netrc_path: Path | None, ca_bundle: Path | None = None
) -> urllib.request.OpenerDirector:
    """An opener that carries Earthdata Login credentials and cookies."""

    try:
        credentials = netrc.netrc(str(netrc_path) if netrc_path else None)
        auth = credentials.authenticators(EARTHDATA_HOST)
    except (FileNotFoundError, netrc.NetrcParseError) as exc:
        raise SystemExit(
            f"Could not read Earthdata credentials from .netrc ({exc}). Add a line:\n"
            f"  machine {EARTHDATA_HOST} login YOUR_USERNAME password YOUR_PASSWORD\n"
            "then: chmod 600 ~/.netrc\n"
            "If the password contains spaces or '#', wrap it in double quotes."
        ) from exc
    if not auth:
        raise SystemExit(
            f"No entry for {EARTHDATA_HOST} in .netrc. Add one (see --help)."
        )
    username, _, password = auth

    token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    authorization = f"Basic {token}"

    password_manager = urllib.request.HTTPPasswordMgrWithDefaultRealm()
    password_manager.add_password(None, f"https://{EARTHDATA_HOST}", username, password)
    return urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=ssl_context(ca_bundle)),
        urllib.request.HTTPBasicAuthHandler(password_manager),
        EarthdataRedirectHandler(authorization),
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
    )


def granule_url(
    day: date,
    lon_slice: tuple[int, int],
    lat_slice: tuple[int, int],
    version: str = GRANULE_VERSION_SUFFIXES[0],
) -> str:
    """OPeNDAP ASCII subset for one day over the Nepal bounding box.

    ``precipitation`` in v07 is indexed (time, lon, lat) -- IMERG stores
    longitude first, which is the opposite of most gridded products and an easy
    place to transpose the world by accident.
    """

    stamp = day.strftime("%Y%m%d")
    name = f"3B-DAY.MS.MRG.3IMERG.{stamp}-S000000-E235959.{version}.nc4"
    subset = (
        f"precipitation[0:0][{lon_slice[0]}:{lon_slice[1]}][{lat_slice[0]}:{lat_slice[1]}]"
    )
    return f"{OPENDAP_ROOT}/{day.year}/{day.month:02d}/{name}.ascii?{urllib.parse.quote(subset, safe='[]:')}"


class NotDapAscii(RuntimeError):
    """The server returned something that is not an OPeNDAP ASCII grid."""


# Hyrax emits one line per longitude, naming its coordinates by VALUE, and a
# separate header line carrying the latitude axis:
#
#   Dataset: 3B-DAY.MS.MRG.3IMERG.20240715-S000000-E235959.V07B.nc4
#   precipitation.lat, 26.45, 26.55, 26.65, ...
#   precipitation.precipitation[precipitation.time=16262][precipitation.lon=80.15], 0, 1.815, ...
#
# The first version of this parser expected lines beginning with "[0][0]," and
# integer offsets, which is what a bare DAP array subset looks like. Against the
# real response it matched nothing and returned an empty grid -- read downstream
# as "a day with no rainfall" and repeated for every day in the record.
#
# Reading the coordinates the server states, rather than trusting offsets to line
# up with the request, is also simply safer: it cannot silently shift rainfall
# between districts if a future subset is requested differently.
_LON_IN_HEADER = re.compile(r"\blon(?:gitude)?\s*=\s*(-?\d+(?:\.\d+)?)")


def _axis_of(head: str) -> str | None:
    name = head.rsplit(".", 1)[-1].strip().casefold()
    if name in ("lat", "latitude"):
        return "lat"
    if name in ("lon", "longitude"):
        return "lon"
    return None


def looks_like_dap_ascii(payload: str) -> bool:
    """Whether the body is plausibly a DAP ASCII response.

    A login page, a DAP error document and a rainfall grid all arrive as HTTP
    200. Reading the first two as an empty grid is what let a broken run report
    "0 rows so far" for nine years without complaint.
    """

    head = payload.lstrip()[:400].lower()
    if head.startswith("<") or "<html" in head or "<!doctype" in head:
        return False
    if "error {" in head or "earthdata login" in head or "urs.earthdata" in head:
        return False
    for line in payload.splitlines():
        if "," in line and _LON_IN_HEADER.search(line.partition(",")[0]):
            return True
    return False


def parse_ascii_grid(payload: str) -> dict[tuple[int, int], float]:
    """Parse an OPeNDAP ASCII grid into {(lon_index, lat_index): mm}.

    Indices are absolute IMERG grid indices, derived from the coordinate values
    the server reports. Values below zero are IMERG's fill and are dropped
    rather than recorded as zero rainfall.
    """

    latitudes: list[float] | None = None
    rows: list[tuple[float, list[str]]] = []
    for raw_line in payload.splitlines():
        line = raw_line.strip()
        if not line or "," not in line:
            continue
        head, _, rest = line.partition(",")
        head = head.strip()
        if "[" not in head:
            axis = _axis_of(head)
            if axis == "lat":
                latitudes = [float(part) for part in rest.split(",") if part.strip()]
            continue
        match = _LON_IN_HEADER.search(head)
        if match is None:
            continue
        rows.append((float(match.group(1)), rest.split(",")))

    if not rows:
        return {}
    if latitudes is None:
        raise NotDapAscii(
            "the response carried data rows but no latitude axis, so values "
            "could not be positioned"
        )

    values: dict[tuple[int, int], float] = {}
    for longitude, cells in rows:
        usable = [part for part in cells if part.strip()]
        if len(usable) != len(latitudes):
            # A silent misalignment would move rainfall between districts.
            raise NotDapAscii(
                f"row at lon={longitude} has {len(usable)} values but the "
                f"latitude axis has {len(latitudes)}"
            )
        lon_index = cell_index(longitude, LON_ORIGIN)
        for latitude, part in zip(latitudes, usable):
            try:
                value = float(part)
            except ValueError:
                continue
            if value < 0:  # IMERG fill
                continue
            values[(lon_index, cell_index(latitude, LAT_ORIGIN))] = value
    return values


_PREFERRED_VERSION = [GRANULE_VERSION_SUFFIXES[0]]


def fetch_day(
    opener: urllib.request.OpenerDirector,
    day: date,
    lon_slice: tuple[int, int],
    lat_slice: tuple[int, int],
    *,
    timeout: int,
    retries: int,
) -> dict[tuple[int, int], float]:
    """Fetch one day, trying each known granule version suffix in turn."""

    ordered = _PREFERRED_VERSION + [
        suffix for suffix in GRANULE_VERSION_SUFFIXES if suffix not in _PREFERRED_VERSION
    ]
    for version in ordered:
        result = _fetch_one(
            opener,
            day,
            lon_slice,
            lat_slice,
            version=version,
            timeout=timeout,
            retries=retries,
        )
        if result is not None:
            if _PREFERRED_VERSION[0] != version:
                LOGGER.info("%s: granule version is %s", day.isoformat(), version)
                _PREFERRED_VERSION[0] = version
            return result
    LOGGER.warning("%s: granule not published", day.isoformat())
    return {}


def _fetch_one(
    opener: urllib.request.OpenerDirector,
    day: date,
    lon_slice: tuple[int, int],
    lat_slice: tuple[int, int],
    *,
    version: str,
    timeout: int,
    retries: int,
) -> dict[tuple[int, int], float] | None:
    """Return the grid, or ``None`` when this version suffix does not exist."""

    url = granule_url(day, lon_slice, lat_slice, version)
    for attempt in range(retries):
        try:
            request = urllib.request.Request(url)
            request.add_header("User-Agent", "nepal-landslide-inventory/0.5 imerg-comparison")
            with opener.open(request, timeout=timeout) as response:
                body = response.read().decode("utf-8", errors="replace")
            if not looks_like_dap_ascii(body):
                raise NotDapAscii(body[:600])
            return parse_ascii_grid(body)
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                raise SystemExit(
                    "Earthdata rejected the credentials (HTTP "
                    f"{exc.code}). The usual cause is not having authorised the "
                    '"NASA GESDISC DATA ARCHIVE" application in your Earthdata '
                    "profile under Applications -> Authorized Apps."
                ) from exc
            if exc.code == 404:
                return None
            if attempt + 1 == retries:
                raise
            time.sleep(min(30, 2 ** attempt))
        except NotDapAscii:
            raise
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, ssl.SSLCertVerificationError):
                raise SystemExit(certificate_help()) from exc
            if attempt + 1 == retries:
                raise
            time.sleep(min(30, 2 ** attempt))
        except ssl.SSLCertVerificationError as exc:
            raise SystemExit(certificate_help()) from exc
        except TimeoutError:
            if attempt + 1 == retries:
                raise
            time.sleep(min(30, 2 ** attempt))
    return None


def district_means(
    grid: dict[tuple[int, int], float],
    cells_by_district: dict[str, list[tuple[int, int]]],
) -> dict[str, float]:
    """Unweighted mean of the grid cells falling inside each district.

    A district with no data is omitted rather than recorded as zero rainfall.
    """

    means: dict[str, float] = {}
    for district, cells in cells_by_district.items():
        total = 0.0
        seen = 0
        for cell in cells:
            value = grid.get(cell)
            if value is None:
                continue
            total += value
            seen += 1
        if seen:
            means[district] = total / seen
    return means


def merge_and_write(
    output_path: Path,
    rows: dict[tuple[str, str], dict[str, str]],
    *,
    replace: bool = False,
) -> tuple[int, int]:
    """Merge into any existing series. See the CHIRPS downloader for why."""

    columns = ["date", "district", "rain_mm", "source", "product_version"]
    existing: dict[tuple[str, str], dict[str, str]] = {}
    if output_path.exists() and not replace:
        with output_path.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                existing[(row["date"], row["district"])] = row
    existing.update(rows)
    temporary_path = output_path.with_suffix(output_path.suffix + ".partial")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with temporary_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for key in sorted(existing, key=lambda item: (item[1], item[0])):
            writer.writerow(existing[key])
    temporary_path.replace(output_path)
    return len(rows), len(existing)


def complete_days(output_path: Path, districts_expected: int) -> set[str]:
    """Dates in an existing series that already hold every district's value.

    A full fetch is 3,926 days at roughly thirteen seconds each -- about
    fourteen hours. Refetching days already on disk after an interruption
    wastes that time for nothing, so a resumed run skips them.

    The test is deliberately strict: a day counts as done only when every
    district that has grid cells has a value for it. A day cut in half by an
    interruption is refetched rather than left permanently incomplete.
    """

    if not output_path.exists():
        return set()
    seen: dict[str, set[str]] = {}
    with output_path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            seen.setdefault(row["date"], set()).add(row["district"])
    return {day for day, districts in seen.items() if len(districts) >= districts_expected}


def collect_days(
    opener: urllib.request.OpenerDirector,
    start: date,
    end: date,
    lon_slice: tuple[int, int],
    lat_slice: tuple[int, int],
    cells_by_district: dict[str, list[tuple[int, int]]],
    *,
    timeout: int = 120,
    retries: int = 5,
    sleep_seconds: float = 0.5,
    max_empty_days: int = 5,
    skip_days: frozenset[str] | set[str] = frozenset(),
    checkpoint_days: int = 0,
    checkpoint=None,
) -> tuple[dict[tuple[str, str], dict[str, str]], list[str], str | None]:
    """Fetch each day in the range. Return ``(rows, missing_days, stop_reason)``.

    WHY THIS RETURNS A STOP REASON INSTEAD OF EXITING
    -------------------------------------------------
    The fail-fast guard below is correct and stays. Its first implementation,
    though, raised ``SystemExit`` from inside the loop -- which fired before the
    caller reached ``merge_and_write``. A fourteen-hour run that had correctly
    collected 302,302 rows hit the guard at the end of the published record and
    exited with a 46-byte, header-only output file. The guard did its job and
    the run threw away everything it had earned.

    So no path out of this loop may destroy collected data. Every stop --
    the empty-day guard, a non-data response, Ctrl-C -- sets ``stop_reason`` and
    breaks, and the caller persists ``rows`` before reporting it.
    """

    rows: dict[tuple[str, str], dict[str, str]] = {}
    missing_days: list[str] = []
    stop_reason: str | None = None
    consecutive_empty = 0
    fetched = 0
    day = start
    try:
        while day <= end:
            if day.isoformat() in skip_days:
                day += timedelta(days=1)
                continue
            try:
                grid = fetch_day(
                    opener,
                    day,
                    lon_slice,
                    lat_slice,
                    timeout=timeout,
                    retries=retries,
                )
            except NotDapAscii as exc:
                stop_reason = (
                    "The server returned something that is not rainfall data, most "
                    "likely an Earthdata login page.\n\n"
                    "Check that you have authorised the 'NASA GESDISC DATA ARCHIVE' "
                    "application in your Earthdata profile\n"
                    "(Applications -> Authorized Apps), then run with --probe to see "
                    "the full response:\n\n"
                    f"    ... --probe --start {day.isoformat()}\n\n"
                    f"First 600 characters of what came back:\n{exc.args[0]}"
                )
                break

            if not grid:
                missing_days.append(day.isoformat())
                consecutive_empty += 1
                if consecutive_empty >= max_empty_days:
                    stop_reason = (
                        f"Stopped: {consecutive_empty} days in a row returned no data "
                        f"(through {day.isoformat()}).\n"
                        "That is either the end of the published record or a fault, "
                        "and continuing would waste hours either way.\n"
                        "Everything fetched before this point has been saved.\n\n"
                        "If the record genuinely has a long gap here, raise "
                        "--max-empty-days and run again; completed days are skipped."
                    )
                    break
            else:
                consecutive_empty = 0
                for district, rain in district_means(grid, cells_by_district).items():
                    rows[(day.isoformat(), district)] = {
                        "date": day.isoformat(),
                        "district": district,
                        "rain_mm": f"{rain:.6f}",
                        "source": SOURCE,
                        "product_version": PRODUCT_VERSION,
                    }

            fetched += 1
            if checkpoint is not None and checkpoint_days and fetched % checkpoint_days == 0:
                checkpoint(rows)
            if day.day == 1:
                LOGGER.info("%s: %s rows so far", day.isoformat(), len(rows))
            time.sleep(sleep_seconds)
            day += timedelta(days=1)
    except KeyboardInterrupt:
        stop_reason = (
            f"Interrupted at {day.isoformat()}. Everything fetched before this "
            "point has been saved; running again resumes from here."
        )
    return rows, missing_days, stop_reason


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--boundaries", default="data/reference/nepal_districts_77.geojson")
    parser.add_argument("--output", default="data/external/imerg_daily_districts.csv")
    parser.add_argument("--manifest", default="data/external/imerg_daily_districts_manifest.json")
    parser.add_argument("--start", default="2015-01-01")
    parser.add_argument("--end", default="2026-07-31")
    parser.add_argument("--netrc", default="", help="path to a .netrc (default: ~/.netrc)")
    parser.add_argument(
        "--ca-bundle",
        default="",
        help="PEM file of trusted certificate authorities, if the default store is unusable",
    )
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--retries", type=int, default=5)
    parser.add_argument("--sleep-seconds", type=float, default=0.5)
    parser.add_argument("--replace", action="store_true")
    parser.add_argument(
        "--probe",
        action="store_true",
        help="fetch only --start and print the raw response, for diagnosis",
    )
    parser.add_argument(
        "--max-empty-days",
        type=int,
        default=5,
        help=(
            "stop after this many consecutive days with no data (default 5). "
            "Guards against a long run that is silently collecting nothing."
        ),
    )
    parser.add_argument(
        "--checkpoint-days",
        type=int,
        default=100,
        help=(
            "write the output file every this many fetched days (default 100; "
            "0 disables). A full run takes about fourteen hours."
        ),
    )
    parser.add_argument(
        "--refetch-complete-days",
        action="store_true",
        help=(
            "fetch days that the output file already covers for every district. "
            "By default they are skipped so an interrupted run resumes cheaply."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="resolve the grid assignment and print diagnostics without fetching",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "src"))
    from landslide_inventory.analysis.rainfall import normalize_district

    boundaries = json.loads((root / args.boundaries).read_text(encoding="utf-8"))
    features = boundaries.get("features", [])
    if len(features) != 77:
        raise SystemExit(f"Expected 77 district polygons, found {len(features)}")

    cells_by_district = district_grid_cells(features, normalize_district)
    sparse = {name: len(cells) for name, cells in cells_by_district.items() if len(cells) < 4}
    all_cells = [cell for cells in cells_by_district.values() for cell in cells]
    lon_start = min(cell[0] for cell in all_cells)
    lon_end = max(cell[0] for cell in all_cells)
    lat_start = min(cell[1] for cell in all_cells)
    lat_end = max(cell[1] for cell in all_cells)

    LOGGER.info(
        "grid assignment: %s districts, %s cells, lon %s..%s lat %s..%s",
        len(cells_by_district),
        len(all_cells),
        lon_start,
        lon_end,
        lat_start,
        lat_end,
    )
    if sparse:
        LOGGER.warning(
            "districts resolved by fewer than four grid cells (report these as a "
            "spatial-support caveat): %s",
            sparse,
        )
    if args.dry_run:
        print(json.dumps({"cells_per_district": {k: len(v) for k, v in cells_by_district.items()},
                          "sparse_districts": sparse}, indent=2, ensure_ascii=False))
        return 0

    opener = build_opener(
        Path(args.netrc).expanduser() if args.netrc else None,
        Path(args.ca_bundle).expanduser() if args.ca_bundle else None,
    )
    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)

    if args.probe:
        # Fetch one day and show exactly what came back, so a failure is
        # diagnosed from the response rather than from guesswork.
        url = granule_url(start, (lon_start, lon_end), (lat_start, lat_end))
        print(f"URL:\n  {url}\n")
        request = urllib.request.Request(url)
        request.add_header("User-Agent", "nepal-landslide-inventory/0.5 imerg-comparison")
        try:
            with opener.open(request, timeout=args.timeout) as response:
                status = response.status
                content_type = response.headers.get("Content-Type", "?")
                body = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            print(f"HTTP {exc.code} {exc.reason}\n")
            print(body[:1500])
            return 1
        print(f"HTTP {status}   Content-Type: {content_type}   bytes: {len(body)}")
        print(f"looks like DAP ASCII: {looks_like_dap_ascii(body)}\n")
        print("--- first 30 lines ---")
        for line in body.splitlines()[:30]:
            print(line[:200])
        grid = parse_ascii_grid(body) if looks_like_dap_ascii(body) else {}
        print(f"\n--- parsed {len(grid)} grid values ---")
        if grid:
            sample = list(grid.items())[:5]
            print(f"sample: {sample}")
            means = district_means(grid, cells_by_district)
            print(f"districts with a value: {len(means)} of {len(cells_by_district)}")
            print(f"sample means: {list(means.items())[:3]}")
        return 0
    output_path = root / args.output
    skip_days: set[str] = set()
    if not args.replace and not args.refetch_complete_days:
        skip_days = complete_days(output_path, len(cells_by_district))
        if skip_days:
            LOGGER.info(
                "resuming: %s days already complete in %s will be skipped",
                len(skip_days),
                args.output,
            )

    # The output file is written as the run proceeds, not only at the end, so
    # that an interruption fourteen hours in costs one checkpoint interval
    # rather than the whole run. merge_and_write merges by (date, district), so
    # writing the accumulated rows repeatedly is idempotent.
    replace_next = [args.replace]

    def checkpoint(collected: dict[tuple[str, str], dict[str, str]]) -> None:
        _, running_total = merge_and_write(
            output_path, collected, replace=replace_next[0]
        )
        replace_next[0] = False
        LOGGER.info("checkpoint: %s rows on disk", running_total)

    rows, missing_days, stop_reason = collect_days(
        opener,
        start,
        end,
        (lon_start, lon_end),
        (lat_start, lat_end),
        cells_by_district,
        timeout=args.timeout,
        retries=args.retries,
        sleep_seconds=args.sleep_seconds,
        max_empty_days=args.max_empty_days,
        skip_days=skip_days,
        checkpoint_days=max(0, args.checkpoint_days),
        checkpoint=checkpoint,
    )

    written, total = merge_and_write(output_path, rows, replace=replace_next[0])
    manifest = {
        "product_version": PRODUCT_VERSION,
        "source": SOURCE,
        "start": args.start,
        "end": args.end,
        "rows_fetched": written,
        "rows_total": total,
        "districts": len(cells_by_district),
        "grid_cells_used": len(all_cells),
        "cells_per_district": {k: len(v) for k, v in cells_by_district.items()},
        "districts_with_fewer_than_four_cells": sparse,
        "days_with_no_granule": missing_days,
        "days_skipped_as_already_complete": len(skip_days),
        "last_day_fetched": max((key[0] for key in rows), default=None),
        "stopped_early": stop_reason is not None,
        "stop_reason": stop_reason,
        "aggregation_note": (
            "Unweighted mean of 0.1-degree cell centres inside each district. "
            "CHIRPS district means in this project come from ClimateSERV's "
            "area-weighted server-side mean, so a CHIRPS-IMERG comparison differs "
            "in aggregation as well as in product."
        ),
    }
    (root / args.manifest).write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    LOGGER.info("wrote %s rows (%s total) to %s", written, total, args.output)
    if missing_days:
        LOGGER.warning("%s days had no published granule", len(missing_days))
    if stop_reason is not None:
        # Reported after the data is on disk, never in place of saving it.
        LOGGER.warning("%s", stop_reason)
        return 0 if rows or skip_days else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
