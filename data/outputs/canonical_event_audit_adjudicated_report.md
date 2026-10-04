# Canonical event-level audit

Inventory: `nepal_landslide_inventory_v0.6.0_v7_20260915`
Reviewed rows: 150

| Metric | Weighted estimate | 95% stratified-bootstrap CI | Decisive n | Unclear / N.A. |
|---|---:|---:|---:|---:|
| event existence precision | 0.860 | 0.804-0.912 | 150 | 0 |
| usable record precision | 0.402 | 0.319-0.489 | 143 | 7 |
| single event accuracy | 0.754 | 0.675-0.825 | 131 | 1 |
| district accuracy | 0.845 | 0.779-0.903 | 127 | 5 |
| date accuracy | 0.762 | 0.684-0.836 | 121 | 11 |
| municipality accuracy | 0.976 | 0.928-1.000 | 64 | 1 |
| event type accuracy | 0.672 | 0.610-0.734 | 132 | 0 |
| hazard type accuracy | 0.931 | 0.890-0.965 | 131 | 1 |
| deaths exact accuracy | 0.786 | 0.721-0.849 | 128 | 4 |
| duplicate merge accuracy | 0.622 | 0.439-0.794 | 38 | 1 |

Point estimates exclude unclear labels; their counts are shown explicitly.
The audit evaluates the frozen release and does not silently modify it.
