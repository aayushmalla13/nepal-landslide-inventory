# Final Validation and Release Summary

Generated: 2026-09-15T02:59:16Z

## Held-out article classification

Locked v7 sampled 395 articles from 9504 eligible articles after prior-evaluation and assisted-discovery exclusions. 395 rows were decidable and 0 were excluded as undecidable.

| Measure | Estimate | Stratified-bootstrap 95% CI |
|---|---:|---:|
| Precision | 0.626 | 0.552–0.701 |
| Recall | 0.759 | 0.682–0.843 |
| F1 | 0.686 | 0.624–0.750 |

These are population-weighted article-level headline metrics. Unweighted sample metrics are diagnostic and are not reportable as inventory-wide performance.

## Field extraction

District exact accuracy was 0.828, with coverage 0.922, among 127 true headline articles with district truth.

Event-date exact accuracy was 0.824, with coverage 0.976, among 83 true headline articles with event-date truth.

## Released canonical inventory

- Canonical events: 2885
- Date range: 2015-03-07 to 2026-08-09
- Districts represented: 76
- Representative news sources: 17
- Road-obstruction subtype: 587
- Non-single records: 0
- Canonical CSV SHA-256: `3b335babbfcbe0b50d2aad9023e08e55a2ca6e8e0881729615df33e2c9b9d0e8`

## Reviewed post-validation corrections

A versioned correction layer containing 5 records was applied after locked-v7 scoring. It records reviewed date corrections or exclusions from canonical release construction with source evidence and before/after state.

Locked v7 therefore validates the pre-correction article classifier. The reviewed corrections are a transparent release-QA layer and were not used to recompute or improve the held-out score. Event-date performance is reported because the prespecified minimum truth count was met.

## Limitations

- The held-out design evaluates article-level detection, not deduplicated event-level precision or cluster completeness.
- News availability and archive depth vary by source and year; temporal counts must not be interpreted as an unbiased landslide trend.
- The final article-level precision estimate implies that residual false positives remain in the automated inventory.
- Any future classifier change requires a new locked test version.
