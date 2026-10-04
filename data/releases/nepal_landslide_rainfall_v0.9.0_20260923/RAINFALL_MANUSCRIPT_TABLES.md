# Rainfall manuscript tables

**Generated file — do not edit by hand.** Rebuild with
`PYTHONPATH=src python3 scripts/build_manuscript_tables.py` after every
`rainfall_release`. Every number is read from the analysis outputs, so these
tables cannot drift away from the analysis the way a hand-maintained copy did.

Analysis version 0.9.0. Threshold confidence intervals are estimated in the
development split; performance intervals in the untouched temporal test split.

## Table 1. Primary exposure — concurrent windows, including the reported event day

| Window | Development AUC | Threshold (mm) | Threshold 95% CI (development) | Test AUC (95% CI) | Test sensitivity | Test specificity |
|---|---:|---:|---:|---:|---:|---:|
| 1 day | 0.619 | 15.9 | 0.6–17.6 | 0.637 (0.614–0.663) | 0.289 | 0.884 |
| 3 days | 0.649 | 31.6 | 21.1–38.3 | 0.683 (0.653–0.711) | 0.448 | 0.802 |
| **5 days (selected)** | 0.652 | 51.6 | 43.9–63.7 | 0.677 (0.644–0.705) | 0.458 | 0.776 |
| 7 days | 0.644 | 76.0 | 45.9–87.4 | 0.673 (0.636–0.702) | 0.420 | 0.790 |

## Table 2. Co-primary exposure — strictly antecedent windows, excluding the event day

| Window | Development AUC | Threshold (mm) | Threshold 95% CI (development) | Test AUC (95% CI) | Test sensitivity | Test specificity |
|---|---:|---:|---:|---:|---:|---:|
| 1 day | 0.613 | 7.1 | 2.0–13.0 | 0.614 (0.592–0.638) | 0.420 | 0.772 |
| **3 days (selected)** | 0.625 | 23.7 | 17.3–44.9 | 0.651 (0.617–0.678) | 0.511 | 0.722 |
| 5 days | 0.623 | 43.7 | 24.3–72.7 | 0.646 (0.610–0.676) | 0.477 | 0.704 |
| 7 days | 0.609 | 59.4 | 48.7–96.0 | 0.645 (0.604–0.676) | 0.514 | 0.676 |

## Table 3. Conditional (within-matched-set) logistic models

| Split | Exposure | Window | Odds ratio per 10 mm | 95% CI | Within-stratum concordance |
|---|---|---:|---:|---:|---:|
| All years | Concurrent | 5 | 1.233 | 1.198–1.269 | 0.666 |
| All years | Strictly antecedent | 3 | 1.213 | 1.175–1.253 | 0.637 |
| Development | Concurrent | 5 | 1.228 | 1.186–1.271 | 0.659 |
| Development | Strictly antecedent | 3 | 1.191 | 1.148–1.236 | 0.625 |
| Temporal test | Concurrent | 5 | 1.240 | 1.188–1.293 | 0.676 |
| Temporal test | Strictly antecedent | 3 | 1.255 | 1.188–1.325 | 0.654 |

## Table 4. Resampled validation

| Scheme | Exposure | Window | Folds | Median AUC | AUC range | SD | Threshold range (mm) |
|---|---|---:|---:|---:|---:|---:|---:|
| leave one year out | Concurrent | 5 | 12 | 0.651 | 0.566–0.711 | 0.050 | 45.3–45.5 |
| spatial holdout | Concurrent | 5 | 5 | 0.661 | 0.638–0.689 | 0.019 | 45.3–45.5 |
| leave one year out | Strictly antecedent | 3 | 12 | 0.633 | 0.575–0.664 | 0.038 | 19.1–22.4 |
| spatial holdout | Strictly antecedent | 3 | 5 | 0.632 | 0.619–0.657 | 0.014 | 19.1–22.1 |

## Table 5. Sensitivity analyses

| Variant | Exposure | Window | Threshold (mm) | Test cases | Test controls | Development AUC | Test AUC | Sensitivity | Specificity |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `primary_conf_ge_0.78` | Concurrent | 5 | 51.6 | 650 | 2591 | 0.652 | 0.677 | 0.458 | 0.776 |
| `primary_conf_ge_0.78` | Strictly antecedent | 3 | 23.7 | 650 | 2591 | 0.625 | 0.651 | 0.511 | 0.722 |
| `all_dated_events` | Concurrent | 5 | 51.6 | 741 | 2968 | 0.649 | 0.674 | 0.463 | 0.761 |
| `all_dated_events` | Strictly antecedent | 5 | 43.7 | 741 | 2968 | 0.627 | 0.651 | 0.495 | 0.699 |
| `high_conf_ge_0.80` | Concurrent | 5 | 50.5 | 488 | 1941 | 0.656 | 0.667 | 0.463 | 0.761 |
| `high_conf_ge_0.80` | Strictly antecedent | 3 | 23.7 | 488 | 1941 | 0.629 | 0.642 | 0.506 | 0.706 |
| `primary_date_minus_1d` | Concurrent | 3 | 20.0 | 650 | 2581 | 0.627 | 0.656 | 0.568 | 0.674 |
| `primary_date_minus_1d` | Strictly antecedent | 3 | 19.3 | 650 | 2581 | 0.600 | 0.624 | 0.522 | 0.665 |
| `primary_date_plus_1d` | Concurrent | 5 | 46.9 | 649 | 2597 | 0.646 | 0.676 | 0.513 | 0.725 |
| `primary_date_plus_1d` | Strictly antecedent | 5 | 51.6 | 649 | 2597 | 0.647 | 0.665 | 0.459 | 0.753 |
| `include_known_nonrain_triggers` | Concurrent | 5 | 51.6 | 789 | 3180 | 0.641 | 0.657 | 0.444 | 0.769 |
| `include_known_nonrain_triggers` | Strictly antecedent | 3 | 23.7 | 789 | 3180 | 0.616 | 0.633 | 0.488 | 0.714 |
| `exclude_road_obstructions` | Concurrent | 5 | 54.2 | 483 | 1963 | 0.648 | 0.660 | 0.416 | 0.789 |
| `exclude_road_obstructions` | Strictly antecedent | 3 | 20.0 | 483 | 1963 | 0.621 | 0.641 | 0.561 | 0.671 |
| `balanced_source_panel` | Concurrent | 5 | 51.6 | 512 | 2031 | 0.654 | 0.667 | 0.459 | 0.774 |
| `balanced_source_panel` | Strictly antecedent | 3 | 19.2 | 512 | 2031 | 0.625 | 0.637 | 0.576 | 0.656 |
| `strict_matched_sets` | Concurrent | 3 | 31.6 | 459 | 1996 | 0.649 | 0.678 | 0.447 | 0.802 |
| `strict_matched_sets` | Strictly antecedent | 3 | 23.7 | 459 | 1996 | 0.621 | 0.648 | 0.505 | 0.722 |

## Table 6. Season stratification

| Season | Exposure | Window | Threshold (mm) | Development AUC | Test AUC | Sensitivity | Specificity |
|---|---|---:|---:|---:|---:|---:|---:|
| monsoon JJAS | Concurrent | 5 | 51.6 | 0.641 | 0.666 | 0.529 | 0.695 |
| monsoon JJAS | Strictly antecedent | 3 | 23.7 | 0.617 | 0.634 | 0.582 | 0.627 |
| non monsoon | Concurrent | 5 | 12.6 | 0.694 | 0.719 | 0.469 | 0.833 |
| non monsoon | Strictly antecedent | 3 | 1.5 | 0.633 | 0.679 | 0.538 | 0.700 |

## Table 7. Design and matching diagnostics

| Quantity | Value |
|---|---:|
| Canonical event records read | 2872 |
| Distinct district-days in the inventory | 2247 |
| Records sharing a district-day | 625 |
| Districts with at least one event | 76 |
| Monsoon share of events | 0.771 |
| Primary events before the rainfall join | 1798 |
| Excluded: event after the rainfall record ends | 18 |
| Rainfall record ends | 2026-07-31 |
| Matched sets (case-days) | 1453 |
| Control rows | 6059 |
| Cases with no eligible control | 173 (0.119) |
| Duplicate control rows | 0.193 |
| Maximum reuse of one control district-day | 11 |
