# Submission index — v0.4.0

Primary manuscript text:

- `docs/MANUSCRIPT_PACKAGE_V04.md`

Tables:

- `docs/MANUSCRIPT_TABLES_V04.csv`

Release bundles:

- `data/releases/nepal_landslide_inventory_v0.4.0_v6_20260810/`
- `data/releases/nepal_landslide_rainfall_v0.6.0_20260904/`

Rainfall manuscript and sensitivity:

- `docs/RAINFALL_MANUSCRIPT_DRAFT.md`
- `docs/RAINFALL_PRODUCT_SENSITIVITY.md`
- `docs/RAINFALL_PRODUCT_COMPARISON.md`

The release bundle contains the canonical CSV, frozen locked-v6 labels and
predictions, validation metrics, audit outputs, correction provenance, and
checksummed manifest. The live SQLite database is intentionally stored outside
the Box-synced project directory because of file-size limits.

Before submission, cite inventory v0.4.0 and rainfall v0.6.0 and retain the
exact bundle locks from their `release_manifest.json` files. Do not relabel v6 or recompute its metrics after the
release expansion.
