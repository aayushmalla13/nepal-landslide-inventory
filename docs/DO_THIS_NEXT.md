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

## Next scientific stage

The preliminary collision gate is complete for 91 dated candidates. It found
199 broad candidate pairs: 3 high tier, 36 medium tier, and 160 low tier, with
no source-URL overlaps.

The nine-row date review is complete: eight dates were resolved and one
candidate was excluded. Final collision screening now covers 99 candidates and
found 4 high-tier, 40 medium-tier, and 166 low-tier pairs; no source URLs
overlap.

Complete the 99-row final decision sheet by following
`docs/CANONICAL_EVENT_COLLISION_REVIEW_GUIDE.md`:

`data/outputs/canonical_event_reconstruction_FINAL_COLLISION_DECISIONS.csv`

Save it as
`data/outputs/canonical_event_reconstruction_FINAL_COLLISION_DECISIONS_COMPLETED.csv`.
Rows marked `unclear` will block correction application.

Do not insert the 100 candidates directly. Their provisional +45 event-count
delta can shrink after collision review.

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
