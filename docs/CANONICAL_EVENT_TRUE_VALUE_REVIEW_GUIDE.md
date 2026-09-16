# Canonical event true-value review guide

## File

Open:

`data/outputs/canonical_event_true_value_REVIEW.csv`

These 37 records represent real, single-event identities outside the completed
identity reconstruction batch. They need corrected or confirmed date, district,
event type, hazard type, or death values.

## Record decision

Fill `final_record_action` with one of:

- `retain`: evidence supports a usable corrected record.
- `exclude_candidate`: the required true value cannot be established well
  enough for the corrected release.
- `unclear`: the decision genuinely remains unresolved; this blocks release.

Use `reviewer_D` or another stable reviewer ID in `reviewed_by`, and explain the
evidence briefly in `review_notes`.

## Value fields

Fill only final fields named by `recommended_actions`:

- `correct_date` or `review_date` -> `final_event_date`
- `correct_district` or `review_district` -> `final_district`
- `correct_municipality` or `review_municipality` -> `final_municipality`
- `correct_event_type` or `review_event_type` -> `final_event_type`
- `correct_hazard_type` or `review_hazard_type` -> `final_hazard_type`
- `correct_deaths` or `review_deaths` -> `final_deaths`

For a `correct_*` action, enter a concrete replacement that differs from the
claim. For a `review_*` action, enter a concrete value, `keep_original`, or
`unclear`. An `unclear` field blocks release even when the record action is
`retain`.

Use:

- Dates as `YYYY-MM-DD`.
- Canonical English district names such as `Chitwan` or `Sindhupalchok`.
- Event types: `landslide`, `road_obstruction`, or `other`.
- Hazard types: `landslide`, `debris_flow`, `rockfall`, or `other`.
- Deaths as a non-negative integer or `not_reported`.

The `suggested_*` columns contain adjudicated structured values where one is
already available. Confirm them against the article evidence rather than
copying blindly.

For `exclude_candidate` or record-level `unclear`, leave all `final_*` value
columns blank.

Save as:

`data/outputs/canonical_event_true_value_REVIEW_COMPLETED.csv`

Do not reorder rows or edit claimed, suggested, evidence, or action columns.
