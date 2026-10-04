# v1.1 final candidate-collision review

## File to complete

Open `data/outputs/v11_reconstruction_FINAL_COLLISION_REVIEW.csv`.

This is the final identity gate for the 24 eligible proposed new events. Seven
rows with no or only low-tier matches are already marked `new_event`. Review the
17 rows whose `final_candidate_action` is blank.

The possible counterpart IDs are in `candidate_matches_json`. Full pair details
are in `data/outputs/v11_reconstruction_FINAL_COLLISION_PAIRS.csv`.

## Columns to fill

Change only:

- `final_candidate_action`
- `merge_candidate_event_id`
- `reviewed_by_final`
- `final_collision_notes`

Choose one action for each blank row:

- `new_event`: retain as a distinct physical event.
- `merge_candidate`: merge into one listed candidate; enter its exact ID.
- `exclude_duplicate`: exclude as a duplicate of one listed retained candidate;
  enter that exact ID.
- `unclear`: identity cannot be resolved safely.

Merge and exclusion targets must appear in `candidate_matches_json`, must
themselves be retained as `new_event`, and require a short note. URL overlap is
expected when one article was decomposed into multiple named failures; it does
not by itself mean those failures are duplicates.

Save as:

`data/outputs/v11_reconstruction_FINAL_COLLISION_DECISIONS_COMPLETED.csv`

Then validate with:

```bash
PYTHONPATH=src .venv/bin/python scripts/validate_v11_final_collisions.py
```
