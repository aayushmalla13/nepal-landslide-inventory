# v1.4 remediation queue

**Status:** frozen and unapplied

Source candidate: `nepal_landslide_inventory_v1.3.0_candidate_20260930`
Actionable rows: 83 of 150
Population-weighted flagged share: 0.559

The weighted share is not an invalid-event rate. A valid event can be
queued for one attribute, and action counts overlap.

## Ordered work batches

| Category | Rows |
|---|---:|
| requires_true_value_review | 35 |
| requires_article_mapping | 30 |
| structured_attribute_candidate | 18 |

## Priority

| Category | Rows |
|---|---:|
| P0_identity_or_linkage | 63 |
| P1_attribute | 19 |
| P2_uncertain | 1 |

## Certainty

| Category | Rows |
|---|---:|
| confirmed | 70 |
| mixed_confirmed_and_review | 9 |
| requires_review | 4 |

## Systematic issue families

| Category | Rows |
|---|---:|
| event_date_resolution | 39 |
| casualty_extraction | 28 |
| event_granularity | 23 |
| location_role_resolution | 20 |
| event_type_classification | 14 |
| scope_or_event_specificity | 7 |
| hazard_type_classification | 5 |
| deduplication | 1 |

## Source domains

| Category | Rows |
|---|---:|
| setopati.com | 19 |
| nagariknews.nagariknetwork.com | 13 |
| thehimalayantimes.com | 10 |
| myrepublica.nagariknetwork.com | 9 |
| ujyaaloonline.com | 7 |
| nepalpress.com | 7 |
| rajdhanidaily.com | 5 |
| deshsanchar.com | 4 |
| english.onlinekhabar.com | 4 |
| onlinekhabar.com | 3 |
| risingnepaldaily.com | 1 |
| ratopati.com | 1 |

## Recommended actions

| Category | Rows |
|---|---:|
| correct_date | 30 |
| correct_deaths | 24 |
| split_or_exclude_aggregate | 19 |
| correct_event_type | 14 |
| review_date | 9 |
| correct_municipality | 9 |
| correct_district | 8 |
| exclude_false_event | 7 |
| correct_hazard_type | 5 |
| review_event_granularity | 4 |
| clear_deaths | 3 |
| review_district | 2 |
| review_municipality | 1 |
| review_duplicate_merge | 1 |
| review_deaths | 1 |

Article mapping and identity decisions must be completed before true-value
or structured-attribute corrections are applied. The v1.3 audit and this
queue remain immutable evidence throughout remediation.
