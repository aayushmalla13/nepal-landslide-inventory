# Post-correction validation result

**Decision:** do not promote

**Candidate:** `nepal_landslide_inventory_v0.7.0_candidate_20260916`

## Design

The locked validation used two samples that were scored separately:

- A 150-row stratified probability sample drawn from 2,723 eligible events that
  were untouched by the prior audit and correction process.
- A 50-row targeted challenge covering reconstructed events, merges, structured
  attribute corrections, and true-value corrections.

The fresh sample estimates candidate quality only for its eligible untouched
frame. The correction challenge is implementation QA and is not an inventory
precision estimate. Both files were completed by `reviewer_postcorr_A`; no
independent second review was performed for this gate.

## Fresh probability result

| Metric | Weighted estimate | 95% stratified-bootstrap CI |
|---|---:|---:|
| event existence precision | 0.833 | 0.774-0.888 |
| usable record precision | 0.358 | 0.284-0.437 |
| single event accuracy | 0.704 | 0.623-0.779 |
| district accuracy | 0.799 | 0.731-0.864 |
| date accuracy | 0.743 | 0.658-0.824 |
| municipality accuracy | 0.898 | 0.837-0.956 |
| event type accuracy | 0.683 | 0.616-0.752 |
| hazard type accuracy | 0.844 | 0.780-0.902 |
| deaths exact accuracy | 0.878 | 0.817-0.935 |
| duplicate merge accuracy | 0.854 | 0.739-0.946 |

The unweighted labels included 23 confirmed non-events among 150 sampled rows
and 43 multi-event failures among the 126 confirmed events. These are material
known defects, not merely a threshold choice.

Compared descriptively with the prior adjudicated v0.6 audit, event-existence
precision changed from 0.860 to 0.833, usable-record precision from 0.402 to
0.358, district accuracy from 0.845 to 0.799, and date accuracy from 0.762 to
0.743. These are not paired estimates: the releases, eligible frames, samples,
and review designs differ, so the changes must not be presented as formal
evidence of deterioration or improvement.

## Correction challenge

The targeted correction pass rate was 0.977 among 43 decisive rows; seven rows
were unclear. Merges, structured corrections, and true-value corrections had no
confirmed failures in their decisive challenge rows. One identity-add record,
`event_184f63e3ff3d7bcb`, failed because its evidence supports `debris_flow`
rather than the claimed generic `landslide` hazard type.

The challenge shows that the reviewed correction plans were mostly applied as
intended. It does not offset the residual errors found in the fresh sample.

## Release decision

No numeric promotion threshold was prespecified, so no post hoc cutoff is used.
The candidate is nevertheless not promoted because the fresh audit directly
demonstrates substantial residual false-event, event-identity, event-type,
date, and district errors. The candidate remains a traceable correction
artifact, not the final paper dataset.

## Next remediation gate

The 137-row frozen remediation queue is complete. See
`docs/POST_CORRECTION_REMEDIATION_QUEUE.md`.

1. Complete the 67-row article-mapping gate while keeping the completed audits
   and frozen remediation queue immutable.
2. Group failures by source and root cause; prioritize false events and
   multi-event cluster decomposition, then event type, date, and district.
3. Correct the confirmed Akkarebhir challenge failure and review the seven
   unclear identity-add cases without counting them as passes.
4. Implement generalizable parser, specificity, and deduplication fixes with
   regression tests before applying event-level corrections.
5. Assemble a new checksummed candidate and draw a new probability sample that
   excludes all previously reviewed events and article evidence.

Do not rescore the current 200 rows as evidence for a repaired candidate.

## Reproducibility

- Scorer: `scripts/score_post_correction_validation.py`
- Machine-readable score:
  `data/outputs/post_correction_validation_score.json`
- Rendered score: `data/outputs/post_correction_validation_report.md`
- Fresh completed SHA-256:
  `060266bca594690d9ace5df8c851ecee31e0ea987e45f0a93bf162f196667484`
- Challenge completed SHA-256:
  `fb4cb0c618a7eca8a84199df3e8dd41b4e04dc62178db81ec1397707f8281978`
