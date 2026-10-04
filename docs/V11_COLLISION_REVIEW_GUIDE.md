# v1.1 existing-event collision review

## File to complete

Open `data/outputs/v11_reconstruction_COLLISION_REVIEW.csv`.

The sheet contains all 41 reconstructed candidates. Nineteen candidates with no
screened match are already marked `new_event` by `collision_screen_v1`; do not
change those unless you find contrary evidence. Review the 22 rows whose
`final_action` is blank.

Use `candidate_matches_json` in the same row. It lists the possible existing
events with their IDs, dates, locations, titles, URLs, match tiers and reasons.
The expanded evidence is in
`data/outputs/v11_reconstruction_COLLISION_PAIRS.csv`.

## Columns to fill

Change only:

- `final_action`
- `merge_existing_event_id`
- `reviewed_by`
- `collision_review_notes`

For each blank row, choose one action:

- `new_event`: physically distinct from every listed existing event.
- `merge_existing`: the same physical event as a listed event; enter that exact
  ID in `merge_existing_event_id`.
- `exclude_duplicate`: duplicate evidence that should not be attached.
- `exclude_candidate`: not safe to add as an event.
- `unclear`: evidence cannot support a release-safe decision.

Use your name in `reviewed_by`. Leave `merge_existing_event_id` blank except for
`merge_existing`. Add a brief note for every merge, exclusion or unclear row.
Same date and district alone do not prove a duplicate; compare municipality,
place, title and physical incident details.

Save the completed sheet as:

`data/outputs/v11_reconstruction_COLLISION_DECISIONS_COMPLETED.csv`

Then validate it with:

```bash
PYTHONPATH=src .venv/bin/python scripts/validate_v11_collision_decisions.py
```
