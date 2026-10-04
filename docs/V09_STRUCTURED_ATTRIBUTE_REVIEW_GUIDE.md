# v0.9 structured-attribute review guide

## File

Open:

`data/outputs/v09_structured_attribute_REVIEW.csv`

These 25 events have stable identity, date, and district. This final manual gate
confirms only event type, hazard type, or reported deaths.

## What to fill

For every row, fill:

- `final_record_action`: normally `retain`; use `exclude_candidate` only if the
  evidence shows the record cannot be made release-safe, and `unclear` only when
  a decision genuinely cannot be reached.
- `reviewed_by`: use the same stable reviewer ID on every row.
- `review_notes`: briefly state the decisive evidence.

Fill only final fields named by `recommended_actions`:

- `correct_event_type` -> `final_event_type`
- `correct_hazard_type` -> `final_hazard_type`
- `correct_deaths` -> `final_deaths`

Use these exact values:

- Event type: `landslide`, `road_obstruction`, or `other`
- Hazard type: `landslide`, `debris_flow`, `rockfall`, or `other`
- Deaths: a non-negative integer or `not_reported`

Every correction must differ from its claimed value. A confirmed zero death
count is `0`; use `not_reported` only when the evidence does not establish a
count. Treat `suggested_*` as audit hints, not answers, and confirm each against
`article_evidence`.

For `exclude_candidate` or `unclear`, leave all `final_*` value columns blank.
Do not edit or reorder existing rows or frozen columns.

## Save and validate

Save the UTF-8 CSV as:

`data/outputs/v09_structured_attribute_REVIEW_COMPLETED.csv`

Then run:

```bash
PYTHONPATH=src .venv/bin/python scripts/validate_v09_structured_attribute_review.py
```

The gate passes only with status
`validated_structured_attributes_not_yet_applied` and zero unresolved rows.
