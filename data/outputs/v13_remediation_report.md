# v1.3 remediation queue

**Status:** frozen and unapplied

Source candidate: `nepal_landslide_inventory_v1.2.0_candidate_20260929`
Actionable rows: 91 of 150
Population-weighted flagged share: 0.614

The weighted share is not an invalid-event rate. A valid event can be
queued for one attribute, and action counts overlap.

## Ordered work batches

| Category | Rows |
|---|---:|
| requires_true_value_review | 45 |
| structured_attribute_candidate | 24 |
| requires_article_mapping | 22 |

## Priority

| Category | Rows |
|---|---:|
| P0_identity_or_linkage | 64 |
| P1_attribute | 26 |
| P2_uncertain | 1 |

## Certainty

| Category | Rows |
|---|---:|
| confirmed | 68 |
| requires_review | 14 |
| mixed_confirmed_and_review | 9 |

## Systematic issue families

| Category | Rows |
|---|---:|
| event_date_resolution | 36 |
| casualty_extraction | 20 |
| location_role_resolution | 18 |
| event_type_classification | 15 |
| event_granularity | 14 |
| hazard_type_classification | 11 |
| scope_or_event_specificity | 10 |
| deduplication | 3 |

## Source domains

| Category | Rows |
|---|---:|
| nagariknews.nagariknetwork.com | 16 |
| myrepublica.nagariknetwork.com | 15 |
| setopati.com | 14 |
| nepalpress.com | 11 |
| english.onlinekhabar.com | 7 |
| ujyaaloonline.com | 6 |
| rajdhanidaily.com | 5 |
| onlinekhabar.com | 5 |
| thehimalayantimes.com | 5 |
| deshsanchar.com | 3 |
| ratopati.com | 2 |
| kathmandupost.com | 1 |
| english.nepalpress.com | 1 |

## Recommended actions

| Category | Rows |
|---|---:|
| correct_date | 23 |
| correct_deaths | 18 |
| correct_event_type | 15 |
| review_date | 13 |
| correct_district | 11 |
| correct_hazard_type | 10 |
| exclude_false_event | 8 |
| split_or_exclude_aggregate | 8 |
| review_event_granularity | 6 |
| correct_municipality | 3 |
| clear_deaths | 2 |
| recluster_articles | 2 |
| review_municipality | 2 |
| review_event_existence | 2 |
| review_district | 2 |
| review_duplicate_merge | 1 |
| review_hazard_type | 1 |

Article mapping and identity decisions must be completed before true-value
or structured-attribute corrections are applied. The v1.2 audit and this
queue remain immutable evidence throughout remediation.
