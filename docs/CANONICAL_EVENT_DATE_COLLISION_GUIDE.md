# Reconstruction date and collision review guide

## Current gate

The 100 reconstructed candidates have been compared with the 2,830 unaffected
events in frozen inventory v0.6.0. Nine candidates cannot complete collision
screening because their event date is unclear.

Resolve those nine dates before reviewing collision decisions. The preliminary
collision output will be regenerated afterward.

## Date review

Open:

`data/outputs/canonical_event_reconstruction_DATE_REVIEW.csv`

For each row, read `event_evidence` and enough of `source_evidence` to choose one
of two actions:

- `set_date`: the evidence supports a specific event date.
- `exclude_candidate`: no defensible event date can be established for this
  event candidate.

Fill:

- `final_action`
- `resolved_event_date` as `YYYY-MM-DD` when the action is `set_date`; leave it
  blank for exclusion
- `reviewed_by`
- `review_notes`

Do not use publication date automatically. Relative phrases such as “last
month,” “Wednesday,” or “during the previous monsoon” must be resolved from the
article's publication date and wording, or the candidate must be excluded.

Save as:

`data/outputs/canonical_event_reconstruction_DATE_REVIEW_COMPLETED.csv`

Do not edit or complete the collision decision sheet yet. It currently contains
preliminary matches for only the 91 already-dated candidates and must be rebuilt
after this date review.

## Preliminary collision context

The first pass generated 199 possible pairs: 3 high tier, 36 medium tier, and
160 low tier. No pair shares a source URL. These are candidate matches, not
automatic duplicates.
