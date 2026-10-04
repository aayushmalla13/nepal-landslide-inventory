# External Inventory Match Report

Generated at: 2026-09-23T15:12:28+00:00
Common comparison cutoff: 2026-08-08

## Inputs
- Frozen canonical CSV: data/releases/nepal_landslide_inventory_v0.8.0_candidate_20260923/canonical_events_final.csv
- Frozen canonical CSV SHA-256: 0822515b56693af22daf2e3cc6e63b178eb41fefa46a8b607a47d6da9efdcd07
- Normalized BIPAD input snapshot: data/outputs/external_bipad_input_snapshot.csv
- Normalized BIPAD snapshot SHA-256: 0f8ffe6210e78560a23d4b07fee5c61ccfa73e7ca389f05415553d89ed81f2dc
- Canonical news events: 2868
- BIPAD rows in the study window: 5345
- Harmonized BIPAD incident clusters: 4095
- BIPAD collapse ratio: 1.305

## Candidate overlap
- Tier A candidates: 449
- Tier B candidates: 337
- Tier C candidates: 3523
- BIPAD clusters with a strong A/B match: 579
- BIPAD clusters with only a weak Tier-C candidate: 1115
- BIPAD clusters with no candidate: 2401
- Targeted search seeds: 3516
- Canonical news events without an A/B match: 2265

## COOLR
- Scientific inventory groups: 1
- Mapped polygon features: 796
- COOLR polygons are spatial evidence, not independent incident counts.

## Interpretation
BIPAD is an incomplete administrative observation system, not ground truth. The outputs report overlap and candidate links—not precision or recall. Tier C is intentionally treated as a weak lead because district-level ±7-day overlap is common during the monsoon.
