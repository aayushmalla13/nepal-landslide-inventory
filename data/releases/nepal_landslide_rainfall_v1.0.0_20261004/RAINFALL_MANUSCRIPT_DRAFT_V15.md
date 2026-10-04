# Media-reported landslide occurrence and antecedent rainfall in Nepal: a validated event-detection inventory and district-day analysis, 2015-2026

**Generated manuscript core - do not edit numeric results by hand.** Rebuild with
`PYTHONPATH=src python3 scripts/build_v15_rainfall_manuscript.py`.

**Authors:** [complete before submission]

**Analysis version:** 1.0.0 (2026-10-04). Inventory release
`nepal_landslide_inventory_v1.5.0_event_detection_validated_20261004`; rainfall release
`nepal_landslide_rainfall_v1.0.0_20261004`.

## Abstract

We assembled 2,122 media-derived landslide event records across
74 Nepal districts from 2015-03-07 to
2026-08-09. A fresh 150-row stratified probability audit estimated
event-existence precision at 0.958 (95% CI
0.923-
0.986) and district accuracy at
0.910; exact-date accuracy was
0.753, requiring explicit temporal sensitivity analysis.
We linked 1,278 district-day
cases to 5,460 controls
matched on district, calendar month, and year. Windows and thresholds were
selected through 2022 and tested without retuning from 2023 onward.
The primary concurrent analysis selected R3 at
31.7 mm and achieved test AUC 0.686
(95% CI 0.647-0.722), sensitivity
0.473, and specificity 0.789.
The strictly antecedent co-primary selected R3 at
21.0 mm with test AUC 0.646.
Leave-one-year-out AUC had median 0.663 and range
0.576-0.711. The threshold changed under deliberate
date shifts, so it is an empirical association measure rather than an
operational warning threshold. Independent BIPAD comparison showed Tier-A
overlap 0.220 versus
0.093 expected by date permutation
(chance-corrected 0.128,
empirical p=0.0099).

**Keywords:** landslide inventory; media mining; Nepal; CHIRPS; antecedent rainfall; matched case-control; external agreement

## 1. Study design

The inventory is a source-bounded record of media-detected events, not a complete
census. The primary unit for rainfall analysis is the district-day. Multiple
records in the same district on the same date are collapsed to one case-day.
Controls are sampled in the same district, calendar month, and year and must be
at least seven days from any reported event. Five controls are requested per case.
Concurrent rainfall windows include the reported event day; strictly antecedent
windows end the day before it. Development ends on 2022-12-31.

## 2. Inventory validation

| Metric | Estimate | 95% CI | Prespecified decision |
|---|---:|---:|---|
| Event-existence precision | 0.958 | 0.923-0.986 | pass |
| Usable-record precision | 0.570 | 0.493-0.650 | fail |
| Single-event accuracy | 0.822 | 0.762-0.881 | fail |
| District accuracy | 0.910 | 0.865-0.953 | pass |
| Exact-date accuracy | 0.753 | 0.678-0.823 | fail |

The validated claim is therefore high-precision event detection. The data do
not support an unqualified high-precision full-record or exact-date claim.

## 3. Rainfall results

The primary development sample contained 712 case-days and 3,152 matched controls. The temporal test set contained 566 case-days and 2,308 controls. The development-selected 31.7 mm threshold was carried forward unchanged. Test AUC was 0.686.

| Exposure | Window | Development threshold (95% CI), mm | Test AUC (95% CI) | Sensitivity | Specificity |
|---|---:|---:|---:|---:|---:|
| Concurrent, includes event day | R3 | 31.7 (15.2-38.2) | 0.686 (0.647-0.722) | 0.473 | 0.789 |
| Strictly antecedent | R3 | 21.0 (14.7-29.1) | 0.646 (0.604-0.682) | 0.557 | 0.669 |

The primary matched-set conditional model gave an odds ratio of 1.248 per 10 mm.
There were 131 cases
without an eligible control (10.3%)
and 19.9% of control rows
repeated a district-day; the strict matched-set variant is reported separately.

## 4. Date sensitivity

| Variant | Window | Threshold (mm) | Test AUC | Sensitivity | Specificity |
|---|---:|---:|---:|---:|---:|
| `primary_conf_ge_0.78` | R3 | 31.7 | 0.686 | 0.473 | 0.789 |
| `high_conf_ge_0.80` | R3 | 31.3 | 0.676 | 0.489 | 0.760 |
| `primary_date_minus_1d` | R3 | 21.0 | 0.649 | 0.557 | 0.666 |
| `primary_date_plus_1d` | R5 | 46.9 | 0.673 | 0.521 | 0.704 |
| `primary_date_minus_3d` | R3 | 15.4 | 0.621 | 0.592 | 0.560 |
| `primary_date_plus_3d` | R7 | 87.9 | 0.667 | 0.391 | 0.805 |

The confidence >=0.90 variant contained only 17 cases and was too sparse for a stable temporal estimate.

## 5. Integrity and external agreement

The refreshed integrity audit examined 1,278 case-days
and found 0 logically impossible rows.
Only 3 case-days (0.23%)
were potentially excludable contamination. Removing them changed the R3 AUC by
+0.0000 and the
cutpoint by +0.0 mm.

The common BIPAD comparison contained 2,119
news events and 4,095 harmonized BIPAD clusters.
District-year counts correlated at rho=0.355,
whereas district-month counts correlated at rho=-0.075.
BIPAD is incomplete and not ground truth; these are agreement measures, not
precision or recall.

## 6. Limitations and defensible claims

The inventory is affected by publisher turnover, geographic and severity-related
reporting bias, and imperfect exact dates and event granularity. June-September
accounts for 81.1% of records, and the three largest publishers account for 47.0%.
Daily associations are sensitive to date displacement, and district-mean CHIRPS
smooths localized rainfall extremes. Absolute risk, calibration, completeness,
and operational warning performance are not identifiable from this design.

The paper may claim a validated high-precision web-derived event-detection
inventory and a reproducible association between reported district-days and
antecedent rainfall. It must not claim a complete landslide census, validated
full-record precision, exact daily timing, or an operational warning threshold.

## Data and code availability

Canonical inventory: `nepal_landslide_inventory_v1.5.0_event_detection_validated_20261004` (SHA-256
`313745c27218be7989764cc9614b71cc69a9549ff05c483247a6c89bd276ae19`). External agreement:
`nepal_landslide_external_validation_v0.2.0_20261004`. Rainfall analysis:
`nepal_landslide_rainfall_v1.0.0_20261004`. Full article text should not be
redistributed; source URLs, derived fields, code, manifests, and checksums are
included for reproducibility.

