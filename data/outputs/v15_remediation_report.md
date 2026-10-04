# v1.5 remediation queue

**Status:** frozen and unapplied

Source candidate: `nepal_landslide_inventory_v1.4.0_candidate_20261002`
Actionable rows: 104 of 150
Population-weighted flagged share: 0.695

The weighted share is not an invalid-event rate. A valid event can be
queued for one attribute, and action counts overlap.

## Ordered work batches

| Category | Rows |
|---|---:|
| requires_article_mapping | 46 |
| structured_attribute_candidate | 33 |
| requires_true_value_review | 25 |

## Priority

| Category | Rows |
|---|---:|
| P0_identity_or_linkage | 70 |
| P1_attribute | 34 |

## Certainty

| Category | Rows |
|---|---:|
| confirmed | 89 |
| mixed_confirmed_and_review | 9 |
| requires_review | 6 |

## Systematic issue families

| Category | Rows |
|---|---:|
| event_date_resolution | 37 |
| event_granularity | 33 |
| casualty_extraction | 30 |
| location_role_resolution | 22 |
| hazard_type_classification | 21 |
| scope_or_event_specificity | 13 |
| event_type_classification | 13 |
| deduplication | 3 |

## Source domains

| Category | Rows |
|---|---:|
| setopati.com | 25 |
| nagariknews.nagariknetwork.com | 16 |
| thehimalayantimes.com | 12 |
| ujyaaloonline.com | 11 |
| myrepublica.nagariknetwork.com | 9 |
| onlinekhabar.com | 7 |
| deshsanchar.com | 7 |
| english.onlinekhabar.com | 6 |
| nepalpress.com | 5 |
| rajdhanidaily.com | 3 |
| ratopati.com | 2 |
| english.nepalpress.com | 1 |

## Recommended actions

| Category | Rows |
|---|---:|
| correct_deaths | 30 |
| split_or_exclude_aggregate | 27 |
| correct_date | 25 |
| correct_hazard_type | 18 |
| exclude_false_event | 13 |
| correct_event_type | 13 |
| review_date | 12 |
| correct_municipality | 12 |
| correct_district | 10 |
| review_event_granularity | 6 |
| review_hazard_type | 3 |
| review_district | 2 |
| recluster_articles | 2 |
| review_duplicate_merge | 1 |

Article mapping and identity decisions must be completed before true-value
or structured-attribute corrections are applied. The v1.4 audit and this
queue remain immutable evidence throughout remediation.
