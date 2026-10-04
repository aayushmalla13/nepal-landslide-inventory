# v1.5 Candidate Result

The validated v1.5 identity, true-value, structured-attribute, and exact-date
preflight plans have been assembled into a locked candidate release.

- Source candidate: v1.4, 2,138 events
- v1.5 candidate: 2,122 unique events
- Identity: 38 old events superseded, 26 release-ready reconstructed events,
  9 merges into existing events, and 24 exact-date preflight exclusions
- True value: 21 corrections and 4 exclusions
- Structured attributes: 33 corrections and no exclusions
- Application log: 155 actions

The release has canonical districts, unique event IDs, exact ISO dates, SQLite
integrity, and equal CSV/SQLite content. The v1.4 source hash remains unchanged.

The independent locked probability audit is complete. Event-existence
precision and district accuracy passed, but usable-record precision,
single-event accuracy, and date accuracy failed the prespecified thresholds.
The candidate therefore remains unpromoted with
`fresh_locked_validation_complete=false`; see
`docs/V15_FINAL_VALIDATION_RESULT.md`.
