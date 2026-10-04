# v1.4 Candidate Result

The validated v1.4 identity, true-value, structured-attribute, and exact-date
preflight plans have been assembled into a locked candidate release.

- Source candidate: v1.3, 2,146 events
- v1.4 candidate: 2,138 unique events
- Identity: 20 old events superseded, 16 release-ready reconstructed events,
  3 merges into existing events, and 6 exact-date preflight exclusions
- True value: 30 corrections, 4 exclusions, and 1 confirmed no-change
- Structured attributes: 18 corrections and no exclusions
- Application log: 97 actions

The release has canonical districts, unique event IDs, exact ISO dates, SQLite
integrity, and equal CSV/SQLite content. The v1.3 source hash remains unchanged.

The independent locked probability audit is complete. Event-existence
precision passed, but usable-record precision, single-event accuracy, and date
accuracy failed the prespecified thresholds. The candidate therefore remains
unpromoted with `fresh_locked_validation_complete=false`; see
`docs/V14_FINAL_VALIDATION_RESULT.md`.
