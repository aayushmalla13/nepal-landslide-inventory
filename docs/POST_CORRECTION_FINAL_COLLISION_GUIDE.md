# Final post-correction candidate collision review

## Purpose

The existing-event review produced 42 eligible proposed new events and 11 safe
merges. Eleven candidates tied to three old aggregate events are blocked as
whole bundles because at least one identity decision in each bundle remains
unclear.

This final gate checks the 42 proposed new events against one another before an
identity plan can be assembled. No identity decision has been applied.

## Open these files together

1. `data/outputs/post_correction_reconstruction_FINAL_COLLISION_DECISIONS.csv`
2. `data/outputs/post_correction_reconstruction_FINAL_COLLISION_PAIRS.csv`

## Fill only these columns

- `final_candidate_action`
- `merge_candidate_event_id`
- `reviewed_by_final`
- `final_collision_notes`

Allowed actions are:

- `new_event`: retain this candidate as a distinct physical event
- `merge_candidate`: merge it into another listed candidate
- `exclude_duplicate`: exclude it as a duplicate of another listed candidate
- `unclear`: identity remains unresolved

For `merge_candidate` or `exclude_duplicate`, supply a listed target candidate
in `merge_candidate_event_id`. The target row itself must be marked
`new_event`; merge chains and cycles are invalid. Leave the target blank for
`new_event` and `unclear`.

## Important evidence rule

Shared source URLs are expected when one article was decomposed into multiple
physical events. URL overlap is therefore only a review signal here, not proof
of duplication. Compare the event evidence, place, date, municipality, and
whether the text actually distinguishes the failures.

Save as:

`data/outputs/post_correction_reconstruction_FINAL_COLLISION_DECISIONS_COMPLETED.csv`

Then run:

```bash
PYTHONPATH=src .venv/bin/python scripts/validate_post_correction_final_collisions.py
```

Any `unclear` result blocks the affected identity bundle from application.
