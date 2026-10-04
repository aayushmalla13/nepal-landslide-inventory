# v1.2 final locked validation guide

## Purpose

This is the independent validation gate for
`nepal_landslide_inventory_v1.2.0_candidate_20260929`. The 150-row stratified
probability sample excludes every traceable previously reviewed event ID and
article URL through v1.1, plus all URLs in the v1.2 correction and reviewed
merge layers.

Do not open prior completed audits while labeling. Do not inspect parser code,
confidence fields, correction files, scores, or model answers for sampled
rows. The reading pack intentionally omits those fields.

## Files

Keep these side by side:

- `data/outputs/v12_final_validation_LABEL_HERE.csv`
- `data/outputs/v12_final_validation_reading_pack.csv`

Read all article evidence for one row, then fill only the label columns in the
first file. Do not change row order, column names, event claims, titles, URLs,
or any other prefilled cell.

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
- For one-article rows, leave `duplicate_merge_correct` blank or enter
  `not_applicable`.
- Use one consistent identifier in `annotator`.
- Explain every `no` or `unclear` decision briefly in `notes`.

When `event_really_happened` is `no` or `unclear`, the remaining truth fields
may stay blank. Do not infer correctness from the balance of labels or from
earlier validation performance.

Save the completed UTF-8 file as:

`data/outputs/v12_final_validation_COMPLETED.csv`

## Locked decision rule

Promotion requires every prespecified check to pass:

- Event-existence precision >= 0.90 and 95% CI lower bound >= 0.85.
- Usable-record precision >= 0.70 and 95% CI lower bound >= 0.60.
- Single-event, district, and date accuracy each >= 0.85 with 95% CI lower
  bound >= 0.75.
- Event-existence unclear fraction <= 0.05.

If any check fails, v1.2 remains a candidate. These thresholds were inherited
unchanged and were not selected after seeing this sample.

After all 150 rows are complete, run:

```bash
PYTHONPATH=src .venv/bin/python scripts/score_v12_final_validation.py
```

The scorer first verifies the locked template, row order, frozen claims, label
vocabulary, weights, and manifest hashes. It then reports weighted estimates
and stratified-bootstrap 95% confidence intervals.

## Paper standard

The primary blinded annotation and locked weighted score support the inventory
precision claim. For a stronger paper, a second annotator should independently
label a prespecified subset before seeing the primary labels; agreement can be
reported separately and disagreements adjudicated only after both submissions
are locked.
