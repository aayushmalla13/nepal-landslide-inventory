# v1.5 True-Value Review

Open `data/outputs/v15_remediation_BATCH_TRUE_VALUE_REVIEW.csv`.

Review all 25 rows using `article_evidence`, `audit_notes`, the source URL, and
`recommended_actions`. Edit only the `proposed_*` fields named by
`recommended_actions`, plus `reviewed_action`, `reviewed_by`, and
`review_notes`. Do not alter frozen columns or reorder rows.

- `retain`: the event is usable; fill every proposed field required by
  `recommended_actions`.
- `exclude_candidate`: exact event identity, date, or district cannot be
  established; leave all proposed fields blank.
- `unclear`: evidence cannot support either decision; this blocks candidate
  assembly and should be used only when further source review is required.

For a `review_*` action, use `keep_original` when the claimed value is correct
or `unclear` when it cannot be resolved. For a `correct_*` action, enter a
replacement value; it cannot equal the original claim or remain unclear.

Use `YYYY-MM-DD` dates, canonical Nepal districts and municipalities,
non-negative integer deaths or `not_reported`, and the event/hazard categories
already used by the inventory. Set `reviewed_by` to `aayush` and write a short,
evidence-based `review_notes` entry for every row.

Save as:

`data/outputs/v15_remediation_BATCH_TRUE_VALUE_REVIEW_COMPLETED.csv`
