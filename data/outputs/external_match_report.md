# External Inventory Match Report

Generated at: 2026-10-04T08:20:38+00:00
Common comparison cutoff: 2026-08-08

## Inputs
- Frozen canonical CSV: data/releases/nepal_landslide_inventory_v1.5.0_event_detection_validated_20261004/canonical_events_final.csv
- Frozen canonical CSV SHA-256: 313745c27218be7989764cc9614b71cc69a9549ff05c483247a6c89bd276ae19
- Normalized BIPAD input snapshot: data/outputs/external_bipad_input_snapshot.csv
- Normalized BIPAD snapshot SHA-256: 0f8ffe6210e78560a23d4b07fee5c61ccfa73e7ca389f05415553d89ed81f2dc
- Canonical news events: 2119
- BIPAD rows in the study window: 5345
- Harmonized BIPAD incident clusters: 4095
- BIPAD collapse ratio: 1.305

## Candidate overlap
- Tier A candidates: 482
- Tier B candidates: 360
- Tier C candidates: 2839
- BIPAD clusters with a strong A/B match: 562
- BIPAD clusters with only a weak Tier-C candidate: 882
- BIPAD clusters with no candidate: 2651
- Targeted search seeds: 3533
- Canonical news events without an A/B match: 1456

## COOLR
- Scientific inventory groups: 1
- Mapped polygon features: 796
- COOLR polygons are spatial evidence, not independent incident counts.

## Interpretation
BIPAD is an incomplete administrative observation system, not ground truth. The outputs report overlap and candidate links—not precision or recall. Tier C is intentionally treated as a weak lead because district-level ±7-day overlap is common during the monsoon.
