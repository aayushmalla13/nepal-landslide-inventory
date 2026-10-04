# Post-correction true-value plan result

## Outcome

The 45-row post-correction true-value review is complete, release-safe, and
materialized as a checksummed unapplied plan.

- 31 existing events have planned true-value corrections.
- 13 existing events have planned exclusions because an essential event,
  district, or exact date could not be established.
- One reviewed row is retained unchanged because the source municipality name
  is an alias of the inventory's existing canonical municipality.
- No reviewed event overlaps an old-event removal or existing-event merge in
  the post-correction identity plan.
- No decision or field remains unresolved.

The planned corrections comprise 16 event-date, 13 district, three
municipality, 10 event-type, eight hazard-type, and four death-value changes.
A correction row can change more than one field.

## Inventory effect

The post-correction identity plan contains 2,885 provisional events. Applying
the 13 true-value exclusions would reduce this to 2,872 events. Relative to the
2,904-row v0.7 source candidate, the combined identity and true-value plans
produce a net change of -32 events.

This is not a promoted inventory and no canonical release file or database was
modified.

## Reproducibility

- Completed review:
  `data/outputs/post_correction_remediation_BATCH_TRUE_VALUE_REVIEW_COMPLETED.csv`
- Validator: `scripts/validate_post_correction_true_value_review.py`
- Validation result:
  `data/outputs/post_correction_true_value_review_validation.json`
- Materializer: `scripts/materialize_post_correction_true_value_plan.py`
- Corrections: `data/outputs/post_correction_true_value_plan_CORRECTIONS.csv`
- Exclusions: `data/outputs/post_correction_true_value_plan_EXCLUSIONS.csv`
- Reviewed no-change decision:
  `data/outputs/post_correction_true_value_plan_NO_CHANGE.csv`
- Plan manifest: `data/outputs/post_correction_true_value_plan_manifest.json`
- Plan report: `data/outputs/post_correction_true_value_plan_report.md`

The validation and plan manifests pin the completed review, frozen template,
v0.7 source candidate, identity-plan inputs, and all generated plan outputs by
SHA-256.

## Next gate

Complete and validate the 25-row structured-attribute batch before assembling a
new checksummed candidate. Do not apply this plan independently, promote the
candidate, or rerun rainfall linkage yet.
