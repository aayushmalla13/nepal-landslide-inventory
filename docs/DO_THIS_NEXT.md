# Do this next - audit-driven corrected release

**Status:** the frozen pipeline, independent canonical-event review, and
third-reviewer adjudication are complete as of 2026-09-16.

## Definitive validation result

- Inventory release: `nepal_landslide_inventory_v0.6.0_v7_20260915`
- Audited sample: 150 stratified events from 2,885 canonical events
- Independent reviewers: 2
- Rows adjudicated by `reviewer_C`: 46
- Event existence precision: 0.860 (95% CI 0.804-0.912)
- Strict usable-record precision: 0.402 (0.319-0.489)
- District accuracy: 0.845 (0.779-0.903)
- Date accuracy: 0.762 (0.684-0.836)

See `docs/CANONICAL_EVENT_ADJUDICATED_RESULT.md` for all agreement and accuracy
metrics. The first-review result remains historical evidence; manuscript claims
must use the adjudicated result.

## Next scientific stage

Create a correction-candidate table from the adjudicated 150-row audit before
changing production data. For every rejected or inaccurate record, encode a
specific action such as exclude event, split cluster, correct district, correct
date, correct event/hazard type, correct deaths, or re-cluster duplicates.

Then:

1. Apply only evidence-supported corrections through a reviewed correction
   layer, preserving immutable source provenance.
2. Investigate whether each audited error exposes a systematic rule that should
   be fixed across the full inventory rather than only in sampled records.
3. Add regression tests for every accepted systematic fix.
4. Re-run extraction, scope filtering, specificity, location consistency,
   deduplication, and canonical export into a new versioned release.
5. Re-run rainfall linkage and sensitivity analyses because corrected dates and
   event identities can change rainfall results.
6. Keep v0.6.0 and rainfall v0.8.0 frozen and publish all new outputs under new
   release identifiers.

Do not claim that the audited corrections alone establish the precision of the
future corrected release. That release needs a fresh locked audit or a clearly
labelled post-correction verification sample.

## Preserved evidence

- Frozen inventory: `data/releases/nepal_landslide_inventory_v0.6.0_v7_20260915/`
- Frozen rainfall: `data/releases/nepal_landslide_rainfall_v0.8.0_20260915/`
- Adjudicated labels: `data/outputs/canonical_event_audit_ADJUDICATED.csv`
- Adjudication provenance: `data/outputs/canonical_event_audit_adjudication_manifest.json`
- Definitive score: `data/outputs/canonical_event_audit_adjudicated_score.json`
- Agreement report: `data/outputs/canonical_event_audit_interannotator_agreement.md`

## Submission decisions still needed

1. Author names, affiliations, ORCIDs, and corresponding-author email.
2. CRediT contribution initials.
3. Funding statement.
4. Gazetteer licensing choice in `docs/MANUSCRIPT_DECLARATIONS.md`.
5. Target journal and required AI-use disclosure wording.
