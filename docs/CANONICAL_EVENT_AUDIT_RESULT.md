# Canonical event-level audit result

**Status:** complete first-human audit; independent adjudication pending.

## Frozen target

- Inventory: `nepal_landslide_inventory_v0.6.0_v7_20260915`
- Canonical population: 2,885 records
- Canonical CSV SHA-256:
  `3b335babbfcbe0b50d2aad9023e08e55a2ca6e8e0881729615df33e2c9b9d0e8`
- Stratified sample: 150 records across 24 populated language-period-event
  type-support strata
- Completed-label SHA-256:
  `c5cbedb457b999bca3a3cc2ef92e1d62b74f57ed49f8f60417395a80a4f0a5ed`

## Preliminary weighted results

| Metric | Estimate | 95% stratified-bootstrap CI | Decisive n |
|---|---:|---:|---:|
| Event existence precision | 0.874 | 0.820-0.924 | 150 |
| Usable record precision | 0.403 | 0.321-0.486 | 144 |
| Single physical event accuracy | 0.756 | 0.679-0.827 | 134 |
| District accuracy | 0.826 | 0.764-0.885 | 131 |
| Date accuracy | 0.764 | 0.684-0.840 | 120 |
| Municipality accuracy | 0.976 | 0.928-1.000 | 64 |
| Event type accuracy | 0.685 | 0.621-0.748 | 134 |
| Hazard type accuracy | 0.948 | 0.911-0.979 | 133 |
| Deaths exact accuracy | 0.802 | 0.740-0.862 | 131 |
| Duplicate-merge accuracy | 0.642 | 0.458-0.813 | 38 |

`Usable record precision` requires a real event, one physical event, the
correct district, and the correct event date. It is deliberately stricter than
article-classification precision. Six unclear records are excluded from its
point estimate and reported separately in the machine-readable score.

## Diagnostic pattern

- Event existence was 1.000 in the sampled road-obstruction and multi-article
  strata, but 0.841 among records typed as general landslides and 0.846 among
  single-article records.
- Weighted usable-record precision was similar in English-title (0.376) and
  Nepali-title (0.413) strata, so this is not only a language problem.
- District accuracy was weakest in 2023-2026 (0.705), consistent with datelines,
  road names, and nearby-district references being mistaken for event sites.
- Date accuracy was weakest in 2019-2022 (0.677), commonly because publication,
  reopening, recovery, or follow-up dates replaced failure onset.
- Multi-article records had event-existence precision 1.000 but weighted
  duplicate-merge accuracy 0.642. Several clusters combine separate failures at
  the same road corridor or during the same disaster period.
- Among 134 reviewed real events, 36 records typed as general `landslide` were
  labelled `road_obstruction`. This accounts for much of the low event-type
  accuracy but does not imply that the physical hazard was false.

## Scientific consequence

The audit supports the existence of a large real landslide-event signal, but it
does not support treating every canonical row as a correctly resolved single
physical event with exact date and district. The current inventory remains a
frozen media-derived record inventory. Its 2,885 rows must not be described as
2,885 independently verified physical failures.

Do not silently correct or overwrite v0.6.0. Before a replacement release,
obtain an independent second review and adjudicate disagreements. If the result
holds, construct a correction layer for false events, multi-event rows,
district/date errors, event-type errors, and bad duplicate merges; then issue a
new inventory version and rerun only analyses affected by the corrected case
set.

## Outputs

- `data/outputs/canonical_event_audit_COMPLETED.csv`
- `data/outputs/canonical_event_audit_score.json`
- `data/outputs/canonical_event_audit_report.md`
- `data/outputs/canonical_event_audit_manifest.json`
- `data/outputs/canonical_event_audit_weights.csv`
