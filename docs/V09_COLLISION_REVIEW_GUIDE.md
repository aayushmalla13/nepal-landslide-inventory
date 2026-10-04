# v0.9 existing-event collision review guide

## Purpose

This gate determines whether each of the 49 reconstructed physical-event
candidates is new, duplicates an unaffected v0.8 event, should be excluded, or
remains unclear. No decision has been applied to the inventory.

## Files

Use these together:

- `data/outputs/v09_reconstruction_COLLISION_DECISIONS.csv`
- `data/outputs/v09_reconstruction_COLLISION_PAIRS.csv`

The decision sheet embeds up to ten candidate matches in
`candidate_matches_json`. The pair file contains all 142 screened pairs.

Do not change frozen columns or row order. Fill only:

- `final_action`
- `merge_existing_event_id`
- `reviewed_by`
- `collision_review_notes`

## Actions

- `new_event`: the reconstructed candidate is physically distinct from every
  listed existing event.
- `merge_existing`: the candidate is the same physical event as one listed
  existing event. Put that exact ID in `merge_existing_event_id`.
- `exclude_duplicate`: the candidate duplicates another record but should not
  contribute new article evidence to an existing event.
- `exclude_candidate`: the reconstructed candidate itself is not safe to add.
- `unclear`: the evidence cannot support a release-safe decision.

Leave `merge_existing_event_id` blank unless the action is `merge_existing`.
Explain every merge, exclusion, and unclear decision. For `high` and `medium`
rows, compare location details and source evidence rather than relying on the
numeric score alone. A same date and district can still contain separate
physical landslides.

Save the completed file as
`data/outputs/v09_reconstruction_COLLISION_DECISIONS_COMPLETED.csv`, then run:

```bash
PYTHONPATH=src .venv/bin/python scripts/validate_v09_collision_decisions.py
```
