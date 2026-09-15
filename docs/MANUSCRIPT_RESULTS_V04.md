# Manuscript results — v0.4.0

## Paste-ready Results text

The v0.4.0 release contains 3,114 canonical landslide-related events
identified from 10,203 collected articles during 7 March 2015–9 August 2026.
The inventory represents 76 of Nepal's 77 districts and 17 news
sources. Of the canonical records, 603 are typed as road-obstruction records;
no records are classified as multi-event aggregates after deduplication.
Historical e-paper recovery contributed 736 issue-level records. Review of
those issues identified 89 event-specific article candidates, of which 88 were
successfully ingested and processed through the standard pipeline. E-paper
issues were treated as evidence containers rather than events.

On the independently drawn, human-labelled locked-v7 test set,
population-weighted article-level headline classification achieved a precision
of 0.626 (95% CI 0.552–0.701), recall of 0.759 (0.682–0.843), and F1 of 0.686
(0.624–0.750). Among true headline articles, district exact accuracy was 0.828
with 0.922 nonblank coverage (n=127), and event-date exact accuracy was 0.824
with 0.976 nonblank coverage (n=83). Locked v7 was scored once and is now spent.
The earlier locked-v6 estimates used model-generated labels and are retained
only as a historical diagnostic.

A second independent human annotator labelled a blind, stratified 120-row
subset. Headline agreement was 0.850 (Cohen's kappa 0.656), granularity
agreement was 0.783 (kappa 0.706), and hazard-type agreement was 0.717 (kappa
0.544). Exact district and event-date agreement, where both raters supplied a
value, was 0.981 (52/53) and 0.941 (32/34), respectively. These are
pre-adjudication results; locked-v7 labels were not changed after comparison.

## Inventory summary

| Measure | Value |
|---|---:|
| Canonical events | 3,114 |
| Study period | 2015-03-07 to 2026-08-09 |
| Districts represented | 76 |
| Representative sources | 17 |
| Road-obstruction subtype | 603 |
| Non-single records | 0 |

## Primary locked evaluation (v7)

These metrics are population-weighted article-level headline-classification
results from the independently drawn, human-labelled frozen v7 test set.

| Measure | Estimate | 95% CI |
|---|---:|---:|
| Precision | 0.626 | 0.552–0.701 |
| Recall | 0.759 | 0.682–0.843 |
| F1 | 0.686 | 0.624–0.750 |
| District exact accuracy | 0.828 | — |
| District coverage | 0.922 | — |
| Event-date exact accuracy | 0.824 | — |
| Event-date coverage | 0.976 | — |

District and event-date accuracy are reportable from 127 and 83 truth-available
rows, respectively. Inter-rater reliability was measured on a separate blind
120-row subset of locked v7.

## Release provenance

- Release: `nepal_landslide_inventory_v0.4.0_v6_20260810`
- Bundle lock: `3ed1d90c21e4bc8bf5efad1e56f163e80d40c11c1b317251787417f3e574bcb3`
  (corrected 2026-08-14 to match `release_manifest.json`; all 12 file digests
  re-verified, bundle unmodified)
- Canonical CSV SHA-256: see the release manifest
- External e-paper articles added before this release: 88
- Primary validation: `data/outputs/locked_test_set_v7_score.json`
- Inter-rater agreement: `data/outputs/locked_test_set_v7_interannotator_agreement.json`
