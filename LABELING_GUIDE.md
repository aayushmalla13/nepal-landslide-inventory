# Manual Verification Labeling Guide

Use this guide while filling:
- `/Users/aayush/Documents/nepal_landslide_inventory/data/outputs/manual_verification_sample.csv`

Fill only the truth columns:
- `class_true`
- `district_true`
- `municipality_true`
- `date_true`
- `deaths_true`
- `trigger_true`
- `notes`

## Core principle

Label from the article itself, not from the predicted fields.
If something is uncertain, leave the field blank rather than guessing.

## Class labels

### `class_true = 1`
Use when all of these are true:
- it is a real landslide event
- the event occurred in Nepal
- the district is identifiable
- the event date is usable enough for a final event row

Examples:
- single-event landslide report
- specific fatal landslide in a named district
- clearly dated event article with a resolvable Nepal location

### `class_true = 2`
Use when it is landslide-related and in Nepal, but not strong enough for a clean final event row.

Typical cases:
- real event but district unclear
- real event but date unclear
- follow-up / rescue / recovery article tied to a real event
- article mentions a landslide incident but lacks enough structure for final inventory use

### `class_true = 3`
Use when it should not become a final event row.

Typical cases:
- nationwide / province-wide / district-wide roundup
- cumulative monsoon total
- warning / alert / forecast / high-risk article
- risk-only or damage-only article without a concrete event
- out-of-country event
- irrelevant or metaphorical usage

## District labeling

For `district_true`:
- use the canonical English district name
- fill it only when clearly supported by the article
- if a municipality is clearly stated and you are certain of the district, you may fill the district
- otherwise leave blank

Examples:
- `Sindhupalchok`
- `Rasuwa`
- `Myagdi`

Do not:
- use non-canonical abbreviations
- guess from weak place mentions

## Municipality labeling

For `municipality_true`:
- use the canonical English municipality name
- fill only when clearly stated in the article
- leave blank if only ward, village, tole, or vague locality is mentioned

Examples:
- `Melamchi Municipality`
- `Silichong Rural Municipality`

## Date labeling

For `date_true`:
- use `YYYY-MM-DD`
- prefer the actual event date
- if the article clearly reports a same-day event and no separate event date is given, publication date can be used
- leave blank if the date is vague or unclear

Good:
- explicit date in article body or title
- phrases that clearly anchor the event date and can be resolved safely

Leave blank for:
- `recently`
- `in the monsoon`
- `so far`
- retrospective or historical references without a single event date

## Deaths labeling

For `deaths_true`:
- enter the event-specific death count as an integer
- leave blank if unclear
- do not use cumulative regional/national totals unless the article is truly about one event and that count belongs to it

Good:
- `3`
- `11`

Do not use:
- multi-event seasonal totals
- nationwide disaster summaries

## Trigger labeling

Use one of:
- `rainfall`
- `earthquake`
- `anthropogenic`
- `unknown`

Use:
- `rainfall` for monsoon, heavy rain, cloudburst, flood-triggered landslide context
- `earthquake` when quake/tremor clearly triggered the landslide
- `anthropogenic` for road cutting, excavation, construction, dozer activity, slope cutting
- `unknown` when the article does not support a trigger confidently

## Notes

Use `notes` for anything ambiguous or important.

Examples:
- `roundup, not single event`
- `follow-up article`
- `district not stated`
- `event in India, Nepali victims`
- `date unclear`
- `cumulative deaths, not event-specific`

## Recommended workflow

For each row:
1. Open the article URL.
2. Read the title and first few paragraphs.
3. Decide `class_true` first.
4. Fill `district_true`.
5. Fill `municipality_true` if clearly present.
6. Fill `date_true`.
7. Fill `deaths_true`.
8. Fill `trigger_true`.
9. Add a short `notes` comment if needed.

## Quick examples

### Example A: clean event
Article says: landslide killed 3 in Rasuwa on 2024-07-14.
- `class_true = 1`
- `district_true = Rasuwa`
- `date_true = 2024-07-14`
- `deaths_true = 3`
- `trigger_true = rainfall`

### Example B: roundup
Article says: monsoon disasters have killed 244 across Nepal so far.
- `class_true = 3`
- `notes = roundup, nationwide cumulative total`

### Example C: risk warning
Article says: five villages are at high risk of landslides.
- `class_true = 3`
- `notes = risk warning, not concrete event`

### Example D: real but incomplete
Article says: search continues after landslide in Myagdi, date unclear.
- `class_true = 2`
- `district_true = Myagdi`
- `notes = real event but date unclear`

## After labeling

Run:

```bash
cd /Users/aayush/Documents/nepal_landslide_inventory
make run STAGE=manual_score
```

Outputs:
- `/Users/aayush/Documents/nepal_landslide_inventory/data/outputs/manual_metrics.json`
- `/Users/aayush/Documents/nepal_landslide_inventory/data/outputs/manual_report.md`
