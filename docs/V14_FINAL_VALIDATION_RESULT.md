# v1.4 Final Locked Validation Result

**Decision:** retain candidate status. Do not promote v1.4.

The 150-row locked stratified probability audit was completed by `aayush` and
scored without changing the prespecified promotion rule. All rows passed
structural and provenance validation. The scored eligible frame contains 727
previously unreviewed candidate events.

| Metric | Weighted estimate | 95% CI | Result |
|---|---:|---:|---|
| Event-existence precision | 0.910 | 0.868-0.950 | pass |
| Usable-record precision | 0.563 | 0.481-0.643 | fail |
| Single-event accuracy | 0.803 | 0.733-0.869 | fail |
| District accuracy | 0.921 | 0.872-0.962 | pass |
| Date accuracy | 0.786 | 0.714-0.853 | fail |
| Municipality accuracy | 0.868 | 0.798-0.932 | descriptive |
| Event-type accuracy | 0.903 | 0.857-0.948 | descriptive |
| Hazard-type accuracy | 0.869 | 0.813-0.921 | descriptive |
| Deaths exact accuracy | 0.788 | 0.726-0.851 | descriptive |
| Duplicate-merge accuracy | 0.897 | 0.794-1.000 | descriptive |

Event existence remains strong enough for a high-precision event-detection
claim. The candidate does not support the broader validated high-precision
record claim because usable-record precision, single-event accuracy, and date
accuracy fail the locked thresholds.

The sample contains 13 non-events, 27 decisive multi-event records, 10
decisive district errors, and 25 decisive date errors, with overlap among
failure categories. Six additional granularity labels and 12 date labels are
unclear.

The v1.4 release remains a locked candidate. Its release manifest must keep
`fresh_locked_validation_complete=false`. This sample is now spent and may be
used for remediation, but it cannot validate a repaired candidate. Any future
promotion attempt requires a newly assembled candidate and another independent
locked sample.
