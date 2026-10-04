# Rainfall manuscript tables

Analysis version 0.2.0. Threshold confidence intervals are estimated in the
development split; performance intervals in the untouched temporal test split.

## Table 1. Primary exposure — concurrent windows, including the reported event day

| Window | Development AUC | Threshold (mm) | Threshold 95% CI (development) | Test AUC (95% CI) | Test sensitivity | Test specificity |
|---|---:|---:|---:|---:|---:|---:|
| 1 day | 0.613 | 7.2 | 0.5–17.4 | 0.647 (0.626–0.672) | 0.430 | 0.776 |
| 3 days | 0.642 | 31.6 | 11.7–40.0 | 0.694 (0.663–0.725) | 0.449 | 0.821 |
| **5 days (selected)** | **0.642** | **45.4** | **26.8–72.1** | **0.693 (0.657–0.722)** | **0.509** | **0.764** |
| 7 days | 0.635 | 70.3 | 45.6–81.4 | 0.685 (0.649–0.715) | 0.433 | 0.793 |

The selected window is based only on development AUC, with ties broken toward
the shorter window. Test values for the other windows are descriptive and were
not used to change the selection.

## Table 2. Co-primary exposure — strictly antecedent windows, excluding the reported event day

| Window | Development AUC | Threshold (mm) | Threshold 95% CI (development) | Test AUC (95% CI) | Test sensitivity | Test specificity |
|---|---:|---:|---:|---:|---:|---:|
| 1 day | 0.608 | 7.1 | 1.8–11.3 | 0.629 (0.604–0.655) | 0.425 | 0.773 |
| **3 days (selected)** | **0.622** | **19.1** | **12.7–40.0** | **0.664 (0.628–0.697)** | **0.564** | **0.685** |
| 5 days | 0.618 | 43.7 | 24.3–63.4 | 0.662 (0.622–0.696) | 0.458 | 0.744 |
| 7 days | 0.606 | 55.4 | 48.3–96.2 | 0.662 (0.622–0.695) | 0.528 | 0.694 |

CHIRPS reports a 24-hour total and media event dates carry no time of day, so a
concurrent window can include rain that fell after failure. Excluding the event
day costs roughly 0.03 of AUC; these values bound the signal available before a
failure.

## Table 3. Within-matched-set association (conditional logistic regression)

Stratified by matched set; district-clustered sandwich standard errors; 1,322
strata with at least one control. Absolute risk is not identifiable in a matched
case-control sample and is not reported.

| Split | Exposure | Window | Odds ratio per 10 mm | 95% CI | Within-stratum concordance |
|---|---|---:|---:|---:|---:|
| All years | Concurrent | 5 | 1.227 | 1.193–1.261 | 0.671 |
| Development | Concurrent | 5 | 1.200 | 1.161–1.240 | 0.650 |
| Temporal test | Concurrent | 5 | 1.275 | 1.218–1.336 | 0.703 (0.662–0.740) |
| All years | Strictly antecedent | 3 | 1.221 | 1.188–1.255 | 0.645 |
| Development | Strictly antecedent | 3 | 1.184 | 1.142–1.227 | 0.627 |
| Temporal test | Strictly antecedent | 3 | 1.305 | 1.233–1.381 | 0.671 (0.628–0.707) |

Within-stratum concordance tracks the pooled AUC (0.650 vs 0.642 in development;
0.703 vs 0.693 in the test split), confirming that the pooled ROC is not
materially distorted by the matched structure.

## Table 4. Held-out validation

| Scheme | Exposure | Window | Folds | Median AUC | Range | SD | Threshold range (mm) |
|---|---|---:|---:|---:|---:|---:|---:|
| Leave-one-year-out | Concurrent | 5 | 12 | 0.652 | 0.563–0.710 | 0.053 | 45.38–45.42 |
| Spatial (district folds) | Concurrent | 5 | 5 | 0.667 | 0.640–0.677 | 0.016 | 37.5–48.0 |
| Leave-one-year-out | Strictly antecedent | 3 | 12 | 0.622 | 0.560–0.690 | 0.046 | 19.1–22.7 |
| Spatial (district folds) | Strictly antecedent | 3 | 5 | 0.632 | 0.622–0.656 | 0.013 | 20.1–23.0 |

The prespecified temporal-test AUC of 0.693 sits in the top quartile of the
leave-one-year-out range. The cutpoint is far more stable than the
discrimination: 45.4 mm was selected in all twelve year-holdouts.

## Table 5. Prespecified sensitivity analyses (concurrent exposure)

| Variant | Selected window | Threshold (mm) | Test cases | Test controls | Development AUC | Test AUC | Sensitivity | Specificity |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Primary (`conf_date >= 0.78`) | 5 | 45.4 | 642 | 2,480 | 0.642 | 0.693 | 0.509 | 0.764 |
| All dated, rain/unknown trigger | 5 | 51.6 | 734 | 2,868 | 0.644 | 0.689 | 0.456 | 0.797 |
| `conf_date >= 0.80` | 5 | 45.4 | 487 | 1,865 | 0.644 | 0.686 | 0.509 | 0.745 |
| Event date −1 day | 3 | 20.0 | 644 | 2,478 | 0.626 | 0.664 | 0.556 | 0.689 |
| Event date +1 day | 5 | 47.1 | 641 | 2,500 | 0.640 | 0.692 | 0.499 | 0.768 |
| Include known non-rainfall triggers | 5 | 46.5 | 782 | 3,075 | 0.630 | 0.679 | 0.469 | 0.779 |
| Exclude road obstructions | 5 | 54.4 | 493 | 1,928 | 0.640 | 0.690 | 0.416 | 0.828 |
| Balanced source panel | 5 | 51.6 | 521 | 1,986 | 0.646 | 0.696 | 0.449 | 0.820 |
| Strict matched sets | 3 | 31.6 | 446 | 1,933 | 0.637 | 0.683 | 0.437 | 0.816 |

Test AUC exceeds development AUC in every design (+0.030 to +0.053), including
the balanced source panel and strict matched sets. Publisher turnover and
control reuse therefore do not explain the gap; see manuscript §3.4.

## Table 6. Season-stratified results (concurrent exposure, 5-day window)

| Season | Development cases/controls | Test cases/controls | Threshold (mm) | Development AUC | Test AUC | Sensitivity | Specificity |
|---|---:|---:|---:|---:|---:|---:|---:|
| Monsoon (Jun–Sep) | 704 / 2,883 | 489 / 1,722 | 45.4 | 0.627 | 0.687 | 0.599 | 0.671 |
| Non-monsoon | 168 / 833 | 153 / 758 | 1.5 | 0.699 | 0.718 | 0.673 | 0.598 |

The headline cutpoint is a monsoon quantity. Outside the monsoon the optimum is
an order of magnitude lower, because in a dry month any rainfall separates event
days from non-event days. A single year-round national cutpoint is not
defensible.

## Table 7. Matching diagnostics

| Quantity | Value |
|---|---:|
| Matched sets (case-days) | 1,514 |
| Cases with no eligible control | 192 (12.7%) |
| Controls per case: 5 / 4 / 3 / 2 / 1 / 0 | 1,150 / 54 / 37 / 38 / 43 / 192 |
| Control rows | 6,196 |
| Distinct control district-days | 4,948 |
| Control district-days used more than once | 800 |
| Control rows repeating a district-day | 1,248 (20.1%) |
| Maximum reuse of one control district-day | 8 |

Machine-readable values are in `data/outputs/rainfall_threshold_metrics.csv`,
`rainfall_sensitivity_summary.csv`, `rainfall_conditional_models.csv`,
`rainfall_resampled_validation.csv`, `rainfall_season_stratified.csv` and
`rainfall_matching_diagnostics.json`.
