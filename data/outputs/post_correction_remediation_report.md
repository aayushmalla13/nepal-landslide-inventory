# Post-correction remediation queue

Queue rows: 137
Fresh findings: 124 of 150
Fresh population-weighted flagged share: 0.841
Challenge findings: 13 of 50

The weighted flagged share is not the invalid-record rate. A row can be
flagged for one attribute, and action counts overlap.

## Ordered work batches

| Category | Rows |
|---|---:|
| requires_article_mapping | 67 |
| requires_true_value_review | 45 |
| structured_attribute_candidate | 25 |

## Priority

| Category | Rows |
|---|---:|
| P0_identity_or_linkage | 106 |
| P1_attribute | 27 |
| P2_uncertain | 4 |

## Systematic issue families

| Category | Rows |
|---|---:|
| event_date_resolution | 45 |
| event_granularity | 44 |
| event_type_classification | 38 |
| location_role_resolution | 36 |
| hazard_type_classification | 25 |
| casualty_extraction | 24 |
| scope_or_event_specificity | 24 |
| deduplication | 11 |

## Source domains

| Category | Rows |
|---|---:|
| setopati.com | 20 |
| myrepublica.nagariknetwork.com | 18 |
| ujyaaloonline.com | 18 |
| nagariknews.nagariknetwork.com | 17 |
| rajdhanidaily.com | 14 |
| deshsanchar.com | 13 |
| thehimalayantimes.com | 12 |
| nepalpress.com | 7 |
| onlinekhabar.com | 7 |
| english.onlinekhabar.com | 6 |
| english.nepalpress.com | 2 |
| risingnepaldaily.com | 1 |
| ratopati.com | 1 |
| kathmandupost.com | 1 |

## Actions

| Category | Rows |
|---|---:|
| split_or_exclude_aggregate | 43 |
| correct_event_type | 37 |
| correct_date | 27 |
| correct_district | 24 |
| exclude_false_event | 23 |
| correct_hazard_type | 18 |
| review_date | 18 |
| correct_deaths | 13 |
| recluster_articles | 11 |
| review_deaths | 11 |
| review_hazard_type | 7 |
| correct_municipality | 6 |
| review_district | 5 |
| review_municipality | 2 |
| review_event_type | 1 |
| review_event_existence | 1 |
| review_event_granularity | 1 |

Fresh and challenge rows remain distinct in the queue. Challenge rows
must not be weighted or pooled into population estimates. All findings
remain unapplied until their assigned correction gate is completed.
