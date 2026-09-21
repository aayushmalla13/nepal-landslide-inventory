# Post-correction existing-event collision result

**Status:** validated, materialized, and unapplied

## Decisions

The 64-row candidate-versus-existing review is complete and valid. Reviewer
`reviewer_postcorr_A` made the following decisions:

- New event: 43
- Merge into a listed existing event: 12
- Unclear: 9

All 12 merge targets were present in the corresponding locked collision-pair
evidence. No frozen candidate or match field was changed.

## Bundle-safe materialization

The nine unclear candidates belong to three old aggregate events. One of those
old events also contains a proposed new event and a proposed merge. Applying
only those clear pieces while retaining the unresolved original would create
partial duplicate identities.

The materializer therefore blocks each affected old event as a whole:

- Eligible proposed new events: 42
- Safe merges into existing events: 11
- Blocked reconstruction candidates: 11
- Blocked old-event bundles retained unchanged: 3
- Old events safe to supersede: 61

No action has been applied to v0.7 or the production database.

## Final candidate collision screen

The 42 eligible proposed new events were compared with one another. The screen
produced 34 pairs, all within candidates reconstructed from the same old
aggregate source.

- Candidates with high-tier pairs: 9
- Candidates with medium-tier pairs: 15
- Candidates with low-tier pairs: 10
- Candidates with no pair: 8

Shared article URLs are expected after decomposing a multi-event article and
are not proof of duplication. Final review must compare the event evidence,
place, date, and whether the source distinguishes separate physical failures.

## Next gate

Complete and validate the 42-row final candidate-to-candidate collision sheet.
Merge and duplicate-exclusion targets must be listed pairs and must themselves
be retained as `new_event`. Any unclear decision keeps its identity bundle
unapplied.

## Reproducibility

- Completed existing-event decisions:
  `data/outputs/post_correction_reconstruction_COLLISION_DECISIONS_COMPLETED.csv`
- Existing-event validation:
  `data/outputs/post_correction_collision_validation.json`
- Eligible new candidates:
  `data/outputs/post_correction_existing_collision_NEW_CANDIDATES.csv`
- Safe existing-event merges:
  `data/outputs/post_correction_existing_collision_MERGES.csv`
- Blocked candidates:
  `data/outputs/post_correction_existing_collision_BLOCKED_CANDIDATES.csv`
- Outcome manifest:
  `data/outputs/post_correction_existing_collision_outcomes_manifest.json`
- Final decisions:
  `data/outputs/post_correction_reconstruction_FINAL_COLLISION_DECISIONS.csv`
- Final pairs:
  `data/outputs/post_correction_reconstruction_FINAL_COLLISION_PAIRS.csv`
