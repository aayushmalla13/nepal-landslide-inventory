# Do this next - canonical event-level audit

**Status:** frozen scientific pipeline complete; independent event-level audit
pack drawn on 2026-09-16.

## Current frozen results

- Inventory release: `nepal_landslide_inventory_v0.6.0_v7_20260915`
- Rainfall release: `nepal_landslide_rainfall_v0.8.0_20260915`
- Inventory events: 2,885
- Primary CHIRPS result: R5 threshold 51.6 mm; temporal-test AUC 0.675
- IMERG sensitivity: completed and released with v0.6.0
- Automated secondary extraction: failed its utility gate and is frozen out of
  production; see `docs/SECONDARY_EXTRACTION_DECISION.md`

Do not rebuild or overwrite either frozen release. Any scientific change now
requires new evidence, a new locked evaluation, and a new release version.

## Completed first-human audit

The 150-row canonical event audit is complete and scored. See
`docs/CANONICAL_EVENT_AUDIT_RESULT.md`. Preliminary population-weighted event
existence precision is 0.874 (95% CI 0.820-0.924), but strict usable-record
precision is 0.403 (0.321-0.486). This is validation of the frozen v0.6.0
inventory, not extractor development.

## Next validation gate

Obtain an independent second review and adjudicate disagreements before
changing the inventory or manuscript headline claims. Do not apply the first
reviewer's corrections directly: event granularity, onset date, road-event
typing, and cluster identity involve judgement and need a reliability check.

The answer-free second-review pack is ready. A different human reviewer should
follow `docs/CANONICAL_EVENT_SECOND_REVIEW_GUIDE.md` and open only:

1. `data/outputs/canonical_event_audit_second_LABEL_HERE.csv`
2. `data/outputs/canonical_event_audit_second_reading_pack.csv`

Save the completed file as
`data/outputs/canonical_event_audit_second_COMPLETED.csv`. Do not show the
second reviewer the first completed sheet, first score, first result document,
or private second-review mapping. After completion run:

```bash
PYTHONPATH=src .venv/bin/python scripts/score_canonical_event_second_review.py
```

The scorer will report exact agreement and Cohen's kappa and create an
evidence-bearing disagreement sheet for final adjudication.

The frozen releases remain the only current reportable data sources. Audit
findings do not modify them automatically. Corrections, if justified, require a
new inventory release and corresponding rainfall provenance release.

## Submission consolidation after the audit

Repository-side consolidation completed:

1. Manuscript declarations reference rainfall v0.8.0.
2. The rainfall manuscript carries the IMERG sensitivity result and its
   Bhaktapur/Kathmandu spatial-support caveat.
3. Automated secondary extraction is recorded as excluded exploratory work and
   is protected by a production-boundary regression test.
4. All frozen release bundles and the current v0.8.0 working outputs verify.

Author decisions still needed before submission:

1. Author names, affiliations, ORCIDs, and corresponding-author email.
2. CRediT contribution initials.
3. Funding statement.
4. Gazetteer licensing choice recorded in `docs/MANUSCRIPT_DECLARATIONS.md`.
5. Target journal and its required AI-use disclosure wording.

## Preserved checkpoints

- Inventory: `data/releases/nepal_landslide_inventory_v0.6.0_v7_20260915/`
- Rainfall: `data/releases/nepal_landslide_rainfall_v0.8.0_20260915/`
- Secondary diagnostic score: `data/outputs/secondary_locked_v8_score.json`
- Secondary decision: `docs/SECONDARY_EXTRACTION_DECISION.md`
