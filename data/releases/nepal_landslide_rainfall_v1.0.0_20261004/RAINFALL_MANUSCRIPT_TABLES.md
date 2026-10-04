# Rainfall manuscript tables

**Generated file — do not edit by hand.** Rebuild with
`PYTHONPATH=src python3 scripts/build_manuscript_tables.py` after every
`rainfall_release`. Every number is read from the analysis outputs, so these
tables cannot drift away from the analysis the way a hand-maintained copy did.

Analysis version 1.0.0. Threshold confidence intervals are estimated in the
development split; performance intervals in the untouched temporal test split.

## Table 1. Primary exposure — concurrent windows, including the reported event day

| Window | Development AUC | Threshold (mm) | Threshold 95% CI (development) | Test AUC (95% CI) | Test sensitivity | Test specificity |
|---|---:|---:|---:|---:|---:|---:|
| 1 day | 0.625 | 7.0 | 3.3–17.2 | 0.648 (0.614–0.680) | 0.470 | 0.755 |
| **3 days (selected)** | 0.646 | 31.7 | 15.2–38.2 | 0.686 (0.647–0.722) | 0.473 | 0.789 |
| 5 days | 0.641 | 45.5 | 25.0–73.9 | 0.680 (0.636–0.719) | 0.541 | 0.707 |
| 7 days | 0.629 | 76.0 | 49.0–99.9 | 0.674 (0.632–0.711) | 0.449 | 0.763 |

## Table 2. Co-primary exposure — strictly antecedent windows, excluding the event day

| Window | Development AUC | Threshold (mm) | Threshold 95% CI (development) | Test AUC (95% CI) | Test sensitivity | Test specificity |
|---|---:|---:|---:|---:|---:|---:|
| 1 day | 0.618 | 4.3 | 2.0–10.5 | 0.630 (0.594–0.664) | 0.505 | 0.698 |
| **3 days (selected)** | 0.621 | 21.0 | 14.7–29.1 | 0.646 (0.604–0.682) | 0.557 | 0.669 |
| 5 days | 0.613 | 43.7 | 24.2–56.4 | 0.643 (0.597–0.683) | 0.488 | 0.677 |
| 7 days | 0.596 | 60.4 | 33.0–101.9 | 0.641 (0.601–0.677) | 0.518 | 0.650 |

## Table 3. Conditional (within-matched-set) logistic models

| Split | Exposure | Window | Odds ratio per 10 mm | 95% CI | Within-stratum concordance |
|---|---|---:|---:|---:|---:|
| All years | Concurrent | 3 | 1.248 | 1.204–1.293 | 0.671 |
| All years | Strictly antecedent | 3 | 1.189 | 1.152–1.226 | 0.630 |
| Development | Concurrent | 3 | 1.218 | 1.174–1.263 | 0.657 |
| Development | Strictly antecedent | 3 | 1.169 | 1.129–1.211 | 0.625 |
| Temporal test | Concurrent | 3 | 1.302 | 1.218–1.392 | 0.689 |
| Temporal test | Strictly antecedent | 3 | 1.224 | 1.151–1.301 | 0.637 |

## Table 4. Resampled validation

| Scheme | Exposure | Window | Folds | Median AUC | AUC range | SD | Threshold range (mm) |
|---|---|---:|---:|---:|---:|---:|---:|
| leave one year out | Concurrent | 3 | 12 | 0.663 | 0.576–0.711 | 0.045 | 31.7–31.7 |
| spatial holdout | Concurrent | 3 | 5 | 0.663 | 0.640–0.687 | 0.020 | 20.4–31.7 |
| leave one year out | Strictly antecedent | 3 | 12 | 0.631 | 0.566–0.676 | 0.042 | 21.0–21.8 |
| spatial holdout | Strictly antecedent | 3 | 5 | 0.620 | 0.599–0.653 | 0.022 | 21.0–22.8 |

## Table 5. Sensitivity analyses

| Variant | Exposure | Window | Threshold (mm) | Test cases | Test controls | Development AUC | Test AUC | Sensitivity | Specificity |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `primary_conf_ge_0.78` | Concurrent | 3 | 31.7 | 566 | 2308 | 0.646 | 0.686 | 0.473 | 0.789 |
| `primary_conf_ge_0.78` | Strictly antecedent | 3 | 21.0 | 566 | 2308 | 0.621 | 0.646 | 0.557 | 0.669 |
| `all_dated_events` | Concurrent | 3 | 33.7 | 632 | 2570 | 0.647 | 0.671 | 0.437 | 0.785 |
| `all_dated_events` | Strictly antecedent | 3 | 21.0 | 632 | 2570 | 0.625 | 0.640 | 0.559 | 0.657 |
| `high_conf_ge_0.80` | Concurrent | 3 | 31.3 | 440 | 1766 | 0.637 | 0.676 | 0.489 | 0.760 |
| `high_conf_ge_0.80` | Strictly antecedent | 1 | 3.3 | 440 | 1766 | 0.622 | 0.625 | 0.545 | 0.651 |
| `primary_date_minus_1d` | Concurrent | 3 | 21.0 | 566 | 2303 | 0.629 | 0.649 | 0.557 | 0.666 |
| `primary_date_minus_1d` | Strictly antecedent | 3 | 15.9 | 566 | 2303 | 0.590 | 0.619 | 0.590 | 0.575 |
| `primary_date_plus_1d` | Concurrent | 5 | 46.9 | 566 | 2325 | 0.644 | 0.673 | 0.521 | 0.704 |
| `primary_date_plus_1d` | Strictly antecedent | 3 | 31.3 | 566 | 2325 | 0.648 | 0.668 | 0.473 | 0.766 |
| `primary_date_minus_3d` | Concurrent | 3 | 15.4 | 569 | 2317 | 0.572 | 0.621 | 0.592 | 0.560 |
| `primary_date_minus_3d` | Strictly antecedent | 1 | 0.0 | 569 | 2317 | 0.554 | 0.577 | 0.640 | 0.473 |
| `primary_date_plus_3d` | Concurrent | 7 | 87.9 | 565 | 2331 | 0.628 | 0.667 | 0.391 | 0.805 |
| `primary_date_plus_3d` | Strictly antecedent | 7 | 71.3 | 565 | 2331 | 0.635 | 0.668 | 0.492 | 0.714 |
| `include_known_nonrain_triggers` | Concurrent | 3 | 21.0 | 607 | 2493 | 0.638 | 0.672 | 0.575 | 0.671 |
| `include_known_nonrain_triggers` | Strictly antecedent | 3 | 21.0 | 607 | 2493 | 0.613 | 0.637 | 0.547 | 0.664 |
| `exclude_road_obstructions` | Concurrent | 3 | 21.1 | 284 | 1198 | 0.642 | 0.659 | 0.577 | 0.641 |
| `exclude_road_obstructions` | Strictly antecedent | 1 | 6.1 | 284 | 1198 | 0.620 | 0.608 | 0.479 | 0.707 |
| `balanced_source_panel` | Concurrent | 3 | 31.3 | 442 | 1771 | 0.653 | 0.678 | 0.480 | 0.786 |
| `balanced_source_panel` | Strictly antecedent | 3 | 21.0 | 442 | 1771 | 0.623 | 0.637 | 0.554 | 0.650 |
| `strict_matched_sets` | Concurrent | 5 | 45.5 | 417 | 1781 | 0.647 | 0.672 | 0.518 | 0.719 |
| `strict_matched_sets` | Strictly antecedent | 3 | 21.0 | 417 | 1781 | 0.621 | 0.636 | 0.535 | 0.674 |

## Table 6. Season stratification

| Season | Exposure | Window | Threshold (mm) | Development AUC | Test AUC | Sensitivity | Specificity |
|---|---|---:|---:|---:|---:|---:|---:|
| monsoon JJAS | Concurrent | 3 | 31.7 | 0.629 | 0.691 | 0.542 | 0.731 |
| monsoon JJAS | Strictly antecedent | 3 | 21.0 | 0.603 | 0.643 | 0.629 | 0.578 |
| non monsoon | Concurrent | 3 | 2.9 | 0.734 | 0.679 | 0.518 | 0.748 |
| non monsoon | Strictly antecedent | 3 | 5.0 | 0.686 | 0.637 | 0.418 | 0.812 |

## Table 7. Design and matching diagnostics

| Quantity | Value |
|---|---:|
| Canonical event records read | 2122 |
| Distinct district-days in the inventory | 1590 |
| Records sharing a district-day | 532 |
| Districts with at least one event | 74 |
| Monsoon share of events | 0.811 |
| Primary events before the rainfall join | 1710 |
| Excluded: event after the rainfall record ends | 19 |
| Rainfall record ends | 2026-07-31 |
| Matched sets (case-days) | 1278 |
| Control rows | 5460 |
| Cases with no eligible control | 131 (0.103) |
| Duplicate control rows | 0.199 |
| Maximum reuse of one control district-day | 6 |
