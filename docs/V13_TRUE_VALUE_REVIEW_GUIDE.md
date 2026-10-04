# v1.3 True-Value Review

Open `data/outputs/v13_remediation_BATCH_TRUE_VALUE_REVIEW_PREFILLED.csv`.

The sheet has 45 rows. Fifteen rows are already complete using the locked v1.3
date-remediation replay. Seven additional rows have their verified
`proposed_event_date` prefilled. Review only the 30 rows where
`reviewed_action` is blank.

Use `article_evidence`, `audit_notes`, the source URL, and
`recommended_actions`. Edit only the `proposed_*` fields named by
`recommended_actions`, plus `reviewed_action`, `reviewed_by`, and
`review_notes`. Do not alter prefilled values or frozen columns.

- `retain`: the event is usable; fill every required proposed field.
- `exclude_candidate`: exact identity, date, or district cannot be established;
  leave the remaining proposed fields blank.
- `unclear`: evidence cannot support either decision; this blocks assembly.

Use `YYYY-MM-DD` dates, canonical Nepal districts and municipalities,
non-negative integer deaths or `not_reported`, and the event/hazard categories
already used by the inventory. Set `reviewed_by` to `aayush` and write a short
evidence-based note.

Save as:

`data/outputs/v13_remediation_BATCH_TRUE_VALUE_REVIEW_COMPLETED.csv`
