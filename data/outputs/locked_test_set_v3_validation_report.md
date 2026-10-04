# Final Validation and Release Summary

Generated: 2026-08-10T04:18:04Z

## Held-out article classification

Locked v3 sampled 386 articles from 3676 eligible articles after prior-evaluation and assisted-discovery exclusions. 382 rows were decidable and 4 were excluded as undecidable.

| Measure | Estimate | Stratified-bootstrap 95% CI |
|---|---:|---:|
| Precision | 0.680 | 0.609–0.749 |
| Recall | 0.851 | 0.787–0.915 |
| F1 | 0.756 | 0.702–0.809 |

These are population-weighted article-level headline metrics. Unweighted sample metrics are diagnostic and are not reportable as inventory-wide performance.

## Field extraction

District exact accuracy was 0.819, with coverage 0.922, among 123 true headline articles with district truth.

Event-date accuracy is not reportable: only 5 rows contained event-date truth, below the prespecified minimum of 30.

## Released canonical inventory

- Canonical events: 1614
- Date range: 2015-04-07 to 2026-08-07
- Districts represented: 73
- Representative news sources: 9
- Road-obstruction subtype: 343
- Non-single records: 0
- Canonical CSV SHA-256: `1d2a1fcafafbf1863ede9c2a81020d8752026cf52a7665105e68d1322a06584f`

## Reviewed post-validation corrections

A versioned correction layer containing 4 records was applied after locked-v3 scoring. It corrected one verified event year and excluded three verified foreign, multi-event, or aggregate articles from canonical release construction.

Locked v3 therefore validates the pre-correction article classifier. The reviewed corrections are a transparent release-QA layer and were not used to recompute or improve the held-out score. Event-date performance remains explicitly unreported.

## Limitations

- The held-out design evaluates article-level detection, not deduplicated event-level precision or cluster completeness.
- News availability and archive depth vary by source and year; temporal counts must not be interpreted as an unbiased landslide trend.
- The final article-level precision estimate implies that residual false positives remain in the automated inventory.
- Any future classifier change requires a new locked test version.
