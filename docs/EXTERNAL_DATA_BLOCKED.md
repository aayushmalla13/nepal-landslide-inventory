# External data that could not be acquired, and exactly what unblocks it

**Date:** 2026-08-14

Four analyses named as future work in the senior review need data that this
session could not fetch. This records precisely what is blocked, why, and the
single step that unblocks each, so none of it has to be rediscovered.

## Network reachability actually observed

The analysis environment reaches **GitHub raw content** and **PyPI** only.
Everything else tested returned no route:

| Host | Needed for | Result |
|---|---|---|
| `raw.githubusercontent.com` | reference geodata | reachable |
| `pypi.org` | packages | reachable |
| `climateserv.servirglobal.net` | CHIRPS daily district means | **blocked** |
| `data.chc.ucsb.edu` | CHIRPS direct | **blocked** |
| `data.humdata.org` | HDX / OCHA boundaries | **blocked** |
| `services.arcgis.com`, `opendata.arcgis.com` | boundary services | **blocked** |
| `portal.opentopography.org` | SRTM / DEM | **blocked** |
| `nominatim.openstreetmap.org`, `overpass-api.de` | geocoding | **blocked** |

The `github.com` API is additionally scoped to configured repositories, so
repository *search* is unavailable; only direct raw file paths work.

This is why the gazetteer rebuild succeeded (both sources are GitHub-hosted) and
why the four items below did not.

---

## 1. CHIRPS beyond 30 June 2026 — **RESOLVED 2026-09-03**

Downloaded by the author from an unrestricted network and merged. The record now
runs to **31 July 2026**, all CHIRPS v2.0 **Final** — no Prelim, so the caveat
below about mixing products did not arise.

Verified by overlap: the run deliberately re-fetched June 2026, and all 2,310
overlapping district-days reproduce the stored values exactly.

Events excluded for want of rainfall fell from 84 to **18**. Released as
`nepal_landslide_rainfall_v0.5.0_20260903`.

The original caveat still governs any *future* extension, because CHIRPS Final
lags roughly a month: if a later run returns Prelim days, they must be labelled
and analysed as a sensitivity analysis, never appended silently into the primary
series. `product_version` is carried per row for exactly this reason.

**A bug was found in the process.** The downloader replaced its output rather
than merging, so the incremental run truncated the 2015-2026 series to the
requested month. Fixed in `merge_and_write`, with regression tests; `--replace`
is now required to discard existing rows.

---

## 2. IMERG cross-comparison — **DONE (2026-09-04, release v0.6.0)**

**What it unblocks.** The manuscript's standing limitation that every result
rests on a single rainfall product.

**Resolved.** The full record was downloaded (302,302 district-days, 3,926 days x
77 districts, 2015-01-01 to 2025-09-30, no gaps) and the analysis re-run on it
against a CHIRPS run truncated to the identical period. IMERG discriminates
better at every window in both splits (+0.034 to +0.063 AUC; all eight paired,
district-clustered intervals exclude zero), so the association is not an artefact
of CHIRPS. The cutpoint is product-specific: 39.1 mm at R5 under IMERG against
51.6 mm under CHIRPS, and IMERG selects R3 rather than R5. Full account in
`docs/RAINFALL_PRODUCT_SENSITIVITY.md`. The notes below are kept because they
document how the download works and the caveats that still apply to the result.

**Status 2026-09-03.** `scripts/download_imerg_gesdisc.py` is written and
tested. It produces the identical schema to the CHIRPS downloader, so the
comparison needs no new analysis code: point
`analysis.chirps_daily_district_path` at the IMERG file, set a distinct
`analysis.rainfall_product`, and run the stage.

**It adds no dependencies.** The obvious implementation needs numpy, an HDF5
reader and a rasteriser. That is a bad trade for one sensitivity analysis in a
project built on the standard library. It is also unnecessary: IMERG is a
0.1-degree grid, Nepal resolves to 1,356 cells, and deciding which cell belongs
to which district is a point-in-polygon test done once. Daily values are fetched
as text through OPeNDAP, so nothing parses HDF5.

**Two caveats that belong in the manuscript, not in a footnote.**

1. *Aggregation differs as well as product.* CHIRPS district means come from
   ClimateSERV's area-weighted server-side mean; this computes an unweighted
   mean of cell centres inside each district. Report the comparison as differing
   in both respects, not in product alone.
2. *Two districts have almost no spatial support.* Bhaktapur resolves to a
   single grid cell and Kathmandu to three. Both are flagged in the run manifest
   and should be excluded or caveated in any per-district comparison.

**To run it** (from a machine with an Earthdata login configured):

```bash
PYTHONPATH=src python3 scripts/download_imerg_gesdisc.py --dry-run   # check the grid, no network
PYTHONPATH=src python3 scripts/download_imerg_gesdisc.py --start 2015-01-01 --end 2026-07-31
```

Credentials are read from `~/.netrc`, never from the command line:

```
machine urs.earthdata.nasa.gov login YOUR_USERNAME password YOUR_PASSWORD
```

`chmod 600 ~/.netrc` afterwards. The step people miss is authorising the
**"NASA GESDISC DATA ARCHIVE"** application in the Earthdata profile; without it
the download fails with an opaque redirect error, which the script detects and
explains rather than passing on.

It fetches one day at a time over about 4,250 days, so expect a run of roughly
fourteen hours.

**Interrupting and resuming is safe — but only since 2026-09-04.** The first
version was not, and the failure is worth recording because it cost a complete
run:

- The script has a deliberate fail-fast guard: if `--max-empty-days` days in a
  row return no data, it stops rather than spending hours collecting nothing.
  That guard is right, and an earlier run had proved its worth by catching a
  silent authentication failure.
- It was implemented as `raise SystemExit(...)` **inside the day loop**, which
  fired before the caller reached `merge_and_write`.
- A run then worked perfectly: 302,302 rows — 3,926 days × 77 districts, no
  gaps, 2015-01-01 to 2025-09-30 — and reached the genuine end of the published
  IMERG Final record. The guard fired at 2025-10-05, correctly. The process
  exited leaving a 46-byte, header-only output file. Fourteen hours of correct
  data was discarded by the mechanism meant to protect the run.

The loop now sets a `stop_reason` and breaks; every exit path — the empty-day
guard, a non-data response, Ctrl-C — persists what was collected and then
reports why it stopped. Three behavioural regression tests cover those three
paths, and a structural test asserts that `collect_days` contains no `raise` at
all, so the pattern cannot be reintroduced by a branch no behavioural test
happens to cover.

Two related changes make a long run cheap to restart:

- `--checkpoint-days` (default 100) writes the output file as the run proceeds,
  so an interruption costs one checkpoint interval rather than the whole run.
- A resumed run skips days the output file already covers **for every
  district**; a day cut in half by an interruption is refetched rather than
  left permanently incomplete. `--refetch-complete-days` turns this off.

**Expected outcome of a full run.** IMERG Final publishes with several months'
latency. The record ended at 2025-09-30 as of 2026-09-03, so the last ~300 days
of the CHIRPS series have no IMERG counterpart. That is not a fault. It does
mean the CHIRPS↔IMERG comparison **must be run on the overlapping period only**,
with both products truncated to the IMERG end date — otherwise product and
period are confounded and any difference is uninterpretable.

---

## 3. Terrain and elevation effect modification

**What it unblocks.** Whether the rainfall–landslide association is modified by
relief, slope or elevation — the most-requested extension of a district-scale
threshold study.

**Blocker.** No digital elevation model is present in the repository and
OpenTopography is unreachable. SRTM tiles are not distributed via GitHub.

**Unblock.** Obtain SRTM 30 m (SRTMGL1) or 90 m (SRTMGL3) coverage of Nepal from
OpenTopography (free API key) or NASA Earthdata, then derive per-district
summaries — mean elevation, relief (p95 − p05), mean slope — and join them to the
existing case/control table. The matched design already controls district, so
terrain enters as an effect modifier via an interaction term in the conditional
logistic model, not as a confounder.

**Scale note.** District-mean terrain is a weak covariate: districts span
thousands of metres of relief. This is worth doing only alongside item 4, at
municipality or slope scale.

---

## 4. Sub-district (municipality-scale) rainfall exposure

**What it unblocks.** The manuscript's spatial-smoothing limitation. 2,134
articles now carry a municipality and 1,685 a ward (after the backfill in
`MISSING_DATA_RECOVERY.md`), so a substantially finer exposure is now
*addressable* for the first time.

**What is already solved.** Municipality geometry is now vendored and
checksum-pinned at
`data/reference/sources/nepal_local_units_geometry.geojson` (747 local-unit
polygons, MIT-licensed). The boundary side of this problem is done.

**Blocker.** Gridded rainfall. The project holds only *district-mean* daily
values, not the underlying CHIRPS grid, so municipality means cannot be computed
from what is on disk. That needs the same ClimateSERV or CHIRPS access as item 1,
requested against municipality polygons instead of district polygons.

**Unblock.** Adapt `scripts/download_chirps_climateserv.py` to iterate the
municipality polygons rather than the district polygons, producing
`data/external/chirps_daily_municipalities.csv` in the same schema. That is
roughly a tenfold increase in requests, so expect a long, resumable run — the
existing downloader already caches per-polygon and resumes.

**Expected payoff, stated honestly.** Municipality-scale exposure would apply to
the ~63% of articles with a municipality, so the sub-district analysis would be a
secondary result on a subset, with its own selection caveat: articles naming a
municipality are not a random sample of articles.

---

## 5. Prospective validation

Not blocked by data access — blocked by time. It requires freezing the current
cutpoint, then collecting new events and rainfall forward from a declared start
date. Worth stating in the manuscript as the only way to convert a research
threshold into anything operational.

---

## Summary

| Item | Blocked by | Human input needed |
|---|---|---|
| CHIRPS tail (84 events) | network | run existing downloader elsewhere |
| IMERG comparison | network + credentials | **Earthdata account** |
| Terrain modification | network | DEM download (free API key) |
| Municipality rainfall | network | run adapted downloader; geometry already pinned |
| Prospective validation | elapsed time | declare a start date |

Only IMERG requires a credential the project does not already have a path to.
