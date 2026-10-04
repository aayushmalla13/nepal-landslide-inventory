# v1.0 final locked validation

**Decision:** retain candidate status

**Candidate:** `nepal_landslide_inventory_v1.0.0_candidate_20260927`

## Results

| Metric | Weighted estimate | 95% CI | Decisive n | Unclear / N.A. |
|---|---:|---:|---:|---:|
| event existence precision | 0.945 | 0.903-0.979 | 147 | 3 |
| usable record precision | 0.510 | 0.421-0.592 | 133 | 17 |
| single event accuracy | 0.821 | 0.760-0.878 | 136 | 3 |
| district accuracy | 0.873 | 0.816-0.925 | 137 | 2 |
| date accuracy | 0.789 | 0.714-0.858 | 124 | 15 |
| municipality accuracy | 0.892 | 0.821-0.952 | 85 | 0 |
| event type accuracy | 0.509 | 0.431-0.587 | 139 | 0 |
| hazard type accuracy | 0.978 | 0.949-1.000 | 138 | 1 |
| deaths exact accuracy | 0.859 | 0.800-0.913 | 139 | 0 |
| duplicate merge accuracy | 0.900 | 0.762-1.000 | 18 | 1 |

## Prespecified decision checks

| Check | Pass |
|---|---:|
| event existence precision | yes |
| usable record precision | no |
| single event accuracy | no |
| district accuracy | yes |
| date accuracy | no |
| event existence unclear fraction | yes |

The decision rule and thresholds were frozen in the draw manifest before labels existed.
Estimates apply to the eligible frame after excluding all previously reviewed events and article evidence.
