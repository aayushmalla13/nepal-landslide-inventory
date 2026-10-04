# Dedup collision review guide

## Files

Open these side by side:

1. `data/outputs/dedup_collision_review_BATCH_01_LABEL_HERE.csv`
2. `data/outputs/dedup_collision_review_BATCH_01_READING_PACK.csv`

The first batch contains 50 prioritized cluster pairs. The reading pack has the
same pair order and includes complete article text for both clusters. The score
and recommendation are triage aids only; they are not model answers and no
merge has been applied automatically.

## Question

Do the left and right clusters represent the same physical landslide failure?

Use the event location, ward/place wording, date, casualties, road point, and
incident narrative. Same district, municipality, and date are not enough by
themselves because several failures can occur in one municipality on one day.

## Fill four columns

- `decision`: `merge`, `keep_distinct`, or `unclear`
- `merge_survivor_event_id`: for `merge`, choose one event ID from the full
  connected merge component; leave blank otherwise. All merge rows that
  connect the same group of events must nominate that same survivor, even when
  it is not an endpoint of one particular pair.
- `reviewed_by`: a stable reviewer name such as `aayush`
- `review_notes`: a short factual reason; required for `merge` and `unclear`

Do not edit any other column or reorder rows.

Save the completed file as:

`data/outputs/dedup_collision_review_BATCH_01_COMPLETED.csv`

The completed decisions will be validated before any merge is materialized.

Batch 1 was adjudicated and applied on 2026-09-27. See
`docs/DEDUP_COLLISION_ADJUDICATION_PASS_1.md`; the instructions above remain the
protocol for subsequent batches.

Validation command:

```bash
PYTHONPATH=src .venv/bin/python scripts/validate_current_dedup_collision_review.py
```
