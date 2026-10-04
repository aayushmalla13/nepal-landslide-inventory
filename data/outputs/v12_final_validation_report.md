# v1.2 final locked validation

**Decision:** retain candidate status

**Candidate:** `nepal_landslide_inventory_v1.2.0_candidate_20260929`

## Results

| Metric | Weighted estimate | 95% CI | Decisive n | Unclear / N.A. |
|---|---:|---:|---:|---:|
| event existence precision | 0.944 | 0.905-0.979 | 148 | 2 |
| usable record precision | 0.640 | 0.557-0.721 | 133 | 17 |
| single event accuracy | 0.942 | 0.901-0.977 | 134 | 6 |
| district accuracy | 0.916 | 0.868-0.960 | 138 | 2 |
| date accuracy | 0.812 | 0.742-0.881 | 127 | 13 |
| municipality accuracy | 0.962 | 0.921-1.000 | 85 | 2 |
| event type accuracy | 0.886 | 0.835-0.933 | 140 | 0 |
| hazard type accuracy | 0.933 | 0.890-0.970 | 139 | 1 |
| deaths exact accuracy | 0.862 | 0.807-0.912 | 140 | 0 |
| duplicate merge accuracy | 0.917 | 0.796-1.000 | 25 | 1 |

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
