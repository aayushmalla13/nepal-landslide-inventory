# v0.9 final locked validation

**Decision:** retain candidate status

**Candidate:** `nepal_landslide_inventory_v0.9.0_candidate_20260924`

## Results

| Metric | Weighted estimate | 95% CI | Decisive n | Unclear / N.A. |
|---|---:|---:|---:|---:|
| event existence precision | 0.811 | 0.752-0.869 | 150 | 0 |
| usable record precision | 0.370 | 0.293-0.453 | 141 | 9 |
| single event accuracy | 0.678 | 0.594-0.762 | 120 | 4 |
| district accuracy | 0.891 | 0.833-0.944 | 122 | 2 |
| date accuracy | 0.748 | 0.658-0.832 | 105 | 19 |
| municipality accuracy | 0.921 | 0.850-0.979 | 60 | 0 |
| event type accuracy | 0.781 | 0.712-0.847 | 124 | 0 |
| hazard type accuracy | 0.869 | 0.808-0.925 | 122 | 2 |
| deaths exact accuracy | 0.839 | 0.774-0.899 | 123 | 1 |
| duplicate merge accuracy | 0.605 | 0.373-0.830 | 26 | 2 |

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
