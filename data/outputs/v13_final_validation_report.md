# v1.3 final locked validation

**Decision:** retain candidate status

**Candidate:** `nepal_landslide_inventory_v1.3.0_candidate_20260930`

## Results

| Metric | Weighted estimate | 95% CI | Decisive n | Unclear / N.A. |
|---|---:|---:|---:|---:|
| event existence precision | 0.951 | 0.915-0.980 | 150 | 0 |
| usable record precision | 0.604 | 0.526-0.682 | 143 | 7 |
| single event accuracy | 0.854 | 0.791-0.909 | 139 | 4 |
| district accuracy | 0.941 | 0.898-0.977 | 141 | 2 |
| date accuracy | 0.778 | 0.708-0.844 | 134 | 9 |
| municipality accuracy | 0.893 | 0.830-0.952 | 96 | 1 |
| event type accuracy | 0.896 | 0.844-0.943 | 143 | 0 |
| hazard type accuracy | 0.967 | 0.938-0.993 | 143 | 0 |
| deaths exact accuracy | 0.809 | 0.753-0.864 | 142 | 1 |
| duplicate merge accuracy | 1.000 | 1.000-1.000 | 21 | 1 |

## Prespecified decision checks

| Check | Pass |
|---|---:|
| event existence precision | yes |
| usable record precision | no |
| single event accuracy | yes |
| district accuracy | yes |
| date accuracy | no |
| event existence unclear fraction | yes |

The decision rule and thresholds were frozen in the draw manifest before labels existed.
Estimates apply to the eligible frame after excluding all previously reviewed events and article evidence.
