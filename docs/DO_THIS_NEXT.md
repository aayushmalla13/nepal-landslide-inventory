# Do this next - submission consolidation

**Status:** scientific pipeline complete for the frozen scope as of 2026-09-14.

## Current frozen results

- Inventory release: `nepal_landslide_inventory_v0.4.0_v6_20260810`
- Rainfall release: `nepal_landslide_rainfall_v0.6.0_20260904`
- Inventory events: 3,114
- Primary CHIRPS result: R5 threshold 51.6 mm; temporal-test AUC 0.675
- IMERG sensitivity: completed and released with v0.6.0
- Automated secondary extraction: failed its utility gate and is frozen out of
  production; see `docs/SECONDARY_EXTRACTION_DECISION.md`

Do not rebuild or overwrite either frozen release. Any scientific change now
requires new evidence, a new locked evaluation, and a new release version.

## Next project stage

The next stage is manuscript and submission consolidation, not more extractor
work. Use the frozen inventory v0.4.0 and rainfall v0.6.0 bundles as the only
reportable sources.

Repository-side consolidation completed:

1. Manuscript declarations and the submission index reference rainfall v0.6.0.
2. The rainfall manuscript carries the IMERG sensitivity result and its
   Bhaktapur/Kathmandu spatial-support caveat.
3. Automated secondary extraction is recorded as excluded exploratory work and
   is protected by a production-boundary regression test.
4. All ten frozen release bundles and the current v0.6.0 working outputs verify,
   and the submission index lists both current bundles.

Author decisions still needed before submission:

1. Author names, affiliations, ORCIDs, and corresponding-author email.
2. CRediT contribution initials.
3. Funding statement.
4. Gazetteer licensing choice recorded in `docs/MANUSCRIPT_DECLARATIONS.md`.
5. Target journal and its required AI-use disclosure wording.

## Preserved checkpoints

- Inventory: `data/releases/nepal_landslide_inventory_v0.4.0_v6_20260810/`
- Rainfall: `data/releases/nepal_landslide_rainfall_v0.6.0_20260904/`
- Secondary diagnostic score: `data/outputs/secondary_locked_v8_score.json`
- Secondary decision: `docs/SECONDARY_EXTRACTION_DECISION.md`
