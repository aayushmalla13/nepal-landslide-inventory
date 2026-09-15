# Secondary locked test v8 labeling guide

## Open these two files

1. `data/outputs/secondary_locked_v8_LABEL_HERE.csv`
2. `data/outputs/secondary_locked_v8_reading_pack.csv`

Keep them side by side. They contain the same articles in the same order.

Do not open `secondary_locked_v8_DO_NOT_OPEN_predictions.csv`. It contains the
extractor's answers, strata, and weights. Seeing it before finishing the labels
invalidates the blind test.

## What to label

Read the title and enough of the full article to identify distinct landslide
events. A distinct event needs a district and occurrence date supported by the
article. Do not infer a date merely from the publication date.

Fill these columns:

- `primary_district_date_true`: the district-day that is the article's main
  subject, written as `District|YYYY-MM-DD`. Use `unclear` if it cannot be
  resolved.
- `additional_district_dates_true`: every other supported landslide district-day,
  separated by semicolons. Write `none` if there are no additional events, or
  `unclear` if the article clearly reports additional failures but their
  district-days cannot be resolved.
- `unresolved_additional_events_true`: `yes` if an additional landslide is real
  but lacks a resolvable district or date; otherwise `no`.
- `annotator`: your name or initials.
- `notes`: optional short explanation for close calls.

Example:

```text
primary_district_date_true: Sindhupalchok|2020-06-15
additional_district_dates_true: Kalikot|2020-06-14; Dailekh|2020-06-15
unresolved_additional_events_true: no
```

A district is not an event location merely because it is a dateline, victim's
home, road destination, traffic origin, office address, hospital location, or
part of a named corridor. A publication, funeral, reopening, or rainfall date
is not an event date unless the article attributes it to that landslide.

Several landslides in one district on one date count as one district-day. The
same district on two dates counts as two district-days.

## Finish

Do not reorder rows or rename columns. Save the completed UTF-8 CSV as:

`data/outputs/secondary_locked_v8_COMPLETED.csv`

Only after all labels are frozen should the hidden predictions be opened and
scored.
