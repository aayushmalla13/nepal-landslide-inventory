# Nepal landslide inventory v1.5.0 research release

This immutable bundle supports a validated high-precision web-derived 
landslide event-detection claim for Nepal. It is not validated as a 
complete census or as a high-precision full-record inventory.

- Canonical events: 2,122
- Event-existence precision: 0.958 (95% CI 0.923-0.986)
- District accuracy: 0.910 (95% CI 0.865-0.953)
- Validation sample: 150 locked, stratified probability-audit rows

The prespecified full-record promotion rule failed because usable-record 
precision, single-event accuracy, and exact-date accuracy did not meet 
their thresholds. Those results are retained in `validation/` and must 
be reported with analyses that depend on exact dates or event granularity.
