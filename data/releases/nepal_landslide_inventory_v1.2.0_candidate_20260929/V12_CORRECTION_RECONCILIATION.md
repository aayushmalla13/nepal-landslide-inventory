# v1.2 correction reconciliation

Date: 2026-09-29

## Scope

This reconciliation checks that reviewed v1.1 article corrections and dedup
identity decisions remain effective after the v1.2 parser and granularity
repairs. It uses the isolated diagnostic database and does not modify the
production database or promote a release.

## Article corrections

- Versioned corrections: 23.
- Corrected records matching every nonblank reviewed value: 23.
- Reviewed exclusions: 14.
- Reviewed exclusions reaching a canonical event: 0.
- Correction source SHA-256:
  `6f51bece72db372b97db51ec6eef25b538740281dd8deb4f77c86d6074e3ac9a`.

Two reviewed merge members had parser-date drift and were added to the
correction layer:

- Setopati Nagdi Khola reopening report: corrected to 2021-09-15.
- OnlineKhabar Mukubhanjyang follow-up: corrected to 2023-06-19; the June 17
  Bhalukhopa event in its body is background.

## Reviewed identity merges

- Versioned merge components: 40.
- Fully eligible and realized as one cluster: 25.
- Partially eligible because one or more members are filtered upstream: 15.
- Components with no eligible members: 0.
- Eligible reviewed components still split: 0.

Partially eligible components do not represent failed merges: every surviving
member has one cluster identity, while the absent members are intentionally
excluded by specificity, scope, or granularity filtering.

## Reconciled diagnostic candidate

- Canonical events: 2,160.
- Same-identity collision candidates: 338, retained as separate suffixed IDs.
- Canonical export SHA-256:
  `0c077fab7290b3fbc3f9a74dacb3adfa827e19466433221b4424b4cd75162643`.
- Manifest resume point: `corrections`; extraction and upstream filters are
  unchanged from the complete pass-3 rebuild immediately before reconciliation.

## Decision

The reviewed correction and identity layers are reconciled with the repaired
pipeline. This remains a diagnostic candidate, not a validated release. The
next stage is to freeze a v1.2 candidate artifact and draw a new untouched
probability sample that excludes all previously reviewed event IDs and article
URLs.
