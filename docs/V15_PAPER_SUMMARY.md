# v1.5 paper summary

**Generated file - do not edit by hand.** Rebuild with
`PYTHONPATH=src python3 scripts/build_v15_paper_summary.py`.

## Authoritative dataset

- Release: `nepal_landslide_inventory_v1.5.0_event_detection_validated_20261004`
- Status: `validated_event_detection_only`
- Canonical SHA-256: `313745c27218be7989764cc9614b71cc69a9549ff05c483247a6c89bd276ae19`
- Events: 2,122
- Study period: 2015-03-07 to 2026-08-09
- Districts represented: 74 of 77
- Representative sources: 16

## Locked validation

The fresh audit used 150 rows drawn from a 568-event eligible frame with
stratified probability weights. Confidence intervals are stratified-bootstrap
95% intervals. The audit validates event detection, not the complete record.

| Metric | Estimate | 95% CI | Decision |
|---|---:|---:|---|
| Event-existence precision | 0.958 | 0.923-0.986 | pass |
| Usable-record precision | 0.570 | 0.493-0.650 | fail |
| Single-event accuracy | 0.822 | 0.762-0.881 | fail |
| District accuracy | 0.910 | 0.865-0.953 | pass |
| Exact-date accuracy | 0.753 | 0.678-0.823 | fail |
| Municipality accuracy | 0.859 | 0.783-0.923 | descriptive |
| Event-type accuracy | 0.893 | 0.843-0.937 | descriptive |
| Hazard-type accuracy | 0.902 | 0.853-0.944 | descriptive |
| Deaths exact accuracy | 0.867 | 0.813-0.916 | descriptive |
| Duplicate-merge accuracy | 0.942 | 0.826-1.000 | descriptive |

## Inventory composition

June-September contains 1,722 events (81.1%). The three largest representative
sources account for 47.0% of records. These
figures describe the media-derived inventory and must not be interpreted as
population incidence without accounting for reporting intensity.

### Events by year

| Year | Events |
|---:|---:|
| 2015 | 77 |
| 2016 | 106 |
| 2017 | 93 |
| 2018 | 124 |
| 2019 | 85 |
| 2020 | 229 |
| 2021 | 191 |
| 2022 | 214 |
| 2023 | 190 |
| 2024 | 427 |
| 2025 | 264 |
| 2026 | 122 |

### Events by representative source

| Source | Events | Share |
|---|---:|---:|
| setopati | 447 | 21.1% |
| myrepublica | 288 | 13.6% |
| nagarik | 262 | 12.3% |
| nepalpress | 253 | 11.9% |
| himalayan-times | 225 | 10.6% |
| ujyaalo | 207 | 9.8% |
| online-khabar | 128 | 6.0% |
| deshsanchar | 84 | 4.0% |
| onlinekhabar-en | 84 | 4.0% |
| kathmandu-post | 42 | 2.0% |
| rajdhani | 30 | 1.4% |
| ratopati | 25 | 1.2% |
| nepalpress-en | 24 | 1.1% |
| rising-nepal | 18 | 0.8% |
| ekantipur | 4 | 0.2% |
| nepali-times | 1 | 0.0% |

## Claim boundary

Supported primary claim: a validated high-precision web-derived landslide
event-detection inventory for Nepal. District assignment also passed its
prespecified threshold.

Not supported: a complete census, a high-precision full-record inventory,
or exact-date accuracy sufficient for unqualified daily causal analysis.
Usable-record precision, single-event accuracy, and exact-date accuracy failed
their prespecified thresholds.

## Downstream-analysis status

- BIPAD comparison: complete in `nepal_landslide_external_validation_v0.2.0_20261004`.
- Rainfall analysis: complete in `nepal_landslide_rainfall_v1.0.0_20261004`.
- Existing v0.4 manuscript files are historical and must not supply headline counts.
- Date-dependent analysis must include high-confidence and date-window sensitivity checks.
