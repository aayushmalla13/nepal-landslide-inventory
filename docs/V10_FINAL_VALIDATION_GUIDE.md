# v1.0 final locked validation guide

## Purpose

This is the independent validation gate for
`nepal_landslide_inventory_v1.0.0_candidate_20260927`. The 150-row stratified
probability sample excludes every traceable previously reviewed event ID and
article URL, including all earlier locked audits and the current dedup
collision review.

Do not open prior completed audits while labeling. The reading pack omits
prior answers, scores, confidence fields, parser decisions, and correction
metadata.

## Files

Keep these side by side:

- `data/outputs/v10_final_validation_LABEL_HERE.csv`
- `data/outputs/v10_final_validation_reading_pack.csv`

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
- For multi-article rows, `duplicate_merge_correct`: `yes`, `no`, or
  `unclear`. For one-article rows, leave it blank or use `not_applicable`.
- Use one consistent identifier in `annotator` and explain every `no` or
  `unclear` in `notes`.

Save the completed UTF-8 file as:

`data/outputs/v10_final_validation_COMPLETED.csv`

## Locked decision rule

Promotion requires every prespecified check to pass:

- Event-existence precision >= 0.90 and 95% CI lower bound >= 0.85.
- Usable-record precision >= 0.70 and 95% CI lower bound >= 0.60.
- Single-event, district, and date accuracy each >= 0.85 with 95% CI lower
  bound >= 0.75.
- Event-existence unclear fraction <= 0.05.

If any check fails, v1.0 remains a candidate. These thresholds were not
changed after seeing this sample.

## Score

After completion run:

```bash
PYTHONPATH=src .venv/bin/python scripts/score_v10_final_validation.py
```
