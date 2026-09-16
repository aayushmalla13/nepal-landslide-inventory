# Canonical event true-value result

## Status

The 37-row true-value review is complete, validated, and materialized as an
unapplied release plan. No reviewed event overlaps an event removed or used as
a merge target by the identity plan.

## Decisions

- Reviewed rows: 37
- Retained with corrections: 26
- Excluded from the future corrected release: 11
- Unresolved values: 0
- Identity-plan overlap: 0

The 26 retained records contain 15 date changes, 12 district changes, 9 event
type changes, and 7 death-count changes. Some records contain multiple changes.
District changes also carry the corresponding derived province in the plan.

Three source-uncertain casualty values are represented as `not_reported`, not
as review-level `unclear`. This records that the source did not establish a
death count while keeping the manual gate fully resolved.

## Inventory effect

The identity plan produced a provisional 2,915 events. Removing the 11
true-value exclusions produces 2,904 provisional events, a net increase of 19
from the frozen 2,885-event inventory.

## Provenance outputs

- `data/outputs/canonical_event_true_value_plan_CORRECTIONS.csv`
- `data/outputs/canonical_event_true_value_plan_EXCLUSIONS.csv`
- `data/outputs/canonical_event_true_value_plan_manifest.json`
- `data/outputs/canonical_event_true_value_plan_report.md`

The frozen release remains unchanged. These outputs must be combined with the
identity plan and the pending structured-attribute plan only when a new
versioned release is assembled.
