# Manuscript submission checklist — v0.4.0

## Required headline numbers

- [x] 3,114 canonical events
- [x] Study period: 2015-03-07 to 2026-08-09
- [x] 76 districts
- [x] 17 representative sources
- [x] 603 road-obstruction records
- [x] Human-labelled v7 precision: 0.626 (95% CI 0.552–0.701)
- [x] Human-labelled v7 recall: 0.759 (95% CI 0.682–0.843)
- [x] Human-labelled v7 F1: 0.686 (95% CI 0.624–0.750)
- [x] District exact accuracy / coverage: 0.828 / 0.922 (n=127)
- [x] Event-date exact accuracy / coverage: 0.824 / 0.976 (n=83)

## Required caveats

- [x] State that the inventory is media-derived, not a complete census.
- [x] State that v7 is the first human-labelled locked evaluation.
- [x] Identify v6 metrics as model-labelled historical diagnostics.
- [x] State that 88 reviewed e-paper articles were added before v0.4.0.
- [x] State that e-paper issues were evidence containers, not events.
- [x] Report blind 120-row inter-rater headline agreement 0.850 and kappa 0.656.
- [x] Report granularity kappa 0.706 and lower hazard-type kappa 0.544.
- [x] State that blocked supplementary sources (APF, DRR Portal, ReliefWeb,
  MediaCloud, DesInventar) were not included in the canonical release.

## Files to archive or cite

- `data/releases/nepal_landslide_inventory_v0.4.0_v6_20260810/`
- `docs/MANUSCRIPT_DRAFT_V04.md`
- `docs/MANUSCRIPT_RESULTS_V04.md`
- `data/outputs/canonical_events_final.csv`
- `data/outputs/locked_test_set_v7_score.json`
- `data/outputs/locked_test_set_v7_labels_final.csv`
- `data/outputs/locked_test_set_v7_second_annotator_COMPLETED_HUMAN.csv`
- `data/outputs/locked_test_set_v7_interannotator_agreement.json`
- `data/outputs/external_records.csv`

## Version control

- Release ID: `nepal_landslide_inventory_v0.4.0_v6_20260810`
- Bundle lock: recorded in `release_manifest.json`
- Do not relabel v6 or change frozen labels/predictions.
- Do not relabel or tune against spent locked v7.
