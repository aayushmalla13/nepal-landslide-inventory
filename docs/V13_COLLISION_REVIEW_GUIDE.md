# v1.3 Existing-Event Collision Review

Open `data/outputs/v13_reconstruction_COLLISION_REVIEW.csv`.

Five rows with `top_collision_tier=none` are already locked as `new_event` by
the collision screen. Review only the nine rows whose `final_action` is blank.
Use `candidate_matches_json` for the possible existing events and consult
`data/outputs/v13_reconstruction_COLLISION_PAIRS.csv` when the compact evidence
is insufficient.

Fill only:

- `final_action`
- `merge_existing_event_id`
- `reviewed_by`
- `collision_review_notes`

Allowed `final_action` values:

- `new_event`: the reconstructed candidate is distinct from every match.
- `merge_existing`: it is the same physical event as one listed match; copy
  that match's `existing_event_id` into `merge_existing_event_id`.
- `exclude_duplicate`: the candidate duplicates an existing event and should
  not create another event.
- `exclude_candidate`: the reconstructed candidate is not a usable landslide
  event.
- `unclear`: evidence is insufficient; leave `merge_existing_event_id` blank.

Use `merge_existing_event_id` only with `merge_existing`. Set `reviewed_by` to
`aayush` and briefly record the decisive evidence in
`collision_review_notes`.

Do not edit candidate evidence, match evidence, IDs, row order, or the five
pre-filled rows. Save the completed file as:

`data/outputs/v13_reconstruction_COLLISION_DECISIONS_COMPLETED.csv`
