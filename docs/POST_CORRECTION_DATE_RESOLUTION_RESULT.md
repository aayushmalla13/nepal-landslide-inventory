# Post-correction reconstruction date-resolution result

**Status:** validated, materialized, and unapplied

## Decisions

The 30-row exact-date review is complete and valid. Reviewer
`reviewer_postcorr_A` made the following decisions:

- Exact date resolved: 1
- Candidate excluded because no exact date was supportable: 29

The resolved candidate is dated 2025-08-08. Its article was published Saturday,
2025-08-09 and states that the road had been blocked since Friday evening.

This conservative gate prevents undated physical failures from entering a
date-dependent inventory or rainfall analysis.

## Resulting identity frame

- Reconstruction candidates before date review: 93
- Dated candidates retained for collision screening: 64
- Date-unresolved candidates excluded: 29
- Original mapping decisions still unresolved and retained unchanged: 3

No candidate or production event has been changed.

## Existing-event collision screen

The 64 retained candidates were compared with 2,840 unaffected v0.7 events
after removing the 64 superseded old events from the comparison frame.

- Candidate-existing pairs: 191
- Candidates with medium-tier matches: 29
- Candidates with low-tier matches: 15
- Candidates with no matches: 20
- Candidates with high-tier source-URL overlap: 0

Medium and low tiers are review leads, not automatic merges. Exact date and
district can occur across distinct failures during the same rainfall episode.

## Next gate

The 64-row existing-event collision review is complete. Bundle-safe
materialization leaves 42 eligible new candidates for the final
candidate-to-candidate review. See
`docs/POST_CORRECTION_EXISTING_COLLISION_RESULT.md`.

## Reproducibility

- Completed date review:
  `data/outputs/post_correction_reconstruction_DATE_REVIEW_COMPLETED.csv`
- Date-resolved groups:
  `data/outputs/post_correction_reconstruction_GROUPS_DATE_RESOLVED.csv`
- Date exclusions:
  `data/outputs/post_correction_reconstruction_DATE_EXCLUDED.csv`
- Date-resolution manifest:
  `data/outputs/post_correction_date_resolution_manifest.json`
- Collision decisions:
  `data/outputs/post_correction_reconstruction_COLLISION_DECISIONS.csv`
- Collision pairs:
  `data/outputs/post_correction_reconstruction_COLLISION_PAIRS.csv`
- Collision manifest: `data/outputs/post_correction_collision_manifest.json`
