# v1.3 Structured-Attribute Review

Open `data/outputs/v13_structured_attribute_REVIEW.csv`.

These 24 records already have stable identity, date, and district. This final
manual gate reviews only event type, hazard type, and reported deaths.

For every row, fill `final_record_action`, `reviewed_by`, and `review_notes`.
Normally use `retain`. Use `exclude_candidate` only when the record cannot be
made release-safe, and `unclear` only when the evidence cannot support a
decision.

Fill only final fields named by `recommended_actions`:

- `correct_event_type` -> `final_event_type`
- `correct_hazard_type` -> `final_hazard_type`
- `correct_deaths` or `clear_deaths` -> `final_deaths`

Allowed event types are `landslide`, `road_obstruction`, and `other`. Allowed
hazard types are `landslide`, `debris_flow`, `rockfall`, and `other`. Deaths
must be a non-negative integer or `not_reported`. Confirm `suggested_*` values
against `article_evidence`; they are hints, not answers.

For `exclude_candidate` or `unclear`, leave all `final_*` values blank. Do not
edit frozen columns or row order. Set `reviewed_by` to `aayush`.

Save as:

`data/outputs/v13_structured_attribute_REVIEW_COMPLETED.csv`
