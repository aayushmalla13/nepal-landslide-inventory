# Do this next - audit-driven corrected release

**Status:** the frozen pipeline, independent canonical-event review,
third-reviewer adjudication, two corrected-candidate cycles, fresh rainfall
linkage, refreshed external validation, and the final v0.8 fresh locked audit
are complete as of 2026-09-24. The prespecified audit decision is to retain
candidate status; v0.8 is not promoted.

## Current mutable inventory

Dedup collision adjudication pass 1 is applied to the working pipeline as of
2026-09-27. The original 50-row review remains unchanged; its adjudicated copy
contains 45 merges and five keep-distinct decisions, consolidated into 40
persistent URL-anchored merge components. Fourteen structural article fixes
were added to the existing correction layer, followed by two reviewed
follow-up date fixes. The working inventory now contains 2,605 canonical
events, down from 2,656 before this pass.

The final CSV and pre/post SQLite snapshots are synchronized and the full test
suite passes. This working state has not inherited accuracy metrics from any
earlier frozen release and needs a newly locked validation sample before it can
be promoted. See `docs/DEDUP_COLLISION_ADJUDICATION_PASS_1.md`.

That next gate is now prepared. The exact 2,605-event state is frozen as
`nepal_landslide_inventory_v1.0.0_candidate_20260927`, and all release bundle
checks pass. A blinded 150-row stratified probability sample was drawn from
1,557 eligible never-reviewed events after excluding 633 reviewed event IDs
and 1,975 reviewed article URLs. No sampled article lacks evidence, all label
fields are blank, and a repeated draw is byte-identical.

The current human action is to complete
`data/outputs/v10_final_validation_LABEL_HERE.csv` beside
`data/outputs/v10_final_validation_reading_pack.csv`, following
`docs/V10_FINAL_VALIDATION_GUIDE.md`, and save the result as
`data/outputs/v10_final_validation_COMPLETED.csv`. Do not inspect prior
completed audits while labeling. See `docs/V10_FINAL_VALIDATION_DRAW.md`.

The v1.0 locked audit is now complete. Event-existence precision passes at
0.945 (95% CI 0.903-0.979), as do district accuracy and the unclear-fraction
gate. Promotion fails because usable-record precision is 0.510
(0.421-0.592), single-event accuracy is 0.821 (0.760-0.878), and date accuracy
is 0.789 (0.714-0.858). The release remains a candidate; see
`docs/V10_FINAL_VALIDATION_RESULT.md`.

The skipped downstream `event_typing` stage that caused the frozen candidate's
0.509 event-type accuracy is repaired in the mutable pipeline, and final export
now fails closed when typing is incomplete. The v1.1 remediation queue is
frozen with 123 findings: 36 article-mapping, 49 true-value, and 38 structured-
attribute rows. Work next on
the generated `data/outputs/v11_article_mapping_DECISIONS.csv` beside
`data/outputs/v11_article_membership_MAP.csv`; do not edit the raw remediation
batch or apply later attribute batches until those identity decisions are
complete. See `docs/V11_ARTICLE_MAPPING_GUIDE.md`.

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

## Completed post-correction identity plan

The final candidate collision gate is complete. All 42 eligible candidates were
retained as distinct events, and the bundle-safe plan contains 61
old-event removals, 42 new events, 11 merges into existing events, 29 date-based
candidate exclusions, and 11 blocked candidates. Six reviewed old events remain
unchanged. See `docs/POST_CORRECTION_IDENTITY_PLAN_RESULT.md`.

## Completed post-correction true-value plan

The 45-row true-value review is complete and release-safe. It produces 31
planned corrections, 13 exclusions, and one reviewed no-change alias decision,
with no overlap with the identity plan. After the identity and true-value
plans, the provisional inventory contains 2,872 events, a net change of -32
from the 2,904-row v0.7 source candidate.

See `docs/POST_CORRECTION_TRUE_VALUE_RESULT.md`. This plan is now applied only
in the v0.8 post-correction candidate described below.

## Completed post-correction structured-attribute plan

The final 25-row manual gate is complete and release-safe. All 25 events are
retained with 13 event-type, six hazard-type, and 10 death-value corrections.
There are no unresolved decisions, exclusions, or overlaps with earlier plans.

All post-correction manual gates are now complete. Before assembly, the combined
plans projected a 2,872-event inventory, a net change of -32 from the 2,904-row
v0.7 source candidate. See
`docs/POST_CORRECTION_STRUCTURED_ATTRIBUTE_RESULT.md`.

## Completed post-correction candidate assembly

The validated plans have been applied to
`nepal_landslide_inventory_v0.8.0_candidate_20260923`. The candidate contains
2,872 unique events, and its canonical CSV, SQLite snapshot, 212-row correction
log, provenance table, normalization table, manifest, and bundle lock reconcile.
The repository release verifier accepts the bundle.

The release remains `pending_fresh_validation`; earlier precision and accuracy
metrics must not be attributed to it. See
`docs/POST_CORRECTION_CANDIDATE_RESULT.md`.

## Completed post-correction rainfall linkage

The unchanged rainfall design has been rerun against the exact v0.8 candidate
and frozen as `nepal_landslide_rainfall_v0.9.0_20260923`. The release contains
1,453 primary case-days and 6,059 controls. Concurrent R5 remains 51.6 mm with
temporal-test AUC 0.677; strictly antecedent R3 remains 23.7 mm with AUC 0.651.

The 34-file bundle passes strict checksum verification and includes a case-
integrity audit plus sensitivity analysis. Excluding all 60 flagged case-days
left every all-years cutpoint unchanged and shifted AUC by at most +0.0042. See
`docs/POST_CORRECTION_RAINFALL_RESULT.md`.

## Completed post-correction external validation

The six-layer BIPAD agreement analysis has been rerun against the exact v0.8
candidate and frozen as
`nepal_landslide_external_validation_v0.1.0_20260923`. It compares 2,868
eligible news events with 5,345 BIPAD rows harmonized to 4,095 incident
clusters. Tier A observed overlap is 0.1510 versus 0.0613 expected by chance;
chance-corrected overlap is 0.0897.

The bundle includes a normalized BIPAD input snapshot and records both source
hashes. It passes strict checksum verification. BIPAD is not ground truth, so
the result is framed as agreement and no precision/recall claim is made. See
`docs/POST_CORRECTION_EXTERNAL_VALIDATION_RESULT.md`.

## Completed parser remediation

The first generalizable remediation pass addresses preparedness and planned
works, unrelated or foreign primary incidents, retrospective totals, and strong
multi-location markers. On the selected 66 known false/aggregate audit URLs,
the current classifier rejection count increased from 19 to 31. This is a
development diagnostic, not a precision estimate. See
`docs/PARSER_REMEDIATION_PASS_1.md`.

The second conservative pass adds explicit plural-road, separate-incident, and
multiple-failure-site handling. Database replay now rejects 41 of the same 66
known failures, leaving 25 for location/date-role or cluster-level repair. The
human-labelled development pack shows no sampled single-event regression. See
`docs/PARSER_REMEDIATION_PASS_2.md`.

The third pass fixes the remaining generalizable location-role pattern: a
Kathmandu desk dateline or route endpoint beating unanimous municipalities at
the physical road failure. PCR-002 now resolves to Nawalpur and PCR-008 to
Makwanpur. Broader variants were corpus-tested and rejected as unsafe. See
`docs/PARSER_REMEDIATION_PASS_3.md`.

## Next scientific stage

The final v0.8 audit is complete. Weighted event-existence precision is 0.889
(95% CI 0.837-0.937), strict usable-record precision is 0.463 (0.381-0.545),
single-event accuracy is 0.744 (0.671-0.814), district accuracy is 0.865
(0.805-0.921), and date accuracy is 0.792 (0.714-0.862). Four prespecified
checks failed. See `docs/V08_FRESH_VALIDATION_RESULT.md`.

The v0.9 remediation queue is now frozen with 112 findings partitioned into 54
article-mapping rows, 33 true-value rows, and 25 structured-attribute rows. The
current article-mapping pack links its 54 decisions to 78 full-text source
articles. See `docs/V09_REMEDIATION_QUEUE.md`.

Article mapping is complete and validated. It produced 49 reconstruction
candidates, 17 excluded memberships, and 18 unresolved originals retained
unchanged. The existing-event collision screen contains 21 high/medium review
rows and 28 low/no-match rows.

The identity gates are complete. Bundle-level safety leaves 26 new events, 10
merges, 2 excluded candidates, and 11 blocked candidates inside 5 retained
old-event bundles. All 26 final candidates were confirmed as distinct. The
unapplied identity plan safely supersedes 31 old events and projects 2,867
rows, a net change of -5 from v0.8.

The 33-row true-value and 25-row structured-attribute gates are complete. A
single documented encoding normalization converted explicit no-casualty
evidence from blank/not-reported to zero deaths.

The checksummed v0.9 candidate is assembled at
`data/releases/nepal_landslide_inventory_v0.9.0_candidate_20260924/`. It contains
2,858 events, a net change of -14 from v0.8. All CSV/SQLite, action-log, district,
checksum, and bundle-lock checks pass. See `docs/V09_CANDIDATE_RESULT.md`.

The final v0.9 audit is complete and valid, but four prespecified checks fail.
Weighted event-existence precision is 0.811, usable-record precision 0.370,
single-event accuracy 0.678, district accuracy 0.891, and date accuracy 0.748.
The decision is to retain candidate status. See
`docs/V09_FINAL_VALIDATION_RESULT.md`.

Do not draw a small confirmation sample, promote v0.9, or rerun final rainfall
and external-validation releases against it.

Parser remediation pass 4 is complete. The full working pipeline was rebuilt
to 2,219 canonical events. All 26 spent-audit false-event representatives are
now excluded from canonical clustering, filter reruns are idempotent, and the
canonical gate admits zero rows with `specificity_ok = 0`. These are development
diagnostics, not a new precision estimate. See
`docs/PARSER_REMEDIATION_PASS_4.md`.

Dedup linkage repair pass 5 is complete. The working pipeline now contains
2,656 canonical events, no cluster spans more than one day, casualty conflicts
veto automatic merges, and cross-language merges require corroborating factual
signals. Two additional spent-audit multi-failure aggregates are rejected. The
328 current same-identity groups (451 extra clusters) are review candidates,
not confirmed missed merges. See `docs/DEDUP_LINKAGE_REPAIR_PASS_5.md`.

The current collision review pack is built and checksummed. It contains 645
possible cluster pairs: 25 P1 likely merges, 160 P2 possible merges, 226
conflict/likely-distinct pairs, and 234 weak-evidence pairs. Batch 1 contains
all 25 P1 pairs plus the top 25 P2 pairs. See
`docs/DEDUP_COLLISION_REVIEW_GUIDE.md`.

1. Complete and validate Batch 1 of the current collision review; materialize
   only explicit reviewed merges.
2. Review the remaining confirmed-event representatives excluded by the
   specificity gate, separating date/role corrections from cases requiring
   safe decomposition.
3. Keep the automated secondary-event extractor unwired; its locked precision
   gate failed.
4. Rerun the full pipeline into a new versioned candidate after reviewed
   identity repairs.
5. Draw one new independent probability audit using the unchanged frozen
   promotion rule.

Do not promote v0.7.0 or v0.8.0, rerun rainfall linkage against v0.7.0, or reuse
the current 200 validation rows as evidence for the repaired candidate.

## Preserved evidence

- Frozen inventory: `data/releases/nepal_landslide_inventory_v0.6.0_v7_20260915/`
- Frozen rainfall: `data/releases/nepal_landslide_rainfall_v0.8.0_20260915/`
- Adjudicated labels: `data/outputs/canonical_event_audit_ADJUDICATED.csv`
- Adjudication provenance: `data/outputs/canonical_event_audit_adjudication_manifest.json`
- Definitive score: `data/outputs/canonical_event_audit_adjudicated_score.json`
- Agreement report: `data/outputs/canonical_event_audit_interannotator_agreement.md`
- Final manual-gate plan: `data/outputs/canonical_event_structured_attribute_plan_manifest.json`
- First corrected candidate: `data/releases/nepal_landslide_inventory_v0.7.0_candidate_20260916/`
- Post-correction candidate: `data/releases/nepal_landslide_inventory_v0.8.0_candidate_20260923/`
- Post-correction rainfall: `data/releases/nepal_landslide_rainfall_v0.9.0_20260923/`
- Post-correction external validation: `data/releases/nepal_landslide_external_validation_v0.1.0_20260923/`
- Final fresh-audit manifest: `data/outputs/v08_fresh_validation_manifest.json`
- Final fresh-audit result: `docs/V08_FRESH_VALIDATION_RESULT.md`
- v0.9 remediation queue: `docs/V09_REMEDIATION_QUEUE.md`

## Submission decisions still needed

1. Author names, affiliations, ORCIDs, and corresponding-author email.
2. CRediT contribution initials.
3. Funding statement.
4. Gazetteer licensing choice in `docs/MANUSCRIPT_DECLARATIONS.md`.
5. Target journal and required AI-use disclosure wording.
