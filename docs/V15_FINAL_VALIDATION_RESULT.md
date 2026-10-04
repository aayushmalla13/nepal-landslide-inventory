# v1.5 Final Locked Validation Result

**Decision:** retain candidate status. Do not promote v1.5 under the full-record rule.

The 150-row locked stratified probability audit was completed by `aayush` and
scored without changing the prespecified promotion rule. All rows passed
structural and provenance validation. The scored eligible frame contains 568
previously unreviewed candidate events.

| Metric | Weighted estimate | 95% CI | Result |
|---|---:|---:|---|
| Event-existence precision | 0.958 | 0.923-0.986 | pass |
| Usable-record precision | 0.570 | 0.493-0.650 | fail |
| Single-event accuracy | 0.822 | 0.762-0.881 | fail |
| District accuracy | 0.910 | 0.865-0.953 | pass |
| Date accuracy | 0.753 | 0.678-0.823 | fail |
| Municipality accuracy | 0.859 | 0.783-0.923 | descriptive |
| Event-type accuracy | 0.893 | 0.843-0.937 | descriptive |
| Hazard-type accuracy | 0.902 | 0.853-0.944 | descriptive |
| Deaths exact accuracy | 0.867 | 0.813-0.916 | descriptive |
| Duplicate-merge accuracy | 0.942 | 0.826-1.000 | descriptive |

Event existence supports a validated high-precision event-detection claim.
The candidate does not support the broader validated high-precision full-record
claim because usable-record precision, single-event accuracy, and date accuracy
fail their locked thresholds.

The sample contains 6 non-events, 25 decisive multi-event records, 12 decisive
district errors, and 32 decisive date errors, with overlap among categories.
Two additional granularity labels, two district labels, and 13 date labels are
unclear.

Compared with v1.4, event-existence precision improved from 0.910 to 0.958,
deaths accuracy from 0.788 to 0.867, and duplicate-merge accuracy from 0.897 to
0.942. Date accuracy declined from 0.786 to 0.753, showing that date assignment
remains a systematic pipeline limitation rather than a finite review backlog.

The v1.5 release remains a locked candidate with
`fresh_locked_validation_complete=false`. This sample is spent and cannot be
used to validate a repaired candidate.
