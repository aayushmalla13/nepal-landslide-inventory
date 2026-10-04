# v1.4 Final Candidate Collision Review

Open `data/outputs/v14_reconstruction_FINAL_COLLISION_REVIEW.csv`.

Rows with no medium/high candidate collision are prefilled as `new_event`.
Review only rows with blank `final_candidate_action`, using
`candidate_matches_json` and
`data/outputs/v14_reconstruction_FINAL_COLLISION_PAIRS.csv`.

Fill only `final_candidate_action`, `merge_candidate_event_id`,
`reviewed_by_final`, and `final_collision_notes`.

- `new_event`: distinct physical event.
- `merge_candidate`: same event as a listed candidate; copy its candidate ID.
- `exclude_candidate`: not a usable event.
- `unclear`: identity remains unresolved.

Set `reviewed_by_final` to `aayush`, explain the evidence briefly, and do not
change frozen or prefilled cells. Save as:

`data/outputs/v14_reconstruction_FINAL_COLLISION_DECISIONS_COMPLETED.csv`
