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

## Completed article provenance mapping

The 55 identity/linkage candidates are mapped to all 124 frozen source-article
members. The pack contains 18 proposed whole-cluster exclusions, 19 singleton
article decompositions, 16 re-cluster/decomposition cases, and 2 manual
membership reviews. Mutable working-database cluster IDs were not substituted
for frozen v0.6 memberships.

## Completed reconstruction decisions

The 55-row decision sheet is complete and valid. It excludes 26 old canonical
events and reconstructs the other 29 into 100 physical-event candidates. All
124 frozen article memberships are accounted for and no cluster decision
remains unresolved. See `docs/CANONICAL_EVENT_RECONSTRUCTION_RESULT.md`.

## Completed identity plan

Date resolution and final collision review are complete. The validated identity
plan removes 55 superseded records, adds 85 new physical events, merges 12
candidates into distinct existing events, and excludes 3 reconstruction
candidates. The provisional inventory size is 2,915, a net increase of 30.

See `docs/CANONICAL_EVENT_IDENTITY_PLAN_RESULT.md`. The plan remains unapplied.

## Completed true-value plan

The 37-row true-value review is complete and release-safe. It retains and
corrects 26 existing events, excludes 11 unusable records, and has no overlap
with the identity plan. The provisional corrected inventory now contains 2,904
events, a net increase of 19 from the frozen 2,885-event release.

See `docs/CANONICAL_EVENT_TRUE_VALUE_RESULT.md`. The plan remains unapplied.

## Next scientific stage

Complete the final 27-row structured-attribute review:

`data/outputs/canonical_event_structured_attribute_REVIEW.csv`

These records have stable identity, date, and district but need evidence-backed
event type, hazard type, or death-count corrections. Follow
`docs/CANONICAL_EVENT_STRUCTURED_ATTRIBUTE_REVIEW_GUIDE.md` and save the result
as `data/outputs/canonical_event_structured_attribute_REVIEW_COMPLETED.csv`.

Then:

1. Validate and materialize the structured-attribute decisions.
2. Convert recurring correction patterns into pipeline fixes and regression tests.
3. Assemble all unapplied plans into a new versioned inventory release.
4. Re-run rainfall linkage against the corrected release.
5. Validate the corrected release with a fresh locked sample.

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
