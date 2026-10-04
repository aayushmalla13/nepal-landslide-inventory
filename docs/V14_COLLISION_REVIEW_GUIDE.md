# v1.4 Existing-Event Collision Review

Open `data/outputs/v14_reconstruction_COLLISION_REVIEW.csv`.

Rows with `top_collision_tier=none` are prefilled as `new_event`. Review only
rows with blank `final_action`, using `candidate_matches_json` and
`data/outputs/v14_reconstruction_COLLISION_PAIRS.csv`.

Fill only `final_action`, `merge_existing_event_id`, `reviewed_by`, and
`collision_review_notes`.

- `new_event`: distinct from every listed existing event.
- `merge_existing`: same physical event; copy a listed `existing_event_id`.
- `exclude_duplicate`: duplicate that should not create another event.
- `exclude_candidate`: not a usable landslide event.
- `unclear`: identity cannot be resolved.

Use a merge ID only with `merge_existing`. Set `reviewed_by` to `aayush`, add a
brief evidence-based note, and do not edit frozen fields or prefilled rows.
Save as:

`data/outputs/v14_reconstruction_COLLISION_DECISIONS_COMPLETED.csv`
