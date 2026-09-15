#!/usr/bin/env python3
"""Download daily district-mean CHIRPS rainfall from NASA SERVIR ClimateSERV.

The script is resumable: each completed district response is cached before the
combined CSV is rebuilt.  It uses only the Python standard library.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from landslide_inventory.analysis.rainfall import normalize_district

API_ROOT = "https://climateserv.servirglobal.net/api"
BOUNDARY_URL = "https://localboundries.oknp.org/data/district/nepal.geojson"
BOUNDARY_SHA256 = "2c77e563c9df54270744f2e2b19a69f91dc5ca0ce7800025c0323d8b01c00c2f"
LOGGER = logging.getLogger("chirps_climateserv")


def _request_json(
    method: str,
    params: dict[str, object],
    *,
    timeout: int,
    retries: int,
) -> Any:
    encoded = urllib.parse.urlencode(params).encode("utf-8")
    url = f"{API_ROOT}/{method}/"
    for attempt in range(retries):
        try:
            if method == "submitDataRequest":
                request = urllib.request.Request(url, data=encoded, method="POST")
            else:
                request = urllib.request.Request(f"{url}?{encoded.decode('ascii')}")
            request.add_header("User-Agent", "nepal-landslide-inventory/0.4 rainfall-study")
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            if attempt + 1 == retries:
                raise RuntimeError(f"ClimateSERV {method} failed after {retries} attempts") from exc
            time.sleep(min(30, 2 ** attempt))
    raise AssertionError("unreachable")


def _job_id(payload: Any) -> str:
    if isinstance(payload, list) and payload:
        return str(payload[0]).strip('"')
    if isinstance(payload, str):
        return payload.strip('"')
    raise RuntimeError(f"Unexpected ClimateSERV submission response: {payload!r}")


def _parse_progress(payload: Any) -> float:
    if isinstance(payload, list) and payload:
        return float(payload[0])
    if isinstance(payload, int | float):
        return float(payload)
    raise RuntimeError(f"Unexpected ClimateSERV progress response: {payload!r}")


def _extract_rows(payload: Any, start: date, end: date) -> list[tuple[date, float]]:
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise RuntimeError(f"Unexpected ClimateSERV data response: {str(payload)[:300]}")
    rows: list[tuple[date, float]] = []
    for granule in payload["data"]:
        value = granule.get("value", {})
        raw_rain = value.get("avg")
        if raw_rain is None:
            continue
        epoch = granule.get("epochTime")
        if epoch not in (None, ""):
            day = datetime.fromtimestamp(float(epoch), tz=timezone.utc).date()
        else:
            raw_date = str(granule.get("date", ""))
            day = datetime.strptime(raw_date, "%m/%d/%Y").date()
        rain = float(raw_rain)
        if start <= day <= end and rain >= 0:
            rows.append((day, rain))
    rows.sort()
    return rows


def fetch_district(
    feature: dict[str, Any],
    start: date,
    end: date,
    cache_dir: Path,
    timeout: int,
    retries: int,
    poll_seconds: float,
    job_timeout_minutes: int,
) -> tuple[str, list[tuple[date, float]]]:
    properties = feature["properties"]
    raw_name = str(properties.get("DISTRICT") or properties.get("district") or "")
    district = normalize_district(raw_name)
    cache_path = cache_dir / f"{district.lower().replace(' ', '_')}.json"
    if cache_path.exists():
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        if cached.get("start") == start.isoformat() and cached.get("end") == end.isoformat():
            rows = [(date.fromisoformat(day), float(value)) for day, value in cached["rows"]]
            LOGGER.info("%s: reused %s cached days", district, len(rows))
            return district, rows

    payload = _request_json(
        "submitDataRequest",
        {
            "datatype": 0,
            "begintime": start.strftime("%m/%d/%Y"),
            "endtime": end.strftime("%m/%d/%Y"),
            "intervaltype": 0,
            "operationtype": 5,
            "dateType_Category": "default",
            "isZip_CurrentDataType": "false",
            "geometry": json.dumps(feature["geometry"], separators=(",", ":")),
        },
        timeout=timeout,
        retries=retries,
    )
    job_id = _job_id(payload)
    LOGGER.info("%s: submitted job %s", district, job_id)
    deadline = time.monotonic() + job_timeout_minutes * 60
    while True:
        progress = _parse_progress(
            _request_json(
                "getDataRequestProgress",
                {"id": job_id},
                timeout=timeout,
                retries=retries,
            )
        )
        if progress < 0:
            raise RuntimeError(f"ClimateSERV job failed for {district}: {job_id}")
        if progress >= 100:
            break
        if time.monotonic() >= deadline:
            raise TimeoutError(f"ClimateSERV job timed out for {district}: {job_id}")
        time.sleep(poll_seconds)
    data = _request_json(
        "getDataFromRequest",
        {"id": job_id},
        timeout=timeout,
        retries=retries,
    )
    rows = _extract_rows(data, start, end)
    cache_path.write_text(
        json.dumps(
            {
                "district": district,
                "start": start.isoformat(),
                "end": end.isoformat(),
                "job_id": job_id,
                "rows": [[day.isoformat(), value] for day, value in rows],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    LOGGER.info("%s: downloaded %s days", district, len(rows))
    return district, rows


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--boundaries", default="data/reference/nepal_districts_77.geojson")
    parser.add_argument("--output", default="data/external/chirps_daily_districts.csv")
    parser.add_argument(
        "--replace",
        action="store_true",
        help=(
            "discard any existing rows in --output instead of merging into them. "
            "Only for rebuilding the series from scratch; an incremental run must "
            "not use this."
        ),
    )
    parser.add_argument("--cache-dir", default="data/caches/chirps_climateserv")
    parser.add_argument("--start", default="2015-01-01")
    parser.add_argument("--end", default="2026-08-10")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--retries", type=int, default=5)
    parser.add_argument("--poll-seconds", type=float, default=5.0)
    parser.add_argument("--job-timeout-minutes", type=int, default=45)
    parser.add_argument(
        "--district",
        action="append",
        help="Optional canonical district name to download (repeatable; useful for diagnostics).",
    )
    return parser


def ensure_boundaries(path: Path, timeout: int) -> None:
    """Download the pinned 77-district boundary file when it is absent."""

    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    LOGGER.info("Downloading pinned Nepal district boundaries")
    request = urllib.request.Request(BOUNDARY_URL)
    request.add_header("User-Agent", "nepal-landslide-inventory/0.4 rainfall-study")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        content = response.read()
    digest = hashlib.sha256(content).hexdigest()
    if digest != BOUNDARY_SHA256:
        raise RuntimeError(
            "Downloaded district boundary checksum changed; review the source before continuing "
            f"(expected {BOUNDARY_SHA256}, received {digest})"
        )
    path.write_bytes(content)


def merge_and_write(
    output_path: Path,
    results: dict[str, list[tuple[date, float]]],
    *,
    replace: bool = False,
) -> tuple[int, int, int]:
    """Merge freshly fetched district-days into the stored series and write it.

    Returns ``(fetched, overwritten, total_rows)``.

    MERGE, never replace. This logic used to live inline in ``main`` and opened
    the output with mode ``"w"``, writing only the rows for the requested
    window. Running the script to extend the series by one month therefore
    destroyed the other eleven years: a run with ``--start 2026-06-01`` replaced
    a 2015-2026 file of 323,323 rows with 4,697. Nothing warned, and the loss is
    invisible until an analysis quietly drops a decade of matched controls.

    The natural use of this script is incremental -- fetch the new tail, keep
    what is already downloaded -- so merging is the correct default. A re-fetched
    district-day overwrites the stored one, which is what lets a deliberate
    correction (CHIRPS Prelim later superseded by Final) be applied by re-running
    rather than by hand-editing the CSV.
    """

    columns = ["date", "district", "rain_mm", "source", "product_version"]
    existing: dict[tuple[str, str], dict[str, str]] = {}
    if output_path.exists() and not replace:
        with output_path.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                existing[(row["date"], row["district"])] = row
        LOGGER.info("Merging into %s existing district-day rows", len(existing))

    fetched = 0
    overwritten = 0
    for district in sorted(results):
        for day, rain in results[district]:
            key = (day.isoformat(), district)
            if key in existing:
                overwritten += 1
            existing[key] = {
                "date": day.isoformat(),
                "district": district,
                "rain_mm": f"{rain:.6f}",
                "source": "NASA SERVIR ClimateSERV",
                "product_version": "UCSB CHIRPS v2.0 Final",
            }
            fetched += 1

    # Write through a temporary file so an interrupted run cannot leave a
    # truncated series behind either.
    temporary_path = output_path.with_suffix(output_path.suffix + ".partial")
    with temporary_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for key in sorted(existing, key=lambda item: (item[1], item[0])):
            writer.writerow(existing[key])
    temporary_path.replace(output_path)
    return fetched, overwritten, len(existing)


def main() -> None:
    args = build_parser().parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    if start > end:
        raise ValueError("--start must not be after --end")
    boundaries_path = Path(args.boundaries).resolve()
    output_path = Path(args.output).resolve()
    cache_dir = Path(args.cache_dir).resolve()
    cache_dir.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ensure_boundaries(boundaries_path, args.timeout)
    collection = json.loads(boundaries_path.read_text(encoding="utf-8"))
    features = collection.get("features", [])
    if len(features) != 77:
        raise ValueError(f"Expected 77 district boundary features, found {len(features)}")
    selected_districts = {normalize_district(item) for item in (args.district or [])}
    if selected_districts:
        features = [
            feature
            for feature in features
            if normalize_district(str(feature["properties"].get("DISTRICT", "")))
            in selected_districts
        ]
        if len(features) != len(selected_districts):
            raise ValueError("One or more --district values do not match the boundary file")

    results: dict[str, list[tuple[date, float]]] = {}
    failures: list[str] = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(
                fetch_district,
                feature,
                start,
                end,
                cache_dir,
                args.timeout,
                args.retries,
                args.poll_seconds,
                args.job_timeout_minutes,
            ): feature
            for feature in features
        }
        for future in as_completed(futures):
            feature = futures[future]
            raw_name = str(feature.get("properties", {}).get("DISTRICT", "unknown"))
            try:
                district, rows = future.result()
                results[district] = rows
            except Exception as exc:  # report every district instead of losing completed work
                LOGGER.error("%s failed: %s", raw_name, exc)
                failures.append(f"{raw_name}: {exc}")
    if failures:
        raise RuntimeError("CHIRPS collection failures: " + "; ".join(failures))
    if len(results) != len(features):
        raise RuntimeError(
            f"Expected results for {len(features)} districts, received {len(results)}"
        )

    fetched, overwritten, total = merge_and_write(
        output_path, results, replace=args.replace
    )
    LOGGER.info(
        "Fetched %s district-day rows (%s replaced existing); wrote %s rows to %s",
        fetched,
        overwritten,
        total,
        output_path,
    )


if __name__ == "__main__":
    main()
