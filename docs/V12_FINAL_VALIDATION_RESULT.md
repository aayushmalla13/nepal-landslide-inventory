# v1.2 final locked validation result

Date: 2026-09-29

## Decision

**Retain candidate status.** The frozen v1.2 candidate does not pass every
prespecified promotion threshold.

The completed sample contains 150 rows and passed all structural checks against
the locked template, claims, order, weights, and draw manifest. The annotator
metadata was corrected from an accidentally entered AI identifier to
`human_v12_blind`; this result is a blinded human validation.

## Weighted results

| Metric | Estimate | 95% CI | Promotion result |
| --- | ---: | ---: | --- |
| Event-existence precision | 0.944 | 0.905-0.979 | pass |
| Usable-record precision | 0.640 | 0.557-0.721 | fail |
| Single-event accuracy | 0.942 | 0.901-0.977 | pass |
| District accuracy | 0.916 | 0.868-0.960 | pass |
| Date accuracy | 0.812 | 0.742-0.881 | fail |
| Municipality accuracy | 0.962 | 0.921-1.000 | descriptive |
| Event-type accuracy | 0.886 | 0.835-0.933 | descriptive |
| Hazard-type accuracy | 0.933 | 0.890-0.970 | descriptive |
| Deaths exact accuracy | 0.862 | 0.807-0.912 | descriptive |
| Duplicate-merge accuracy | 0.917 | 0.796-1.000 | descriptive |

The event-existence unclear fraction is 0.013 and passes its maximum of 0.05.

## Error profile

- 23 sampled events have an incorrect claimed date.
- 13 additional dates are unclear.
- 11 sampled events have an incorrect district and 2 are unclear.
- 8 sampled records combine more than one physical event and 6 are unclear.
- 8 sampled records are judged not to be inventory events and 2 are unclear.

The dominant date failures are follow-up reports assigned to the reporting day,
retrospectives assigned to a later administrative or publication date, and
malformed source dates. District failures are dominated by publisher datelines,
victim home districts, route destinations, and neighboring highway districts.
The non-event cases include foreign incidents, risk/prevention reports, opinion,
construction stories, and figurative use of landslide terminology.

## Scientific interpretation

The candidate can support qualified statements about high event-existence,
single-event, and district precision under this blinded human validation. It cannot be
promoted under the project's locked rule and must not be described as a
validated high-precision inventory overall because date and usable-record
precision fail.

## Required next cycle

1. Treat this sample as spent development evidence and preserve the frozen
   v1.2 candidate unchanged.
2. Treat the blinded human labels as development evidence for the next repair
   cycle, not as validation of a modified candidate.
3. Repair date inference first, then district attribution, non-event scope, and
   residual multi-event filtering.
4. Freeze a new candidate and draw another untouched probability sample that
   excludes all 150 v1.2 sampled event IDs and all 195 sampled article URLs.
5. Use blinded human annotation for the promotion claim, with an independent
   second-annotator subset where feasible.

The machine-readable result is
`data/outputs/v12_final_validation_score.json`; the generated report is
`data/outputs/v12_final_validation_report.md`.
