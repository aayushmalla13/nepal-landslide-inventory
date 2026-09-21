# Post-correction reconstruction date review

## Purpose

Thirty of the 93 reconstructed physical-event candidates do not yet have a
defensible exact date. They cannot enter collision screening, rainfall linkage,
or a rebuilt inventory until they receive a supported date or are excluded.

No candidate or production event has been changed.

## File

Open:

`data/outputs/post_correction_reconstruction_DATE_REVIEW.csv`

Each row contains the proposed event identity, audit evidence, article mapping,
publication metadata, and full source text.

## Fill only these columns

- `final_action`: `set_date` or `exclude_candidate`
- `resolved_event_date`: exact `YYYY-MM-DD` date when action is `set_date`;
  otherwise blank
- `reviewed_by`: one stable reviewer identifier
- `review_notes`: short evidence-based explanation

Do not modify frozen columns or row order.

## Rules

1. Use `set_date` only when the text supports one exact calendar date for that
   physical failure.
2. Resolve relative expressions such as “Tuesday,” “last night,” or “three days
   ago” against the article's publication date and wording.
3. Do not automatically use the publication date. Retrospective and roundup
   articles often describe earlier failures.
4. Use `exclude_candidate` when no exact date can be supported. Do not invent a
   date to retain a record.
5. The allowed inventory period is 2015-01-01 through 2026-08-09.

Save as:

`data/outputs/post_correction_reconstruction_DATE_REVIEW_COMPLETED.csv`

Then run:

```bash
PYTHONPATH=src .venv/bin/python scripts/resolve_post_correction_reconstruction_dates.py
```

The validator rejects altered frozen fields, blank reviewer provenance,
unsupported actions, malformed dates, dates outside the inventory period, and
dates supplied for excluded candidates.
