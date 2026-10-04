# v1.3 Final Candidate Collision Review

Open `data/outputs/v13_reconstruction_FINAL_COLLISION_REVIEW.csv`.

Two low-risk rows are already filled as `new_event`. Review only the six rows
whose `final_candidate_action` is blank. These rows compare reconstructed
candidates with one another, not with the frozen inventory.

Read `candidate_matches_json` and, when needed,
`data/outputs/v13_reconstruction_FINAL_COLLISION_PAIRS.csv`.

Fill only:

- `final_candidate_action`
- `merge_candidate_event_id`
- `reviewed_by_final`
- `final_collision_notes`

Allowed actions are:

- `new_event`: this candidate is a distinct physical event.
- `merge_candidate`: it is the same event as a listed candidate; copy that
  candidate's ID into `merge_candidate_event_id`.
- `exclude_candidate`: it should not become an event.
- `unclear`: identity cannot be resolved from the evidence.

Use `merge_candidate_event_id` only for `merge_candidate`. Set
`reviewed_by_final` to `aayush` and add a brief evidence-based note. Do not
change IDs, evidence, row order, or the two pre-filled rows.

Save as:

`data/outputs/v13_reconstruction_FINAL_COLLISION_DECISIONS_COMPLETED.csv`
