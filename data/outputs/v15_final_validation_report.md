# v1.5 final locked validation

**Decision:** retain candidate status

**Candidate:** `nepal_landslide_inventory_v1.5.0_candidate_20261003`

## Results

| Metric | Weighted estimate | 95% CI | Decisive n | Unclear / N.A. |
|---|---:|---:|---:|---:|
| event existence precision | 0.958 | 0.923-0.986 | 150 | 0 |
| usable record precision | 0.570 | 0.493-0.650 | 139 | 11 |
| single event accuracy | 0.822 | 0.762-0.881 | 142 | 2 |
| district accuracy | 0.910 | 0.865-0.953 | 142 | 2 |
| date accuracy | 0.753 | 0.678-0.823 | 131 | 13 |
| municipality accuracy | 0.859 | 0.783-0.923 | 80 | 2 |
| event type accuracy | 0.893 | 0.843-0.937 | 144 | 0 |
| hazard type accuracy | 0.902 | 0.853-0.944 | 144 | 0 |
| deaths exact accuracy | 0.867 | 0.813-0.916 | 144 | 0 |
| duplicate merge accuracy | 0.942 | 0.826-1.000 | 16 | 0 |

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
