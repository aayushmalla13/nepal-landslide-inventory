# v1.4 Final Locked Validation Guide

This is the independent validation gate for
`nepal_landslide_inventory_v1.4.0_candidate_20261002`. The 150-row stratified
probability sample excludes every traceable prior reviewed event ID and article
URL through v1.3 and every v1.4 remediation layer.

Keep these files side by side:

- `data/outputs/v14_final_validation_LABEL_HERE.csv`
- `data/outputs/v14_final_validation_reading_pack.csv`

Read all article evidence for each row, then edit only label columns in the
first file. Do not inspect prior completed audits, parser code, correction
files, scores, or model answers while labeling.

- `event_really_happened`: `yes`, `no`, or `unclear`.
- If yes, fill `one_physical_event`, `district_correct`, and `date_correct`.
- Fill `municipality_correct` only when a municipality is claimed.
- `event_type_true`: `landslide`, `road_obstruction`, `other`, or `unclear`.
- `hazard_type_true`: `landslide`, `debris_flow`, `rockfall`, `other`, or `unclear`.
- `deaths_true`: a non-negative integer, `not_reported`, or `unclear`.
- For multi-article rows, fill `duplicate_merge_correct`; for one-article rows,
  leave it blank or use `not_applicable`.
- Use `aayush` consistently in `annotator` and explain each `no` or `unclear`.

Save as:

`data/outputs/v14_final_validation_COMPLETED.csv`

The unchanged locked promotion rule requires event precision >= 0.90 with CI
lower bound >= 0.85, usable-record precision >= 0.70 with CI lower bound >=
0.60, single-event/district/date accuracy each >= 0.85 with CI lower bounds >=
0.75, and event-unclear fraction <= 0.05.
