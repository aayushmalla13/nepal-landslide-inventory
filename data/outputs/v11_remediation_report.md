# v1.1 remediation queue

**Status:** frozen and unapplied

Source candidate: `nepal_landslide_inventory_v1.0.0_candidate_20260927`
Actionable rows: 123 of 150
Population-weighted flagged share: 0.818

The weighted share is not an invalid-event rate. A valid event can be
queued for one attribute, and action counts overlap.

## Ordered work batches

| Category | Rows |
|---|---:|
| requires_true_value_review | 49 |
| structured_attribute_candidate | 38 |
| requires_article_mapping | 36 |

## Priority

| Category | Rows |
|---|---:|
| P0_identity_or_linkage | 82 |
| P1_attribute | 40 |
| P2_uncertain | 1 |

## Certainty

| Category | Rows |
|---|---:|
| confirmed | 100 |
| mixed_confirmed_and_review | 14 |
| requires_review | 9 |

## Systematic issue families

| Category | Rows |
|---|---:|
| event_type_classification | 68 |
| event_date_resolution | 41 |
| event_granularity | 28 |
| location_role_resolution | 26 |
| casualty_extraction | 19 |
| scope_or_event_specificity | 11 |
| hazard_type_classification | 4 |
| deduplication | 3 |

## Source domains

| Category | Rows |
|---|---:|
| setopati.com | 24 |
| myrepublica.nagariknetwork.com | 17 |
| thehimalayantimes.com | 16 |
| nagariknews.nagariknetwork.com | 16 |
| ujyaaloonline.com | 16 |
| nepalpress.com | 9 |
| english.onlinekhabar.com | 8 |
| deshsanchar.com | 6 |
| onlinekhabar.com | 5 |
| rajdhanidaily.com | 2 |
| kathmandupost.com | 2 |
| ratopati.com | 1 |
| english.nepalpress.com | 1 |

## Recommended actions

| Category | Rows |
|---|---:|
| correct_event_type | 68 |
| correct_date | 26 |
| split_or_exclude_aggregate | 25 |
| correct_deaths | 19 |
| correct_district | 17 |
| review_date | 15 |
| correct_municipality | 9 |
| exclude_false_event | 8 |
| correct_hazard_type | 3 |
| review_event_existence | 3 |
| review_event_granularity | 3 |
| recluster_articles | 2 |
| review_district | 2 |
| review_duplicate_merge | 1 |
| review_hazard_type | 1 |

Article mapping and identity decisions must be completed before true-value
or structured-attribute corrections are applied. The v1.0 audit and this
queue remain immutable evidence throughout remediation.
