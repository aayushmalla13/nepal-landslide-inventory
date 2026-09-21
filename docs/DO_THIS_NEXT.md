# Do this next - audit-driven corrected release

**Status:** the frozen pipeline, independent canonical-event review,
third-reviewer adjudication, corrected candidate, and locked post-correction
validation are complete as of 2026-09-21. The candidate did not advance.

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

## Completed structured-attribute plan

The final 27-row structured-attribute review is complete and release-safe. All
27 events are retained with 15 event-type changes, 7 hazard-type changes, and
10 death-count changes. There are no exclusions, unresolved values, or overlaps
with earlier correction gates.

All manual correction gates are now complete. The consolidated provisional
inventory contains 2,904 events, a net increase of 19 from the frozen release.
See `docs/CANONICAL_EVENT_STRUCTURED_ATTRIBUTE_RESULT.md`.

## Post-correction validation decision

The locked 150-row fresh probability sample and separate 50-row correction
challenge are complete and reproducibly scored. The fresh sample estimated:

- Event existence precision: 0.833 (95% CI 0.774-0.888)
- Strict usable-record precision: 0.358 (0.284-0.437)
- Single-event accuracy: 0.704 (0.623-0.779)
- District accuracy: 0.799 (0.731-0.864)
- Date accuracy: 0.743 (0.658-0.824)
- Event-type accuracy: 0.683 (0.616-0.752)

The correction challenge passed 0.977 of 43 decisive targeted checks, with
seven unclear rows. It confirms that the reviewed correction plans were mostly
applied correctly, but it cannot replace the fresh probability estimate.

No numeric promotion threshold was prespecified. The candidate is not promoted
because the fresh sample directly contains 23 confirmed non-events and 43
multi-event failures among 126 confirmed events, alongside material attribute
errors. See `docs/POST_CORRECTION_VALIDATION_RESULT.md`.

## Completed remediation queue

The two completed post-correction audits are now frozen into a reproducible
137-row remediation queue: 124 fresh-sample findings and 13 challenge findings.
The queue contains 106 P0 identity/linkage rows, 27 P1 attribute rows, and four
P2 uncertain rows. It partitions into 67 article-mapping, 45 true-value, and 25
structured-attribute rows. No correction has been applied.

See `docs/POST_CORRECTION_REMEDIATION_QUEUE.md` and
`data/outputs/post_correction_remediation_manifest.json`.

## Next scientific stage

1. Build and complete the article-level evidence and decision pack for the 67
   article-mapping rows.
2. Resolve false-event exclusions, multi-event decomposition, and article
   re-clustering before changing dates, locations, or structured attributes.
3. Convert recurring patterns into parser, specificity, and deduplication
   fixes with regression tests.
4. Complete the 45-row true-value gate, then the 25-row structured-attribute
   gate against the stabilized event identities.
5. Assemble a new checksummed candidate and draw a newly locked probability
   sample excluding every previously reviewed event and article.

Do not promote v0.7.0, rerun rainfall linkage against it, or reuse the current
200 validation rows as evidence for a repaired candidate.

## Preserved evidence

- Frozen inventory: `data/releases/nepal_landslide_inventory_v0.6.0_v7_20260915/`
- Frozen rainfall: `data/releases/nepal_landslide_rainfall_v0.8.0_20260915/`
- Adjudicated labels: `data/outputs/canonical_event_audit_ADJUDICATED.csv`
- Adjudication provenance: `data/outputs/canonical_event_audit_adjudication_manifest.json`
- Definitive score: `data/outputs/canonical_event_audit_adjudicated_score.json`
- Agreement report: `data/outputs/canonical_event_audit_interannotator_agreement.md`
- Final manual-gate plan: `data/outputs/canonical_event_structured_attribute_plan_manifest.json`
- Corrected candidate: `data/releases/nepal_landslide_inventory_v0.7.0_candidate_20260916/`

## Submission decisions still needed

1. Author names, affiliations, ORCIDs, and corresponding-author email.
2. CRediT contribution initials.
3. Funding statement.
4. Gazetteer licensing choice in `docs/MANUSCRIPT_DECLARATIONS.md`.
5. Target journal and required AI-use disclosure wording.
