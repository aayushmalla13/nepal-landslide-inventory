# Post-correction existing-event collision review

## Purpose

The 64 dated reconstruction candidates must be checked against unaffected v0.7
events before any insertion or merge. This gate prevents reconstructed events
from duplicating records already represented elsewhere in the inventory.

No candidate or production event has been changed.

## Open these files together

1. `data/outputs/post_correction_reconstruction_COLLISION_DECISIONS.csv`
2. `data/outputs/post_correction_reconstruction_COLLISION_PAIRS.csv`

The decision sheet includes each reconstructed candidate and up to ten compact
possible matches. The pair file contains the full scored candidate-existing
comparisons.

## Fill only these columns

- `final_action`
- `merge_existing_event_id`
- `reviewed_by`
- `collision_review_notes`

Allowed actions are:

- `new_event`: no existing event represents this physical failure
- `merge_existing`: the candidate is the same event as one listed existing ID
- `exclude_duplicate`: the candidate duplicates an existing event but should
  not contribute new data
- `exclude_candidate`: evidence is insufficient or the candidate is invalid
- `unclear`: the evidence does not support a defensible decision

For `merge_existing`, copy one `existing_event_id` from that candidate's listed
matches into `merge_existing_event_id`. Leave the merge field blank for every
other action.

## Review rules

1. Source-URL overlap is strong evidence but still verify that the article does
   not report multiple failures.
2. Exact date and municipality are stronger than district alone.
3. A low-tier match is a lead, not proof of duplication.
4. Similar titles can describe different failures during the same rainfall
   episode; use the evidence and locations.
5. Use `unclear` rather than forcing a merge or new event when identity cannot
   be established.

Save as:

`data/outputs/post_correction_reconstruction_COLLISION_DECISIONS_COMPLETED.csv`

Then run:

```bash
PYTHONPATH=src .venv/bin/python scripts/validate_post_correction_collision_decisions.py
```

Candidate-to-candidate collision review remains a separate final identity gate
after these decisions are validated.
