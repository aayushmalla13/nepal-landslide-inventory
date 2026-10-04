# v1.1 structured-attribute review

## File

Open `data/outputs/v11_structured_attribute_REVIEW.csv`.

These 38 events have stable identity, date, and district. This final correction
gate reviews only event type, hazard type, or reported deaths.

## What to fill

For every row, fill `final_record_action`, `reviewed_by`, and `review_notes`.
Normally use `retain`. Use `exclude_candidate` only if the record cannot be made
release-safe, and `unclear` only when a decision genuinely cannot be reached.

Fill only final fields named by `recommended_actions`:

- `correct_event_type` -> `final_event_type`
- `correct_hazard_type` -> `final_hazard_type`
- `correct_deaths` -> `final_deaths`

Allowed event types are `landslide`, `road_obstruction`, and `other`. Allowed
hazard types are `landslide`, `debris_flow`, `rockfall`, and `other`. Deaths must
be a non-negative integer or `not_reported`. Every correction must differ from
the claimed value.

Treat `suggested_*` as hints and confirm them against `article_evidence`. For
`exclude_candidate` or `unclear`, leave every `final_*` value blank. Do not edit
or reorder frozen columns.

Save as `data/outputs/v11_structured_attribute_REVIEW_COMPLETED.csv`, then run:

```bash
PYTHONPATH=src .venv/bin/python scripts/validate_v11_structured_attribute_review.py
```
