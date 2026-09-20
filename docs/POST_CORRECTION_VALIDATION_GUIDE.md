# Post-correction validation guide

## Purpose

This gate validates the 2,904-event corrected candidate before it can become a
final paper release. It has two separate samples that must never be pooled:

- **Fresh probability sample (150 rows):** estimates precision and attribute
  accuracy on events untouched by the earlier audit and correction process.
- **Correction challenge (50 rows):** checks reconstructed, merged, and
  attribute-corrected records. It is targeted QA, not an overall precision
  estimate.

## Files to label

For the fresh sample, keep these side by side:

- `data/outputs/post_correction_fresh_audit_LABEL_HERE.csv`
- `data/outputs/post_correction_fresh_audit_reading_pack.csv`

For the correction challenge, keep these side by side:

- `data/outputs/post_correction_challenge_LABEL_HERE.csv`
- `data/outputs/post_correction_challenge_reading_pack.csv`

Do not open earlier completed canonical-audit labels while reviewing these
files. Prior answers, scores, and model confidence fields are intentionally
absent.

## Labels

Use the same policy as the prior canonical audit:

- `event_really_happened`: `yes`, `no`, or `unclear`.
- `one_physical_event`: whether this row represents one physical failure.
- `district_correct`, `date_correct`, `municipality_correct`: `yes`, `no`, or
  `unclear`. Municipality may stay blank when none is claimed.
- `event_type_true`: `landslide`, `road_obstruction`, `other`, or `unclear`.
- `hazard_type_true`: `landslide`, `debris_flow`, `rockfall`, `other`, or
  `unclear`.
- `deaths_true`: integer, `not_reported`, or `unclear`.
- `duplicate_merge_correct`: `yes`, `no`, or `unclear`.
- `annotator`: use one consistent identifier.
- `notes`: explain close calls and every `no` or `unclear` decision.

Complete the fresh sample first. Save it as
`post_correction_fresh_audit_COMPLETED.csv`. Then complete the challenge and
save it as `post_correction_challenge_COMPLETED.csv`. Keep row order, columns,
and claim values unchanged.

## Interpretation

Only the weighted fresh probability sample can estimate post-correction
release precision. The challenge sample reports pass rates by correction layer
and identifies residual implementation errors. A strong challenge result cannot
replace or inflate the fresh-sample estimate.
