# Post-correction remediation queue

**Status:** frozen and unapplied

**Candidate under review:**
`nepal_landslide_inventory_v0.7.0_candidate_20260916`

## Purpose

The completed post-correction validation labels have been converted into a
checksummed remediation queue. This queue preserves every actionable finding,
its source evidence, original audit labels, sampling provenance, recommended
actions, and systematic issue hypotheses.

The completed audits and the queue are immutable evidence. Corrections must be
recorded in separate decision and application layers.

## Queue inventory

- Total unique findings: 137
- Fresh probability-sample findings: 124 of 150 rows
- Correction-challenge findings: 13 of 50 rows
- Confirmed findings: 99
- Mixed confirmed and uncertain findings: 26
- Review-only findings: 12
- P0 identity or linkage rows: 106
- P1 attribute rows: 27
- P2 uncertain rows: 4

The fresh population-weighted flagged share is 0.841. This is not an
invalid-record rate: a valid event can be flagged for one incorrect attribute,
and multiple actions can occur on one row. Challenge rows have no sampling
weights and are never pooled with the fresh probability sample.

## Ordered correction gates

| Gate | Rows | Purpose |
|---|---:|---|
| article mapping | 67 | resolve exclusions, aggregates, splits, and re-clustering before event identity changes |
| true-value review | 45 | establish replacement dates and locations or resolve uncertain labels |
| structured attributes | 25 | apply event type, hazard type, and casualty corrections after identity is stable |

The gates form a partition of all 137 queue rows.

## Failure concentrations

| Systematic issue family | Flagged rows |
|---|---:|
| event date resolution | 45 |
| event granularity | 44 |
| event type classification | 38 |
| location role resolution | 36 |
| hazard type classification | 25 |
| casualty extraction | 24 |
| scope or event specificity | 24 |
| deduplication | 11 |

The largest flagged-source counts are Setopati (20), MyRepublica (18), Ujyaalo
Online (18), Nagarik (17), Rajdhani Daily (14), Deshsanchar (13), and The
Himalayan Times (12). These are counts within the audit findings, not
source-specific error rates; source denominators must be used before comparing
source performance.

## Challenge findings

The challenge contributes 13 actionable rows. This includes the seven unclear
identity-add cases and the Akkarebhir hazard failure identified by targeted
scoring, plus additional event-type, date, death, and granularity findings that
were outside some rows' original correction target. All are retained because
the reviewer evaluated the complete canonical record.

## Reproducible artifacts

- Builder: `scripts/build_post_correction_remediation_queue.py`
- Frozen queue: `data/outputs/post_correction_remediation_queue.csv`
- Article-mapping batch:
  `data/outputs/post_correction_remediation_BATCH_ARTICLE_MAPPING.csv`
- True-value batch:
  `data/outputs/post_correction_remediation_BATCH_TRUE_VALUE_REVIEW.csv`
- Structured-attribute batch:
  `data/outputs/post_correction_remediation_BATCH_STRUCTURED_ATTRIBUTES.csv`
- Summary: `data/outputs/post_correction_remediation_summary.json`
- Report: `data/outputs/post_correction_remediation_report.md`
- Provenance manifest: `data/outputs/post_correction_remediation_manifest.json`

The manifest verifies all completed labels, reading packs, fresh sampling
weights, validation score, queue, batches, summary, and report by SHA-256.

## Next gate

Build an article-level evidence and decision pack for the 67 article-mapping
rows. Decisions must distinguish whole-event exclusion, decomposition into
multiple physical events, article re-clustering, and unresolved review. Do not
apply date, location, or structured-attribute changes until identity and
article membership are stable.
