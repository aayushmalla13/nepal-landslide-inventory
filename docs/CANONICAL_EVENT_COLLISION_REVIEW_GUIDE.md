# Final reconstruction collision review

## Files

Open:

1. `data/outputs/canonical_event_reconstruction_FINAL_COLLISION_DECISIONS.csv`
2. `data/outputs/canonical_event_reconstruction_FINAL_COLLISION_PAIRS.csv`

The decision sheet contains 99 reconstructed candidates. The pair table contains
all 210 possible frozen-event matches. No source URL is shared between a
candidate and an unaffected frozen event.

## Review order

Filter `proposed_collision_action` in this order:

1. `review_possible_collision`: 36 rows with a medium/high candidate.
2. `likely_new_event_low_tier_matches`: 48 rows with only broad low-tier matches.
3. `new_event_no_candidate_collision`: 15 rows with no match inside the gate.

## Fields to fill

- `final_collision_action`: `new_event`, `merge_existing`,
  `exclude_duplicate`, `exclude_candidate`, or `unclear`.
- `merge_target_event_id`: required only for `merge_existing` or
  `exclude_duplicate`; copy an `existing_event_id` from the pair table.
- `reviewed_by_collision`: stable reviewer ID.
- `collision_review_notes`: required for merges and exclusions and recommended
  for close calls.

Use `merge_existing` when the reconstructed evidence adds information to an
already represented physical event. Use `exclude_duplicate` when the candidate
adds no useful event record beyond the existing event. Use `new_event` only when
the evidence supports a distinct physical failure.

Date proximity and district equality alone are not proof of duplication.
Compare municipality, place wording, road location, casualty details, and the
linked article evidence. Conversely, different article URLs do not prove the
events are distinct.

Save as:

`data/outputs/canonical_event_reconstruction_FINAL_COLLISION_DECISIONS_COMPLETED.csv`

Rows marked `unclear` will keep the release gate blocked.
