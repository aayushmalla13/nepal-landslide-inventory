# Automated Bilingual Landslide Inventory for Nepal (2015-2026)

This repository contains the reproducible Python scaffold for Paper-1, with a config-driven CLI, SQLite bootstrap, environment diagnostics, hybrid collection scaffolding, committed district gazetteers, and smoke tests for the first runnable stages.

## Layout

- `src/landslide_inventory/`: application package
- `resources/`: committed district and municipality gazetteers
- `scripts/`: repository guard scripts and smoke harnesses
- `tests/`: pytest suite
- `data/`: runtime data directories created from `config.yaml`

## Quick start

```bash
cp config.example.yaml config.yaml
# edit only the external-data file paths in config.yaml
make install
make lint_shadow
make test
make doctor
make smoke_basic
make run STAGE=smoke
```

Copy [config.example.yaml](/Users/aayush/Documents/nepal_landslide_inventory/config.example.yaml) to `config.yaml` and edit only the file paths for external data inputs such as the district shapefile, BIPAD export, and CHIRPS aggregates.

## CLI

```bash
python -m landslide_inventory.run --stage smoke --config config.yaml
python -m landslide_inventory.run --stage collect --config config.yaml
python -m landslide_inventory.run --stage normalize_dates --config config.yaml
python -m landslide_inventory.doctor --config config.yaml --minimal
python scripts/smoke.py --config config.yaml --level basic
python scripts/smoke.py --config config.yaml --level stage --stage scrape
```

## Smoke

- `make smoke_basic`: runs minimal doctor, pytest, and the shadow-module guard.
- `make smoke_stage STAGE=<stage>`: runs a single stage with dev-limit environment overrides.
- `make smoke_all_dev`: runs basic smoke, then stage smoke for `scrape`, `normalize_dates`, `lang`, `extract`, and `dedup`.

The smoke harness uses environment overrides instead of editing config files:
- `LS_MAX_URLS_PER_SOURCE`
- `LS_MAX_PAGES_PER_ENTRY`
- `LS_RATE_LIMIT_SECONDS`

## Current outputs

- `data/raw_sqlite/landslide_inventory.sqlite`: initialized SQLite database with `published_date_raw` and `published_date_ad`
- `data/intermediate/keyword_taxonomy.json`: exported keyword taxonomy
- `data/outputs/coverage_report.csv`: source-year coverage report for discovered, fetched, and parsed counts
- `data/logs/`: runtime logs
- `data/caches/`: runtime caches

## Collection

`python -m landslide_inventory.run --stage collect --config config.yaml` runs the hybrid discovery subsystem. It uses config-driven tag/trend pagination where available, supplements discovery with Google News query seeds, stores raw fetch and parse results idempotently in SQLite, and writes `coverage_report.csv` without changing the fixed 2015-2026 study window.

## Notes

- The config must preserve coverage for the full 2015-01-01 through 2026-12-31 study window.
  This was previously stated as 2015-2024 here and in `paper_metadata` while `config.yaml`
  and `config.py` used 2015-2026 — three documents, three answers. `config.yaml` is
  authoritative; the other two now follow it.

  **Temporal-coverage caveat.** Article volume is strongly skewed toward recent years
  (2024 is roughly 5x 2016) and 2025-26 are partial. That is Google News RSS recency bias
  and site archive depth, not landslide activity. Any inter-annual trend claim needs a
  reporting-effort model (articles-per-source-year as an exposure offset) first — see
  `docs/TECHNICAL_REVIEW.md` section 4.4.
- Exactly eight sources are required in config validation.
- `make lint_shadow` fails if `src/` contains top-level modules that could shadow third-party dependencies.
- All scaffold stages are idempotent and use deterministic hashing helpers for reproducibility.

## Extraction checks

After the extraction stage is implemented, use these SQLite checks to verify municipality-backed location coverage:

```sql
select count(*) from article_events where municipality is not null;
select district, count(*)
from article_events
where municipality is not null
group by district
order by count(*) desc
limit 10;
```


## Validation outputs

Run these stages after `extract`, `event_specificity`, `location_consistency`, `filter_scope`, and `dedup`:

```bash
make run STAGE=inventory_audit
make run STAGE=audit_canonical
make run STAGE=manual_pack
# label data/outputs/manual_verification_sample.csv
make run STAGE=manual_score
```

Outputs:
- `data/outputs/inventory_audit_summary.json`: pre-BIPAD QA summary counts and overlap metrics
- `data/outputs/inventory_audit_report.md`: markdown QA report for source, district, and dedup diagnostics
- `data/outputs/source_year_summary.csv`: source/year article and class counts
- `data/outputs/district_coverage_summary.csv`: district-level bilingual coverage table
- `data/outputs/dedup_cluster_audit.csv`: canonical cluster audit table
- `data/outputs/canonical_audit_sample.csv`: deterministic 30-row canonical audit sample
- `data/outputs/manual_verification_sample.csv`: deterministic 150-row article-level manual review pack
- `data/outputs/manual_metrics.json`: scored manual validation metrics after labeling
- `data/outputs/manual_report.md`: markdown summary of manual validation metrics
