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

## Completed correction triage

The audit-derived candidate queue is complete. It contains 119 candidate rows:
90 P0 identity/linkage candidates, 27 P1 attribute candidates, and 2 P2
uncertain candidates. See `docs/CANONICAL_EVENT_CORRECTION_PLAN.md`.

## Next scientific stage

Resolve the 55-row article-mapping batch first:

`data/outputs/canonical_event_correction_BATCH_ARTICLE_MAPPING.csv`

For each row, map all source article URLs and decide the final membership action:
exclude all non-events, split aggregate records into physical events, and
separate articles that were incorrectly merged. Do not apply date, location,
type, hazard, or casualty changes until event identity and cluster membership
are stable.

After article mapping:

1. Complete the 37-row true-value batch with evidence-backed replacement dates
   and locations.
2. Apply the 27 structured attribute candidates against stable events.
3. Convert recurring patterns into pipeline fixes and regression tests.
4. Rebuild into a new versioned inventory release.
5. Re-run rainfall linkage and validate the new release with a fresh sample.

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
