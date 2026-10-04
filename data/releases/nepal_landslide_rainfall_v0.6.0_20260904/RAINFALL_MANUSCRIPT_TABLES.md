# Rainfall manuscript tables

**Generated file — do not edit by hand.** Rebuild with
`PYTHONPATH=src python3 scripts/build_manuscript_tables.py` after every
`rainfall_release`. Every number is read from the analysis outputs, so these
tables cannot drift away from the analysis the way a hand-maintained copy did.

Analysis version 0.6.0. Threshold confidence intervals are estimated in the
development split; performance intervals in the untouched temporal test split.

## Table 1. Primary exposure — concurrent windows, including the reported event day

| Window | Development AUC | Threshold (mm) | Threshold 95% CI (development) | Test AUC (95% CI) | Test sensitivity | Test specificity |
|---|---:|---:|---:|---:|---:|---:|
| 1 day | 0.614 | 15.9 | 0.6–17.6 | 0.635 (0.606–0.665) | 0.286 | 0.881 |
| 3 days | 0.643 | 31.6 | 21.4–38.2 | 0.678 (0.649–0.706) | 0.441 | 0.797 |
| **5 days (selected)** | 0.646 | 51.6 | 33.7–61.7 | 0.675 (0.640–0.702) | 0.456 | 0.772 |
| 7 days | 0.636 | 76.0 | 45.3–81.4 | 0.672 (0.634–0.703) | 0.420 | 0.786 |

## Table 2. Co-primary exposure — strictly antecedent windows, excluding the event day

| Window | Development AUC | Threshold (mm) | Threshold 95% CI (development) | Test AUC (95% CI) | Test sensitivity | Test specificity |
|---|---:|---:|---:|---:|---:|---:|
| 1 day | 0.609 | 4.3 | 2.0–12.4 | 0.613 (0.589–0.638) | 0.480 | 0.695 |
| **3 days (selected)** | 0.621 | 23.7 | 17.3–33.1 | 0.649 (0.615–0.679) | 0.511 | 0.719 |
| 5 days | 0.619 | 43.3 | 24.3–63.4 | 0.647 (0.609–0.679) | 0.484 | 0.700 |
| 7 days | 0.603 | 55.2 | 39.1–96.0 | 0.647 (0.611–0.677) | 0.550 | 0.643 |

## Table 3. Conditional (within-matched-set) logistic models

| Split | Exposure | Window | Odds ratio per 10 mm | 95% CI | Within-stratum concordance |
|---|---|---:|---:|---:|---:|
| All years | Concurrent | 5 | 1.220 | 1.190–1.250 | 0.660 |
| All years | Strictly antecedent | 3 | 1.204 | 1.173–1.236 | 0.632 |
| Development | Concurrent | 5 | 1.212 | 1.173–1.253 | 0.651 |
| Development | Strictly antecedent | 3 | 1.181 | 1.141–1.222 | 0.618 |
| Temporal test | Concurrent | 5 | 1.231 | 1.184–1.279 | 0.673 |
| Temporal test | Strictly antecedent | 3 | 1.248 | 1.186–1.314 | 0.651 |

## Table 4. Resampled validation

| Scheme | Exposure | Window | Folds | Median AUC | AUC range | SD | Threshold range (mm) |
|---|---|---:|---:|---:|---:|---:|---:|
| leave one year out | Concurrent | 5 | 12 | 0.645 | 0.565–0.705 | 0.048 | 45.3–45.5 |
| spatial holdout | Concurrent | 5 | 5 | 0.656 | 0.637–0.681 | 0.016 | 45.3–47.4 |
| leave one year out | Strictly antecedent | 3 | 12 | 0.627 | 0.572–0.666 | 0.033 | 19.0–22.7 |
| spatial holdout | Strictly antecedent | 3 | 5 | 0.634 | 0.616–0.642 | 0.011 | 19.0–22.7 |

## Table 5. Sensitivity analyses

| Variant | Exposure | Window | Threshold (mm) | Test cases | Test controls | Development AUC | Test AUC | Sensitivity | Specificity |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `primary_conf_ge_0.78` | Concurrent | 5 | 51.6 | 669 | 2577 | 0.646 | 0.675 | 0.456 | 0.772 |
| `primary_conf_ge_0.78` | Strictly antecedent | 3 | 23.7 | 669 | 2577 | 0.621 | 0.649 | 0.511 | 0.719 |
| `all_dated_events` | Concurrent | 5 | 51.6 | 754 | 2936 | 0.646 | 0.672 | 0.458 | 0.761 |
| `all_dated_events` | Strictly antecedent | 5 | 43.2 | 754 | 2936 | 0.626 | 0.651 | 0.499 | 0.694 |
| `high_conf_ge_0.80` | Concurrent | 5 | 50.5 | 500 | 1912 | 0.648 | 0.665 | 0.462 | 0.752 |
| `high_conf_ge_0.80` | Strictly antecedent | 3 | 23.7 | 500 | 1912 | 0.625 | 0.641 | 0.510 | 0.698 |
| `primary_date_minus_1d` | Concurrent | 3 | 21.8 | 669 | 2572 | 0.623 | 0.658 | 0.540 | 0.706 |
| `primary_date_minus_1d` | Strictly antecedent | 3 | 19.3 | 669 | 2572 | 0.595 | 0.627 | 0.522 | 0.663 |
| `primary_date_plus_1d` | Concurrent | 5 | 46.9 | 668 | 2588 | 0.641 | 0.678 | 0.510 | 0.724 |
| `primary_date_plus_1d` | Strictly antecedent | 5 | 51.6 | 668 | 2588 | 0.640 | 0.664 | 0.457 | 0.752 |
| `include_known_nonrain_triggers` | Concurrent | 5 | 51.6 | 811 | 3164 | 0.638 | 0.659 | 0.440 | 0.771 |
| `include_known_nonrain_triggers` | Strictly antecedent | 3 | 23.7 | 811 | 3164 | 0.617 | 0.634 | 0.486 | 0.718 |
| `exclude_road_obstructions` | Concurrent | 5 | 54.2 | 514 | 2030 | 0.645 | 0.660 | 0.418 | 0.786 |
| `exclude_road_obstructions` | Strictly antecedent | 3 | 20.0 | 514 | 2030 | 0.620 | 0.644 | 0.560 | 0.671 |
| `balanced_source_panel` | Concurrent | 5 | 51.6 | 530 | 2010 | 0.648 | 0.667 | 0.455 | 0.776 |
| `balanced_source_panel` | Strictly antecedent | 5 | 37.5 | 530 | 2010 | 0.621 | 0.640 | 0.532 | 0.644 |
| `strict_matched_sets` | Concurrent | 3 | 31.3 | 469 | 2040 | 0.643 | 0.672 | 0.433 | 0.796 |
| `strict_matched_sets` | Strictly antecedent | 3 | 23.7 | 469 | 2040 | 0.617 | 0.643 | 0.501 | 0.724 |

## Table 6. Season stratification

| Season | Exposure | Window | Threshold (mm) | Development AUC | Test AUC | Sensitivity | Specificity |
|---|---|---:|---:|---:|---:|---:|---:|
| monsoon JJAS | Concurrent | 5 | 51.6 | 0.633 | 0.658 | 0.526 | 0.687 |
| monsoon JJAS | Strictly antecedent | 3 | 23.7 | 0.611 | 0.629 | 0.583 | 0.620 |
| non monsoon | Concurrent | 5 | 12.6 | 0.689 | 0.722 | 0.473 | 0.841 |
| non monsoon | Strictly antecedent | 3 | 4.8 | 0.626 | 0.676 | 0.439 | 0.839 |

## Table 7. Design and matching diagnostics

| Quantity | Value |
|---|---:|
| Canonical event records read | 2885 |
| Distinct district-days in the inventory | 2319 |
| Records sharing a district-day | 566 |
| Districts with at least one event | 76 |
| Monsoon share of events | 0.763 |
| Primary events before the rainfall join | 1846 |
| Excluded: event after the rainfall record ends | 18 |
| Rainfall record ends | 2026-07-31 |
| Matched sets (case-days) | 1508 |
| Control rows | 6164 |
| Cases with no eligible control | 200 (0.133) |
| Duplicate control rows | 0.188 |
| Maximum reuse of one control district-day | 8 |

