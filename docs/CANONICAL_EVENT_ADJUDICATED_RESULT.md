# Adjudicated canonical event audit result

## Scope

This is the definitive event-level audit of the frozen inventory release
`nepal_landslide_inventory_v0.6.0_v7_20260915`. Two independent reviewers
labelled the same stratified 150-event sample in different random orders. A
third reviewer adjudicated all 46 rows containing at least one disagreement.

The audit validates the frozen release; it does not modify that release.

## Inter-annotator reliability

| Field | Comparable n | Agreement | Cohen's kappa |
|---|---:|---:|---:|
| event really happened | 150 | 0.973 | 0.874 |
| usable record status | 150 | 0.933 | 0.873 |
| one physical event | 130 | 0.938 | 0.844 |
| district correct | 130 | 0.969 | 0.897 |
| date correct | 130 | 0.823 | 0.613 |
| municipality correct | 64 | 0.922 | 0.261 |
| event type true | 130 | 0.977 | 0.953 |
| hazard type true | 130 | 0.969 | 0.705 |
| deaths true | 130 | 0.946 | 0.885 |
| duplicate merge correct | 38 | 0.895 | 0.774 |

Date has the weakest practically important agreement and should be treated as
an uncertainty source. Municipality kappa is low despite 92.2% exact agreement
because almost all ratings are positive; report both values rather than kappa
alone.

## Adjudicated population-weighted estimates

| Metric | Estimate | 95% stratified-bootstrap CI | Decisive n | Unclear / N.A. |
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

Unclear labels are excluded from point estimates and reported explicitly. The
adjudicated estimates closely reproduce the first review, showing that low
strict usability is not an artefact of one annotator.

## Reproducibility

Run:

```bash
PYTHONPATH=src .venv/bin/python scripts/finalize_canonical_event_adjudication.py
PYTHONPATH=src .venv/bin/python scripts/score_canonical_event_audit.py \
  data/outputs/canonical_event_audit_ADJUDICATED.csv \
  --json-output data/outputs/canonical_event_audit_adjudicated_score.json \
  --report-output data/outputs/canonical_event_audit_adjudicated_report.md
```

The adjudication manifest records all input and output SHA-256 hashes. The
completed adjudication contains 46 resolved rows; 104 rows retain the reviewers'
agreed labels.

## Scientific implication

The inventory is useful as a high-recall candidate event collection, but the
frozen v0.6.0 release is not sufficiently precise for analyses requiring exact
event date, event granularity, event type, or duplicate identity without
qualification. Manuscript claims must use the adjudicated estimates. Corrections
belong in a new versioned inventory release and must never overwrite v0.6.0.
