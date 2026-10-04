# v0.9 remediation queue

**Status:** frozen and unapplied

Source candidate: `nepal_landslide_inventory_v0.8.0_candidate_20260923`
Actionable rows: 112 of 150
Population-weighted flagged share: 0.760

The weighted share is not an invalid-event rate. A valid event can be
queued for one attribute, and action counts overlap.

## Ordered work batches

| Category | Rows |
|---|---:|
| requires_article_mapping | 54 |
| requires_true_value_review | 33 |
| structured_attribute_candidate | 25 |

## Priority

| Category | Rows |
|---|---:|
| P0_identity_or_linkage | 87 |
| P1_attribute | 25 |

## Certainty

| Category | Rows |
|---|---:|
| confirmed | 82 |
| mixed_confirmed_and_review | 22 |
| requires_review | 8 |

## Systematic issue families

| Category | Rows |
|---|---:|
| event_date_resolution | 43 |
| event_granularity | 39 |
| event_type_classification | 37 |
| location_role_resolution | 25 |
| casualty_extraction | 19 |
| scope_or_event_specificity | 18 |
| hazard_type_classification | 9 |
| deduplication | 8 |

## Source domains

| Category | Rows |
|---|---:|
| setopati.com | 20 |
| nagariknews.nagariknetwork.com | 13 |
| myrepublica.nagariknetwork.com | 13 |
| rajdhanidaily.com | 12 |
| nepalpress.com | 11 |
| ujyaaloonline.com | 10 |
| deshsanchar.com | 10 |
| thehimalayantimes.com | 9 |
| onlinekhabar.com | 7 |
| english.onlinekhabar.com | 3 |
| kathmandupost.com | 2 |
| ratopati.com | 2 |

## Recommended actions

| Category | Rows |
|---|---:|
| correct_event_type | 37 |
| split_or_exclude_aggregate | 35 |
| correct_date | 24 |
| review_date | 19 |
| correct_deaths | 17 |
| correct_district | 16 |
| exclude_false_event | 15 |
| correct_hazard_type | 8 |
| recluster_articles | 8 |
| correct_municipality | 6 |
| review_event_granularity | 4 |
| review_district | 3 |
| review_event_existence | 3 |
| review_deaths | 2 |
| review_municipality | 2 |
| review_hazard_type | 1 |

Article mapping and identity decisions must be completed before true-value
or structured-attribute corrections are applied. The v0.8 audit and this
queue remain immutable evidence throughout remediation.
