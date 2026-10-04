# v1.0 final locked validation result

Date: 2026-09-27

## Decision

**Retain candidate status.** The 150-row locked probability sample passed
structural validation and scoring, but three prespecified promotion checks
failed. The decision rule was frozen before labels existed and has not been
changed.

Candidate: `nepal_landslide_inventory_v1.0.0_candidate_20260927`

## Weighted results

| Metric | Estimate | 95% CI | Decision relevance |
|---|---:|---:|---|
| Event-existence precision | 0.945 | 0.903-0.979 | pass |
| Usable-record precision | 0.510 | 0.421-0.592 | fail |
| Single-event accuracy | 0.821 | 0.760-0.878 | fail |
| District accuracy | 0.873 | 0.816-0.925 | pass |
| Date accuracy | 0.789 | 0.714-0.858 | fail |
| Municipality accuracy | 0.892 | 0.821-0.952 | descriptive |
| Event-type accuracy | 0.509 | 0.431-0.587 | descriptive |
| Hazard-type accuracy | 0.978 | 0.949-1.000 | descriptive |
| Deaths exact accuracy | 0.859 | 0.800-0.913 | descriptive |
| Duplicate-merge accuracy | 0.900 | 0.762-1.000 | descriptive |

The event-existence unclear fraction was 0.020 and passed its maximum 0.05
threshold.

## Sample findings

- 139 events were confirmed, eight rejected, and three unclear.
- 25 confirmed events represented more than one physical failure; three were
  unclear on granularity.
- 17 decisive district claims and 26 decisive date claims were wrong.
- Fifteen additional dates and two districts were unclear.
- Nine claimed municipalities were wrong.
- Two reviewed multi-article clusters were incorrectly merged and three were
  unclear.

The project can now support a high event-existence precision claim for the
eligible never-reviewed frame, but not a high-precision usable-record claim.
It is therefore not yet ready to be presented as a validated high-precision
event inventory.

## Typing-stage repair

The frozen v1.0 export had been produced after dedup but before the downstream
`event_typing` stage. Consequently, null typing fields were exported through a
fallback as `landslide`, causing 66 genuine road-obstruction rows in the audit
to be claimed as landslides.

This does not change or rescore v1.0. The mutable pipeline was repaired by:

1. adding an export gate that rejects any canonical row without completed
   event typing;
2. rerunning `event_typing` and `export_final`; and
3. adding regression coverage for the gate.

Against the same locked labels, the corrected mutable typing agrees on 124 of
139 decisive rows (0.892 unweighted), compared with 0.509 weighted accuracy in
the frozen candidate. This is a development diagnostic only; it is not a new
promotion metric.

Post-repair working artifacts:

- SQLite snapshot:
  `data/snapshots/landslide_inventory_post_v10_typing_repair_20260927.sqlite`
  (`5403a3a20ad297e9b564f0315080b722b9d5c199d9b298f95ca293e9934cfc4d`)
- Mutable final CSV:
  `data/outputs/canonical_events_final.csv`
  (`2cffaaf35f5bea3858fba95a131d8e80522b35c0bfa2e38cfb50c27fa5713534`)

## Next gate

The immutable v1.1 remediation queue contains 123 rows and partitions them
into 36 article-mapping, 49 true-value, and 38 structured-attribute cases.
Identity and multi-event decisions must be completed before date/location and
structured-attribute changes are applied.

See:

- `data/outputs/v10_final_validation_score.json`
- `data/outputs/v10_final_validation_report.md`
- `data/outputs/v11_remediation_queue.csv`
- `data/outputs/v11_remediation_report.md`
- `data/outputs/v11_remediation_manifest.json`
