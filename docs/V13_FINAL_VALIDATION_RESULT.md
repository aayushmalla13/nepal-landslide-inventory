# v1.3 Final Locked Validation Result

**Decision:** retain candidate status. Do not promote v1.3.

The 150-row locked stratified probability audit was completed by `aayush` and
scored without changing the prespecified rule. All rows passed structural and
provenance validation. The scored eligible frame contains 885 previously
unreviewed candidate events.

| Metric | Weighted estimate | 95% CI | Result |
|---|---:|---:|---|
| Event-existence precision | 0.951 | 0.915-0.980 | pass |
| Usable-record precision | 0.604 | 0.526-0.682 | fail |
| Single-event accuracy | 0.854 | 0.791-0.909 | pass |
| District accuracy | 0.941 | 0.898-0.977 | pass |
| Date accuracy | 0.778 | 0.708-0.844 | fail |
| Municipality accuracy | 0.893 | 0.830-0.952 | descriptive |
| Event-type accuracy | 0.896 | 0.844-0.943 | descriptive |
| Hazard-type accuracy | 0.967 | 0.938-0.993 | descriptive |
| Deaths exact accuracy | 0.809 | 0.753-0.864 | descriptive |
| Duplicate-merge accuracy | 1.000 | 1.000-1.000 | descriptive |

Event existence is strong enough for a high-precision event-detection claim,
but the candidate does not support the broader validated high-precision record
claim. The usable-record and date checks fail both their point-estimate and
confidence-bound requirements. The dominant sampled defects are 30 incorrect
dates, 19 multi-event records, 8 incorrect districts, and 7 non-events, with
overlap among these categories.

The v1.3 release remains a locked candidate. Its release manifest must keep
`fresh_locked_validation_complete=false`. The v1.3 sample is now spent and may
be used for v1.4 remediation, but not for validating a repaired candidate.
Any v1.4 promotion attempt requires another independently drawn locked sample.
