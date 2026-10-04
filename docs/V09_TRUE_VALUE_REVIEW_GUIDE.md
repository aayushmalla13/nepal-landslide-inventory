# v0.9 true-value review guide

## File to complete

Open:

`data/outputs/v09_remediation_BATCH_TRUE_VALUE_REVIEW.csv`

Review all 33 rows using `article_evidence`, `audit_notes`, and the source URL.
Do not change row order, column names, queue IDs, claims, evidence, or audit labels.
Only edit the six `proposed_*` columns plus `reviewed_action`, `reviewed_by`, and
`review_notes`.

Save the completed file as:

`data/outputs/v09_remediation_BATCH_TRUE_VALUE_REVIEW_COMPLETED.csv`

## Record decision

- Use `retain` when the row is a real, usable event. Fill every proposed field
  named by `recommended_actions`.
- Use `exclude_candidate` when the event, district, or exact event date cannot be
  established well enough for the inventory. Leave every `proposed_*` field blank.
- Use `unclear` only when the evidence cannot support either decision. Leave every
  `proposed_*` field blank. This blocks release assembly until resolved.

For `review_event_existence`, `retain` is valid with all proposed fields blank when
the evidence confirms the existing record. Explain the confirmation in
`review_notes`.

## Proposed values

- `correct_date` or `review_date`: `YYYY-MM-DD`; for a review-only action,
  `keep_original` or `unclear` is also allowed.
- `correct_district` or `review_district`: canonical Nepal district name; for a
  review-only action, `keep_original` or `unclear` is also allowed.
- `correct_municipality` or `review_municipality`: canonical municipality,
  `not_established`, or a review sentinel.
- Event type: `landslide`, `road_obstruction`, or `other`.
- Hazard type: `landslide`, `debris_flow`, `rockfall`, or `other`.
- Deaths: a non-negative integer or `not_reported`.

A `correct_*` value must differ from the claimed value. Use `keep_original` only
for `review_*` actions when the audit flag is a reviewed false positive. Use
`unclear` sparingly because any unresolved value blocks this gate.

Set `reviewed_by` on every row and write a short evidence-based `review_notes`.

## Validate

Run:

```bash
PYTHONPATH=src .venv/bin/python scripts/validate_v09_true_value_review.py
```

The gate passes only when the status is
`validated_true_values_not_yet_applied` and the unresolved count is zero.
