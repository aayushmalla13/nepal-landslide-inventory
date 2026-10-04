# Post-correction candidate validation

Inventory: `nepal_landslide_inventory_v0.7.0_candidate_20260916`

## Fresh probability sample

| Metric | Weighted estimate | 95% stratified-bootstrap CI | Decisive n | Unclear / N.A. |
|---|---:|---:|---:|---:|
| event existence precision | 0.833 | 0.774-0.888 | 149 | 1 |
| usable record precision | 0.358 | 0.284-0.437 | 146 | 4 |
| single event accuracy | 0.704 | 0.623-0.779 | 126 | 0 |
| district accuracy | 0.799 | 0.731-0.864 | 121 | 5 |
| date accuracy | 0.743 | 0.658-0.824 | 115 | 11 |
| municipality accuracy | 0.898 | 0.837-0.956 | 64 | 1 |
| event type accuracy | 0.683 | 0.616-0.752 | 125 | 1 |
| hazard type accuracy | 0.844 | 0.780-0.902 | 119 | 7 |
| deaths exact accuracy | 0.878 | 0.817-0.935 | 115 | 11 |
| duplicate merge accuracy | 0.854 | 0.739-0.946 | 34 | 0 |

## Correction challenge

| Layer | Targeted pass | Decisive n | Unclear / N.A. |
|---|---:|---:|---:|
| identity add | 0.952 | 21 | 7 |
| identity merge | 1.000 | 5 | 0 |
| structured attribute correction | 1.000 | 9 | 0 |
| true value correction | 1.000 | 8 | 0 |
| **overall** | **0.977** | **43** | **7** |

Fresh estimates apply only to the untouched 2,723-event eligible frame.
The targeted correction challenge is not an overall precision estimate.
No numeric promotion threshold was prespecified; results must not be judged by a post hoc cutoff.
