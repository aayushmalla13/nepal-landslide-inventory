# Canonical event structured-attribute result

## Status

The final 27-row structured-attribute review is complete, validated, and
materialized as an unapplied release plan. This completes every manual
correction gate derived from the frozen 150-event audit.

## Decisions

- Reviewed rows: 27
- Retained with corrections: 27
- Excluded: 0
- Unresolved values: 0
- Overlap with identity or true-value plans: 0

The plan contains 15 event-type changes, 7 hazard-type changes, and 10
death-count changes. Some records contain more than one correction.

## Consolidated inventory effect

The identity plan removes 55 superseded records and adds 85 reconstructed
events. The true-value plan then excludes 11 records. The structured-attribute
plan changes values without changing row count. The resulting provisional
inventory therefore contains 2,904 events, a net increase of 19 from the
frozen 2,885-event release.

## Provenance outputs

- `data/outputs/canonical_event_structured_attribute_plan_CORRECTIONS.csv`
- `data/outputs/canonical_event_structured_attribute_plan_EXCLUSIONS.csv`
- `data/outputs/canonical_event_structured_attribute_plan_manifest.json`
- `data/outputs/canonical_event_structured_attribute_plan_report.md`

The frozen release remains unchanged. Pipeline fixes and regression tests are
the next gate before these plans are assembled into a new versioned release.
