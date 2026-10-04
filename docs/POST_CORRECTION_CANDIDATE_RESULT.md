# Post-correction candidate assembly result

## Outcome

The validated post-correction identity, true-value, and structured-attribute
plans have been applied to a new versioned candidate:

- Release: `nepal_landslide_inventory_v0.8.0_candidate_20260923`
- Source candidate: `nepal_landslide_inventory_v0.7.0_candidate_20260916`
- Canonical events: 2,872
- Unique event IDs: 2,872
- Date extent: 2015-03-07 through 2026-08-09
- Represented districts: 76
- Canonical CSV SHA-256:
  `0822515b56693af22daf2e3cc6e63b178eb41fefa46a8b607a47d6da9efdcd07`
- Bundle lock:
  `49a65f598a99d45d7c7cca25aec72fa6043fd75b2fb38646fbcb8f686443a757`

The candidate remains `pending_fresh_validation`. It is not promoted, and
accuracy estimates from v0.7 or earlier releases do not validate it.

## Applied actions

The application log contains 212 actions and reconciles exactly to the frozen
manual plans:

- 61 superseded events removed
- 29 reconstruction candidates excluded
- 11 candidates merged into existing events
- 42 reconstructed events added
- 13 existing events excluded at the true-value gate
- 31 true-value corrections applied
- 25 structured-attribute corrections applied

The net change from the 2,904-row source candidate is -32 events. Thirty-nine
reconstructed locations required a documented district alias, municipality
normalization, blanking of an unsupported municipality, or a source-supported
location override.

## Reconciliation

The canonical CSV and SQLite snapshot contain the same ordered records. SQLite
reports 2,872 rows, 2,872 distinct IDs, and `PRAGMA integrity_check = ok`.
Every removed or excluded event is absent, every reconstructed event is
present, every merge contains its planned article URLs, and every corrected
field matches its approved plan. The repository release verifier accepts the
candidate bundle and its checksums.

Reproducible artifacts are in
`data/releases/nepal_landslide_inventory_v0.8.0_candidate_20260923/`. The
assembler is `scripts/assemble_post_correction_candidate_release.py`.

## Next gate

Rainfall linkage and external validation have been rerun against this exact
candidate. A new 150-row independent sample is now locked in
`data/outputs/v08_fresh_validation_manifest.json`; it excludes all traceable
previously reviewed events and article evidence. Complete the blind labels and
run `scripts/score_v08_fresh_validation.py`. Do not promote v0.8 before every
prespecified decision check passes.
