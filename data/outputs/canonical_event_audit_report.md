# Canonical event-level audit

Inventory: `nepal_landslide_inventory_v0.6.0_v7_20260915`
Reviewed rows: 150

| Metric | Weighted estimate | 95% stratified-bootstrap CI | Decisive n | Unclear / N.A. |
|---|---:|---:|---:|---:|
| event existence precision | 0.874 | 0.820-0.924 | 150 | 0 |
| usable record precision | 0.403 | 0.321-0.486 | 144 | 6 |
| single event accuracy | 0.756 | 0.679-0.827 | 134 | 0 |
| district accuracy | 0.826 | 0.764-0.885 | 131 | 3 |
| date accuracy | 0.764 | 0.684-0.840 | 120 | 14 |
| municipality accuracy | 0.976 | 0.928-1.000 | 64 | 1 |
| event type accuracy | 0.685 | 0.621-0.748 | 134 | 0 |
| hazard type accuracy | 0.948 | 0.911-0.979 | 133 | 1 |
| deaths exact accuracy | 0.802 | 0.740-0.862 | 131 | 3 |
| duplicate merge accuracy | 0.642 | 0.458-0.813 | 38 | 1 |

Point estimates exclude unclear labels; their counts are shown explicitly.
The audit evaluates the frozen release and does not silently modify it.
