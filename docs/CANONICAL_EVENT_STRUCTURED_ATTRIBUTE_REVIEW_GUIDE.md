# Canonical event structured-attribute review guide

## File

Open:

`data/outputs/canonical_event_structured_attribute_REVIEW.csv`

These 27 records have stable event identity, date, and district. This final
manual gate confirms event type, hazard type, or reported deaths before the
corrected release is assembled.

## Record decision

Fill `final_record_action` with one of:

- `retain`: evidence supports a usable corrected record.
- `exclude_candidate`: the record cannot be made release-safe from the evidence.
- `unclear`: the decision remains unresolved and blocks release.

Enter a stable reviewer ID in `reviewed_by` and briefly explain the evidence in
`review_notes`.

## Final values

Fill only the fields named by `recommended_actions`:

- `correct_event_type` -> `final_event_type`
- `correct_hazard_type` -> `final_hazard_type`
- `correct_deaths` -> `final_deaths`

Use:

- Event types: `landslide`, `road_obstruction`, or `other`.
- Hazard types: `landslide`, `debris_flow`, `rockfall`, or `other`.
- Deaths: a non-negative integer or `not_reported`.

Every correction must differ from the claimed value. Treat `not_reported` as a
concrete value when the article does not establish a death count; use `unclear`
only when the review itself is unresolved.

The `suggested_*` values come from adjudication. Confirm them against
`article_evidence` rather than copying them blindly. For `exclude_candidate` or
record-level `unclear`, leave all three final value fields blank.

Save as:

`data/outputs/canonical_event_structured_attribute_REVIEW_COMPLETED.csv`

Do not reorder rows or edit claimed, suggested, evidence, or action columns.
