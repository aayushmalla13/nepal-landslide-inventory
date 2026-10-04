# v0.9 remediation queue

## Status

**Frozen and unapplied.**

The failed v0.8 validation has been converted into 112 unique, traceable
findings. Each queue row preserves the original claims, labels, article
evidence, sampling provenance, recommended actions, certainty, and source.

## Ordered gates

| Gate | Rows | Purpose |
|---|---:|---|
| Article mapping | 54 | Exclude false events and resolve aggregates or incorrect clusters |
| True-value review | 33 | Resolve dates, districts, municipalities, and uncertain values |
| Structured attributes | 25 | Apply event type, hazard type, and casualty corrections |

The three batches partition all 112 rows exactly. There are 87 P0 identity or
linkage findings and 25 P1 attribute findings. No correction has been applied.

## Main issue families

| Issue family | Rows |
|---|---:|
| Event date resolution | 43 |
| Event granularity | 39 |
| Event type classification | 37 |
| Location role resolution | 25 |
| Casualty extraction | 19 |
| Scope or event specificity | 18 |
| Hazard type classification | 9 |
| Deduplication | 8 |

## Completed article-mapping gate

The article-mapping pack contains 54 decisions and 78 source articles:

- 24 proposed source-article decompositions
- 15 proposed whole-cluster exclusions
- 8 proposed re-cluster-and-decompose decisions
- 7 manual membership reviews

The completed decisions validate after a documented conservative normalization.
The original submitted file remains preserved. Eighteen unresolved originals
are retained unchanged; 36 resolved originals produce 49 physical-event
candidates and 17 excluded article memberships. The provisional identity delta
is +13 before collision decisions.

## Completed existing-event collision gate

The existing-event screen compares all 49 candidates with 2,836 unaffected
v0.8 events. It generated 142 pairs: 5 candidates have a high-tier top match,
16 medium, 16 low, and 12 no candidate match.

The existing-event gate is now complete: 26 candidates remain eligible as new
events, 10 merges are safe, 2 candidates are excluded, and 11 candidates in 5
unclear old-event bundles are blocked and retained unchanged.

## Completed final identity gate

The final identity gate contained 26 candidate decisions and 25
candidate-to-candidate pairs. All 26 were confirmed as distinct `new_event`
records, with no unresolved decision. The provenance-checked identity plan
contains 31 old-event removals, 26 new events, 10 merges into existing events,
2 excluded candidates, and 11 blocked candidates. Twenty-three reviewed old
events remain unchanged: 18 mapping-unclear records and 5 collision-blocked
bundles. The provisional identity layer contains 2,867 rows, a net change of
-5 from v0.8.

## Current gate

All manual remediation gates are complete. The true-value plan contains 24
corrections, 8 exclusions, and 1 reviewed no-change decision. The structured-
attribute plan contains 25 corrections and no exclusions.

The v0.9 release preflight excludes one additional Dahikhola candidate because
the source supports a Dailekh/Kalikot boundary location but not the single
canonical district required by the schema. The assembled v0.9 candidate
contains 2,858 events and passes all release-integrity checks. The current gate
is a new independent locked audit; see `docs/V09_CANDIDATE_RESULT.md`.

## Reproducibility

- Queue builder: `scripts/build_v09_remediation_queue.py`
- Queue manifest: `data/outputs/v09_remediation_manifest.json`
- Mapping-pack builder: `scripts/build_v09_article_mapping_pack.py`
- Mapping manifest: `data/outputs/v09_article_mapping_manifest.json`
- Mapping validator: `scripts/validate_v09_article_mapping.py`
- Original mapping submission: `data/outputs/v09_article_mapping_DECISIONS_SUBMITTED.csv`
- Mapping normalization manifest: `data/outputs/v09_article_mapping_normalization_manifest.json`
- Reconstruction manifest: `data/outputs/v09_reconstruction_manifest.json`
- Collision manifest: `data/outputs/v09_collision_manifest.json`
- Collision validator: `scripts/validate_v09_collision_decisions.py`
- Existing-collision outcome manifest: `data/outputs/v09_existing_collision_outcomes_manifest.json`
- Final collision manifest: `data/outputs/v09_final_collision_manifest.json`
- Final collision validator: `scripts/validate_v09_final_collisions.py`
- Identity-plan materializer: `scripts/materialize_v09_identity_plan.py`
- Identity-plan manifest: `data/outputs/v09_identity_plan_manifest.json`
- True-value guide: `docs/V09_TRUE_VALUE_REVIEW_GUIDE.md`
- True-value validator: `scripts/validate_v09_true_value_review.py`
- True-value plan manifest: `data/outputs/v09_true_value_plan_manifest.json`
- Structured-review builder: `scripts/build_v09_structured_attribute_review.py`
- Structured-review guide: `docs/V09_STRUCTURED_ATTRIBUTE_REVIEW_GUIDE.md`
- Structured-review validator: `scripts/validate_v09_structured_attribute_review.py`
- Structured plan manifest: `data/outputs/v09_structured_attribute_plan_manifest.json`
- Release-preflight manifest: `data/outputs/v09_release_preflight_manifest.json`
- Candidate assembler: `scripts/assemble_v09_candidate_release.py`
- Candidate result: `docs/V09_CANDIDATE_RESULT.md`
