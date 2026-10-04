# v1.1 true-value review

## File to complete

Open `data/outputs/v11_remediation_BATCH_TRUE_VALUE_REVIEW.csv`.

Review all 49 rows using `article_evidence`, `audit_notes`, and the source URL.
Do not change row order, identifiers, claims, evidence, or audit labels. Edit only
the `proposed_*` columns plus `reviewed_action`, `reviewed_by`, and
`review_notes`.

## Record decision

- `retain`: the event is real and usable. Fill each proposed field named by
  `recommended_actions`.
- `exclude_candidate`: the event, district, or exact date cannot be established
  well enough. Leave all proposed fields blank.
- `unclear`: evidence cannot support either decision. Leave proposed fields
  blank; this blocks release assembly.

For `review_event_existence`, `retain` may leave proposed fields blank when the
evidence confirms the existing record. Explain that confirmation in notes.

## Proposed values

- Dates: `YYYY-MM-DD`; review-only actions also allow `keep_original` or
  `unclear`.
- Districts: canonical Nepal district; review-only actions also allow
  `keep_original` or `unclear`.
- Municipality: canonical municipality, `not_established`, or a review sentinel.
- Event type: `landslide`, `road_obstruction`, or `other`.
- Hazard type: `landslide`, `debris_flow`, `rockfall`, or `other`.
- Deaths: non-negative integer or `not_reported`.

A `correct_*` value must differ from the claimed value. Set `reviewed_by` and add
a short evidence-based note on every row.

Save as:

`data/outputs/v11_remediation_BATCH_TRUE_VALUE_REVIEW_COMPLETED.csv`

Then validate with:

```bash
PYTHONPATH=src .venv/bin/python scripts/validate_v11_true_value_review.py
```
