# Manuscript package — Nepal landslide inventory v0.4.0

## Results

The v0.4.0 release contains 3,114 canonical landslide-related events derived
from 10,203 collected articles covering 7 March 2015 through 9 August 2026.
Events from 76 of Nepal's 77 districts are represented across 17 news sources. The release
contains 603 road-obstruction subtype records and no multi-event aggregates
after deduplication.

Historical e-paper recovery contributed 736 issue-level records. Manual review
identified 89 event-specific article candidates; 88 articles were successfully
ingested and processed through date normalization, language routing, extraction,
specificity filtering, location checks, deduplication, and event typing. Issues
were treated as evidence containers, not events.

## Validation

The independently drawn, human-labelled locked-v7 test set produced
population-weighted article-level headline-classification precision of 0.626
(95% CI 0.552–0.701), recall of 0.759 (0.682–0.843), and F1 of 0.686
(0.624–0.750). District exact accuracy was 0.828 with 0.922 nonblank coverage
among 127 truth-available rows. Event-date exact accuracy was 0.824 with 0.976
nonblank coverage among 83 truth-available rows.

Locked v7 was scored once and is now spent. It is the project's first
human-labelled locked evaluation. Earlier locked-v6 metrics were based on
model-generated labels and are historical diagnostics rather than primary
validation. A second independent human annotator labelled a blind, stratified
120-row subset. Headline agreement was 0.850 (Cohen's kappa 0.656), granularity
agreement was 0.783 (kappa 0.706), and hazard-type agreement was 0.717 (kappa
0.544). Where both raters supplied values, district agreement was 0.981 and
event-date agreement was 0.941. The frozen v7 labels were not adjudicated or
changed after this comparison.

## Methods/provenance note

The canonical inventory is a media-derived event inventory, not a complete
census of all landslides. External government, scientific, road, archive, and
e-paper records were collected for discovery and triangulation. They were not
silently merged into the canonical inventory. Five reviewed corrections were
applied as release-quality controls and did not alter the frozen v6 labels or
predictions.

## Limitations

Coverage varies by source, language, geography, event severity, and year. Some
supplementary sources remained inaccessible or required credentials/files and
were excluded from v0.4.0, including APF, DRR Portal, ReliefWeb, MediaCloud, and
DesInventar. Automated secondary-event extraction was evaluated separately and
remains excluded from the canonical inventory and all released analyses. The inventory should therefore be interpreted as a
reproducible, source-bounded media record rather than a complete hazard census.

## Release provenance

- Release: `nepal_landslide_inventory_v0.4.0_v6_20260810`
- Bundle lock: recorded in `data/releases/nepal_landslide_inventory_v0.4.0_v6_20260810/release_manifest.json`
- Canonical CSV: `data/releases/nepal_landslide_inventory_v0.4.0_v6_20260810/canonical_events_final.csv`
- Primary validation metrics: `data/outputs/locked_test_set_v7_score.json`
- Inter-rater agreement: `data/outputs/locked_test_set_v7_interannotator_agreement.json`
- Historical model-labelled validation: `data/releases/nepal_landslide_inventory_v0.4.0_v6_20260810/locked_test_set_v6_manuscript_metrics.csv`
