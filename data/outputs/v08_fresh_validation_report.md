# v0.8 fresh locked validation

**Decision:** retain candidate status

**Candidate:** `nepal_landslide_inventory_v0.8.0_candidate_20260923`

## Results

| Metric | Weighted estimate | 95% CI | Decisive n | Unclear / N.A. |
|---|---:|---:|---:|---:|
| event existence precision | 0.889 | 0.837-0.937 | 147 | 3 |
| usable record precision | 0.463 | 0.381-0.545 | 139 | 11 |
| single event accuracy | 0.744 | 0.671-0.814 | 128 | 4 |
| district accuracy | 0.865 | 0.805-0.921 | 129 | 3 |
| date accuracy | 0.792 | 0.714-0.862 | 113 | 19 |
| municipality accuracy | 0.926 | 0.866-0.975 | 79 | 2 |
| event type accuracy | 0.685 | 0.609-0.762 | 132 | 0 |
| hazard type accuracy | 0.927 | 0.879-0.971 | 131 | 1 |
| deaths exact accuracy | 0.855 | 0.793-0.911 | 130 | 2 |
| duplicate merge accuracy | 0.700 | 0.479-0.893 | 29 | 0 |

## Prespecified decision checks

| Check | Pass |
|---|---:|
| event existence precision | no |
| usable record precision | no |
| single event accuracy | no |
| district accuracy | yes |
| date accuracy | no |
| event existence unclear fraction | yes |

The decision rule and thresholds were frozen in the draw manifest before labels existed.
Estimates apply to the eligible frame after excluding all previously reviewed events and article evidence.
