# v0.9 candidate assembly result

## Outcome

All validated v0.9 identity, true-value, structured-attribute, and release-
preflight plans have been applied to a new versioned candidate:

- Release: `nepal_landslide_inventory_v0.9.0_candidate_20260924`
- Source candidate: `nepal_landslide_inventory_v0.8.0_candidate_20260923`
- Canonical events: 2,858
- Unique event IDs: 2,858
- Date extent: 2015-03-07 through 2026-08-09
- Represented districts: 76
- Canonical CSV SHA-256:
  `9331668017b1ea34709acfbda34ec9a52c4ab5a02bcdc127cab0a58769379f22`
- Bundle lock:
  `9d08afe7cfb8be5164a2595e7b17cdcca371cb6b29c6b3791bd7550e13cfaf8f`

The candidate remains `pending_fresh_validation`. Metrics from v0.8 or any
earlier release do not validate it.

## Applied actions

The 126-row application log reconciles exactly to the frozen plans:

- 31 superseded events removed
- 3 reconstruction candidates excluded
- 10 candidates merged into existing events
- 25 reconstructed events added
- 8 existing events excluded at the true-value gate
- 24 true-value corrections applied
- 25 structured-attribute corrections applied

The net change from the 2,872-row v0.8 source is -14 events. Five reconstructed
locations required documented canonicalization.

One otherwise valid Dahikhola event was excluded at release preflight. The
source places it between Dullu Municipality in Dailekh and Shubhakalika Rural
Municipality in Kalikot, so the single canonical district required by the
release schema cannot be established without overclaiming. The original human
decision and the release exclusion are both preserved and checksummed.

## Verification

The canonical CSV and SQLite snapshot contain the same ordered records. SQLite
reports 2,858 rows, 2,858 distinct IDs, and `PRAGMA integrity_check = ok`.
Every release listed by `scripts/verify_releases.py` passes checksum and bundle-
lock verification. The full test suite passes with two intentional skips.

Artifacts are in
`data/releases/nepal_landslide_inventory_v0.9.0_candidate_20260924/`.

## Next gate

A new 150-row locked probability sample has been drawn from this exact
candidate. Its 1,898-row eligible frame excludes 483 previously reviewed event
IDs and 1,645 reviewed article URLs. The sample has zero event-ID or
representative-URL overlap with the v0.8 fresh audit, and no sampled article is
missing from the local evidence corpus.

Complete `data/outputs/v09_final_validation_LABEL_HERE.csv` using
`docs/V09_FINAL_VALIDATION_GUIDE.md`, then run the prespecified scorer. Do not
promote v0.9 or rerun final rainfall and external-validation releases until
every frozen decision check passes.
