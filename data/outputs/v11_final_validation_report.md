# v1.1 final locked validation

**Decision:** retain candidate status

**Candidate:** `nepal_landslide_inventory_v1.1.0_candidate_20260928`

## Results

| Metric | Weighted estimate | 95% CI | Decisive n | Unclear / N.A. |
|---|---:|---:|---:|---:|
| event existence precision | 0.958 | 0.923-0.986 | 148 | 2 |
| usable record precision | 0.416 | 0.337-0.497 | 137 | 13 |
| single event accuracy | 0.762 | 0.691-0.829 | 134 | 8 |
| district accuracy | 0.849 | 0.789-0.903 | 138 | 4 |
| date accuracy | 0.708 | 0.627-0.788 | 119 | 23 |
| municipality accuracy | 0.898 | 0.824-0.958 | 69 | 4 |
| event type accuracy | 0.439 | 0.360-0.515 | 142 | 0 |
| hazard type accuracy | 0.947 | 0.908-0.978 | 142 | 0 |
| deaths exact accuracy | 0.891 | 0.838-0.940 | 137 | 5 |
| duplicate merge accuracy | 0.611 | 0.407-0.812 | 21 | 0 |

## Prespecified decision checks

| Check | Pass |
|---|---:|
| event existence precision | yes |
| usable record precision | no |
| single event accuracy | no |
| district accuracy | no |
| date accuracy | no |
| event existence unclear fraction | yes |

The decision rule and thresholds were frozen in the draw manifest before labels existed.
Estimates apply to the eligible frame after excluding all previously reviewed events and article evidence.
