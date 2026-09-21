# Post-correction identity plan result

## Outcome

The final candidate-to-candidate collision review is complete and valid. All 42
eligible candidates were retained as distinct physical events. No candidate
merge, duplicate exclusion, or unresolved final decision remains.

The bundle-safe identity plan contains:

- 61 superseded old events planned for removal
- 42 planned new physical events
- 11 candidates planned for merge into existing events
- 29 candidates excluded because their dates could not be resolved
- 11 candidates blocked across three existing-collision bundles
- six reviewed old events retained unchanged: three mapping-unclear events and
  three existing-collision-blocked bundles
- 35 excluded article memberships preserved as provenance

Starting from the 2,904-row v0.7 candidate, the identity layer would contain
2,885 events, a net change of -19. Merges and exclusions do not add inventory
rows.

## Safety status

This plan is not applied. No canonical CSV, database, release directory, or
rainfall linkage was modified. The blocked bundles remain intact rather than
being partially reconstructed.

## Remaining gates

Recurring audit failures must first be converted into parser, specificity,
scope, and deduplication fixes with regression tests. The 45-row true-value and
25-row structured-attribute gates must then be completed before assembling and
independently validating a new checksummed candidate.
