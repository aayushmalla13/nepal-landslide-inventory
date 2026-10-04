# Rainfall manuscript tables

## Table 1. Primary development and temporal-test performance

| Window | Development AUC | Threshold (mm) | Threshold 95% CI | Test AUC (95% CI) | Test sensitivity | Test specificity |
|---|---:|---:|---:|---:|---:|---:|
| 1 day | 0.613 | 7.2 | 0.5–17.4 | 0.647 (0.626–0.672) | 0.430 | 0.776 |
| 3 days | 0.642 | 31.6 | 11.7–40.0 | 0.694 (0.663–0.725) | 0.449 | 0.821 |
| **5 days (selected)** | **0.642** | **45.4** | **26.8–72.1** | **0.693 (0.657–0.722)** | **0.509** | **0.764** |
| 7 days | 0.635 | 70.3 | 45.6–81.4 | 0.685 (0.649–0.715) | 0.433 | 0.793 |

The selected window is based only on development AUC. Test values for the
other windows are descriptive and were not used to change the selection.

## Table 2. Prespecified sensitivity analyses

| Variant | Selected window | Threshold (mm) | Test cases | Test controls | Test AUC | Sensitivity | Specificity |
|---|---:|---:|---:|---:|---:|---:|---:|
| Primary (`conf_date >= 0.78`) | 5 | 45.4 | 642 | 2,480 | 0.693 | 0.509 | 0.764 |
| All dated, rain/unknown trigger | 5 | 51.6 | 734 | 2,868 | 0.689 | 0.456 | 0.797 |
| `conf_date >= 0.80` | 5 | 45.4 | 487 | 1,865 | 0.686 | 0.509 | 0.745 |
| Event date −1 day | 3 | 20.0 | 644 | 2,478 | 0.664 | 0.556 | 0.689 |
| Event date +1 day | 5 | 47.1 | 641 | 2,500 | 0.692 | 0.499 | 0.768 |
| Include known non-rainfall triggers | 5 | 46.5 | 782 | 3,075 | 0.679 | 0.469 | 0.779 |
| Exclude road obstructions | 5 | 54.4 | 493 | 1,928 | 0.690 | 0.416 | 0.828 |

Machine-readable values are in
`data/outputs/rainfall_threshold_metrics.csv` and
`data/outputs/rainfall_sensitivity_summary.csv`.
