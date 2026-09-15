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

Copy [config.example.yaml](config.example.yaml) to `config.yaml` and edit only the file paths for external data inputs such as the district shapefile, BIPAD export, and CHIRPS aggregates.

The current scientific objective is the Option 2 rainfall study: media-reported
landslides versus antecedent daily rainfall. See
[`docs/RAINFALL_ANALYSIS.md`](docs/RAINFALL_ANALYSIS.md) for the reproducible
CHIRPS download, matched-control design, temporal validation, and outputs.

## Current results

Analysis release `nepal_landslide_rainfall_v0.2.0_20260814` (bundle lock
`404ddfe66a11a42fa72a9b341fd1a8817f52d3370b454af87a99b3a68919870c`), linked to
the frozen inventory release `nepal_landslide_inventory_v0.4.0_v6_20260810`.

| | Primary (concurrent) | Co-primary (strictly antecedent) |
|---|---|---|
| Window selected in development | 5 days | 3 days |
| Cutpoint | 45.4 mm | 19.1 mm |
| Temporal-test AUC | 0.693 (0.657–0.722) | 0.664 (0.628–0.697) |
| Leave-one-year-out AUC | 0.652 (0.563–0.710) | 0.622 (0.560–0.690) |
| Odds ratio per 10 mm | 1.23 (1.19–1.26) | 1.22 (1.19–1.26) |

Concurrent windows end on and include the reported event day, so they may contain
rain that fell after failure; the strictly antecedent result bounds the signal
available beforehand. Read the single temporal-test AUC against the
leave-one-year-out range. The cutpoint is a **monsoon-season research value at
district scale**, not an operational warning threshold — outside the monsoon the
optimum falls to about 1.5 mm.

Key documents:

- [`docs/RAINFALL_ANALYSIS.md`](docs/RAINFALL_ANALYSIS.md) — protocol and analysis roles
- [`docs/RAINFALL_MANUSCRIPT_DRAFT.md`](docs/RAINFALL_MANUSCRIPT_DRAFT.md) — manuscript
- [`docs/RAINFALL_MANUSCRIPT_TABLES.md`](docs/RAINFALL_MANUSCRIPT_TABLES.md) — tables 1–7
- [`docs/RAINFALL_CHANGELOG.md`](docs/RAINFALL_CHANGELOG.md) — v0.1.0 versus v0.2.0
- [`docs/SENIOR_REVIEW_2026-08-14.md`](docs/SENIOR_REVIEW_2026-08-14.md) — independent audit
- [`docs/PROJECT_COMPLETE_PLAIN_LANGUAGE_GUIDE.md`](docs/PROJECT_COMPLETE_PLAIN_LANGUAGE_GUIDE.md) — non-specialist explanation
- [`docs/MISSING_DATA_RECOVERY.md`](docs/MISSING_DATA_RECOVERY.md) — gazetteer rebuild (142 → 753 local units) and municipality/ward backfill
- [`docs/EXTERNAL_DATA_BLOCKED.md`](docs/EXTERNAL_DATA_BLOCKED.md) — IMERG, DEM and CHIRPS-tail acquisition, and exactly what unblocks each

Regenerate the analysis, figures and release:

```bash
PYTHONPATH=src .venv/bin/python -m landslide_inventory.run --stage analysis --config config.yaml
PYTHONPATH=src .venv/bin/python -m landslide_inventory.run \
  --stage analysis_figures --config config.yaml
PYTHONPATH=src .venv/bin/python -m landslide_inventory.run --stage analysis_release --config config.yaml
python3 scripts/verify_releases.py
```

`scripts/verify_releases.py` re-verifies every release bundle (file digests plus
bundle lock) and warns if the working outputs have drifted from the newest frozen
rainfall release. Standard library only.

## CLI

```bash
python -m landslide_inventory.run --stage smoke --config config.yaml
python -m landslide_inventory.run --stage collect --config config.yaml
python -m landslide_inventory.run --stage normalize_dates --config config.yaml
python -m landslide_inventory.run --stage external_probe --config config.yaml
LS_EXTERNAL_SOURCE=bipad python -m landslide_inventory.run --stage external_collect --config config.yaml
python -m landslide_inventory.run --stage external_export --config config.yaml
python -m landslide_inventory.run --stage external_match --config config.yaml
LS_EXTERNAL_SEED_LIMIT=10 python -m landslide_inventory.run --stage external_discover --config config.yaml
python -m landslide_inventory.run --stage external_ingest --config config.yaml
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
- `data/outputs/external_records.csv`: provenance-preserving export of isolated government, archive, scientific, and humanitarian records
- `data/outputs/external_match_report.md`: BIPAD/news overlap summary with strong, weak, and unmatched counts
- `data/outputs/external_search_seeds.csv`: severity-ordered BIPAD gaps for targeted news retrieval
- `data/outputs/external_bipad_match_candidates.csv`: auditable tiered BIPAD/news candidate links
- `data/outputs/external_coolr_inventories.csv`: COOLR features grouped as scientific inventories rather than incident counts
- `data/outputs/external_news_candidates.csv`: bounded Google News index leads linked to unmatched BIPAD seeds; review-only until publisher URLs are resolved
- `data/logs/`: runtime logs
- `data/caches/`: runtime caches

## Collection

`python -m landslide_inventory.run --stage collect --config config.yaml` runs the hybrid discovery subsystem. It uses config-driven tag/trend pagination where available, supplements discovery with Google News query seeds, stores raw fetch and parse results idempotently in SQLite, and writes `coverage_report.csv` without changing the fixed 2015-2026 study window.

External observations and archive indexes use separate `external_records` and
`external_source_runs` tables. They never enter the news evaluation corpus
implicitly. See [docs/EXTERNAL_SOURCES.md](docs/EXTERNAL_SOURCES.md) for supported
sources, credentials, boundaries, and one-source collection commands.

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
- The original eight news sources are required in config validation; additional sources are allowed.
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

# Independent tuning sample; excludes every locked-test and previously labelled URL.
make run STAGE=development_set
# After blind labeling is complete, freeze and diagnose it (not a held-out score).
make run STAGE=score_development
# After tuning and rebuilding, preserve baseline predictions and compare:
make run STAGE=refresh_development_predictions
make run STAGE=score_development_tuned

# After locked-v3 scoring and reviewed release QA:
make run STAGE=corrections
make run STAGE=dedup
make run STAGE=event_typing
make run STAGE=export_final
make run STAGE=inventory_audit
make run STAGE=final_report
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
- `data/outputs/development_set_v1_LABEL_HERE.csv`: blind development-only labeling file
- `data/outputs/development_set_v1_predictions.csv`: separate pipeline snapshot; do not open while labeling
- `data/outputs/development_set_v1_manifest.json`: allocation and exclusion provenance
- `data/outputs/development_set_v1_labels_final.csv`: immutable completed-label snapshot
- `data/outputs/development_set_v1_predictions_tuned.csv`: separate post-tuning snapshot
- `data/outputs/development_set_v1_diagnostics_tuned.json`: development-only before/after diagnostic
- `data/outputs/development_set_v1_errors.csv`: false-positive/false-negative review rows
- `data/outputs/development_set_v1_diagnostics.json`: development-only pattern diagnostics; never report as held-out performance
- `data/outputs/locked_test_set_v3_LABEL_HERE.csv`: untouched post-development labeling file; this is the only v3 CSV the annotator edits
- `data/outputs/locked_test_set_v3_predictions.csv`: frozen blind prediction snapshot; do not open while labeling
- `data/outputs/locked_test_set_v3_manifest.json`: URL lock, sampling weights, and contamination audit
- `docs/LOCKED_TEST_V3.md`: authoritative v3 labeling and scoring runbook
- `corrections/article_corrections.csv`: tracked, reviewed post-validation correction layer applied before dedup
- `data/outputs/locked_test_set_v3_manuscript_metrics.csv`: reportable metrics in table-ready form
- `data/outputs/locked_test_set_v3_validation_report.md`: final methods/results summary and limitations
- `data/releases/nepal_landslide_inventory_v0.1.0_v3_20260810/`: checksummed final CSV, SQLite snapshot, evaluation artifacts, audits, and correction provenance
- `docs/FINAL_RELEASE.md`: final release identity, metrics, checksums, and rebuild commands
