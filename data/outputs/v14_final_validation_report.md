# v1.4 final locked validation

**Decision:** retain candidate status

**Candidate:** `nepal_landslide_inventory_v1.4.0_candidate_20261002`

## Results

| Metric | Weighted estimate | 95% CI | Decisive n | Unclear / N.A. |
|---|---:|---:|---:|---:|
| event existence precision | 0.910 | 0.868-0.950 | 150 | 0 |
| usable record precision | 0.563 | 0.481-0.643 | 141 | 9 |
| single event accuracy | 0.803 | 0.733-0.869 | 131 | 6 |
| district accuracy | 0.921 | 0.872-0.962 | 135 | 2 |
| date accuracy | 0.786 | 0.714-0.853 | 125 | 12 |
| municipality accuracy | 0.868 | 0.798-0.932 | 90 | 0 |
| event type accuracy | 0.903 | 0.857-0.948 | 137 | 0 |
| hazard type accuracy | 0.869 | 0.813-0.921 | 134 | 3 |
| deaths exact accuracy | 0.788 | 0.726-0.851 | 137 | 0 |
| duplicate merge accuracy | 0.897 | 0.794-1.000 | 16 | 1 |

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
