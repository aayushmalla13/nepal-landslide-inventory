# Post-correction structured-attribute plan result

## Outcome

The 25-row post-correction structured-attribute review is complete,
release-safe, and materialized as a checksummed unapplied plan.

- All 25 reviewed events are retained.
- All 25 events receive at least one planned attribute correction.
- The plan contains 13 event-type, six hazard-type, and 10 death-value changes.
- No decision or field remains unresolved.
- No event overlaps the identity or true-value correction plans.
- No additional event exclusion is required at this gate.

## Combined manual-plan effect

All post-correction manual gates are now complete. Starting from the 2,904-row
v0.7 source candidate, the combined identity and true-value plans produce a
2,872-event provisional inventory. This structured-attribute plan changes
attributes only, so the provisional count remains 2,872, a net change of -32.

No canonical release CSV, database, or rainfall linkage was modified.

## Reproducibility

- Completed review:
  `data/outputs/post_correction_structured_attribute_REVIEW_COMPLETED.csv`
- Validator: `scripts/validate_post_correction_structured_attribute_review.py`
- Validation result:
  `data/outputs/post_correction_structured_attribute_review_validation.json`
- Materializer:
  `scripts/materialize_post_correction_structured_attribute_plan.py`
- Corrections:
  `data/outputs/post_correction_structured_attribute_plan_CORRECTIONS.csv`
- Exclusions:
  `data/outputs/post_correction_structured_attribute_plan_EXCLUSIONS.csv`
- Plan manifest:
  `data/outputs/post_correction_structured_attribute_plan_manifest.json`
- Plan report:
  `data/outputs/post_correction_structured_attribute_plan_report.md`

The manifests pin the review template, completed decisions, earlier manual
plans, source candidate, and generated plan tables by SHA-256.

## Next stage

Assemble a new versioned and checksummed candidate from the identity,
true-value, and structured-attribute plans. Reconcile its CSV and SQLite
snapshot before rerunning rainfall, external validation, and a fresh locked
independent audit. Do not promote the candidate before that audit passes.
