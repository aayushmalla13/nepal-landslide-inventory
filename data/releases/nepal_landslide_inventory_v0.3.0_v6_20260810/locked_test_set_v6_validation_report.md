# Final Validation and Release Summary

Generated: 2026-08-12T17:44:11Z

## Held-out article classification

Locked v6 sampled 388 articles from 5869 eligible articles after prior-evaluation and assisted-discovery exclusions. 387 rows were decidable and 1 was excluded as undecidable.

| Measure | Estimate | Stratified-bootstrap 95% CI |
|---|---:|---:|
| Precision | 0.742 | 0.675–0.807 |
| Recall | 0.822 | 0.744–0.910 |
| F1 | 0.780 | 0.723–0.834 |

These are population-weighted article-level headline metrics. Unweighted sample metrics are diagnostic and are not reportable as inventory-wide performance.

## Field extraction

District exact accuracy was 0.822, with coverage 0.927, among 123 true headline articles with district truth.

Event-date accuracy is not reportable: only 18 rows contained event-date truth, below the prespecified minimum of 30.

## Released canonical inventory

- Canonical events: 3114
- Date range: 2015-03-07 to 2026-08-09
- Districts represented: 76
- Representative news sources: 17
- Road-obstruction subtype: 603
- Non-single records: 0
- Canonical CSV SHA-256: `5a8010a2c7c95e4bbae9e5f0655cd01e1bba6c1c623492cf87677c09d628e2b8`

## Reviewed post-validation corrections

A versioned correction layer containing 5 records was applied after locked-v6 scoring. It records reviewed date corrections or exclusions from canonical release construction with source evidence and before/after state.

Locked v6 therefore validates the pre-correction article classifier. The reviewed corrections are a transparent release-QA layer and were not used to recompute or improve the held-out score. Event-date performance remains explicitly unreported.

## Limitations

- The held-out design evaluates article-level detection, not deduplicated event-level precision or cluster completeness.
- News availability and archive depth vary by source and year; temporal counts must not be interpreted as an unbiased landslide trend.
- The final article-level precision estimate implies that residual false positives remain in the automated inventory.
- Any future classifier change requires a new locked test version.
