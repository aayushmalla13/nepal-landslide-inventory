# v0.8 fresh locked validation guide

## Purpose

This is the final independent internal-validation gate for
`nepal_landslide_inventory_v0.8.0_candidate_20260923`. The 150-row stratified
probability sample excludes every previously reviewed event ID and article URL
that can be traced through the project's completed manual-review artifacts.

Do not open prior completed audit files while labeling. The new pack omits all
prior answers, model scores, confidence fields, parser decisions, and correction
metadata.

## Files

Keep these side by side:

- `data/outputs/v08_fresh_validation_LABEL_HERE.csv`
- `data/outputs/v08_fresh_validation_reading_pack.csv`

Read the article evidence, then fill only the label columns in the first file.
Do not change row order, column names, event claims, titles, or URLs.

## Labels

- `event_really_happened`: `yes`, `no`, or `unclear`.
- If the event is `yes`, fill `one_physical_event`, `district_correct`, and
  `date_correct` with `yes`, `no`, or `unclear`.
- Fill `municipality_correct` only when a municipality is claimed.
- `event_type_true`: `landslide`, `road_obstruction`, `other`, or `unclear`.
- `hazard_type_true`: `landslide`, `debris_flow`, `rockfall`, `other`, or
  `unclear`.
- `deaths_true`: a non-negative integer, `not_reported`, or `unclear`.
- For multi-article rows, `duplicate_merge_correct`: `yes`, `no`, or `unclear`.
  For one-article rows, leave it blank or use `not_applicable`.
- Use one consistent identifier in `annotator` and explain every `no` or
  `unclear` in `notes`.

Save the completed file as
`data/outputs/v08_fresh_validation_COMPLETED.csv` in UTF-8 CSV format.

## Locked decision rule

The draw manifest freezes the promotion rule before labels exist. Promotion
requires all of the following:

- Event-existence precision at least 0.90 with 95% CI lower bound at least 0.85.
- Usable-record precision at least 0.70 with 95% CI lower bound at least 0.60.
- Single-event, district, and date accuracy each at least 0.85 with 95% CI lower
  bound at least 0.75.
- No more than 5% unclear event-existence labels.

If any check fails, v0.8 remains a candidate. The thresholds must not be changed
after labels are seen.
