# Secondary extraction release decision

**Status:** DO NOT INTEGRATE
**Decision date:** 2026-09-14
**Scope:** automated district-day records recovered from additional events inside
one article

## Decision

Automated secondary records remain excluded from the SQLite production path,
canonical inventory, rainfall analysis, manuscript headline counts, and every
release bundle. The extractor is retained only as a documented research
experiment and may be run only through the standalone diagnostic scripts.

This decision does not remove the 52 human-confirmed source claims already
stored in `secondary_failures_manually_verified.csv`. That file remains a
provenance-bearing manual supplement and is not canonical inventory input.

## Evidence

The spent claim-level census confirmed both district and date for 52 of 154
old-extractor claims, joint precision 33.8%. Strict v2 then limited recovery to
explicit AD/BS dates in the same evidence sentence. A fresh 145-article frame
was drawn with zero overlap against prior evaluation URLs. Its completed file
records `ChatGPT` as annotator on all rows, so it is a model diagnostic rather
than independent human validation. It identified 59 exact district-days missing
from the pipeline primary records; strict v2 recovered 0 of 59. Its only emitted
claim occurred in an unresolved article, leaving precision unestimable.

The diagnostic therefore supplies no basis for enabling the extractor. The
conservative release decision is unchanged even though the v8 labels are not a
publishable human evaluation.

## Enforced boundary

- `landslide_inventory.run` exposes no secondary or multievent stage.
- No production module imports `unify.multievent`.
- Working and frozen canonical CSVs contain no `extraction_basis=secondary_failure` records.
- Secondary outputs are never read by deduplication, rainfall analysis, final
  export, or release creation.
- Regression coverage lives in `tests/test_secondary_release_boundary.py`.

## Reopening criteria

Reconsideration requires all of the following:

1. A newly collected corpus or a fresh article sample not used for development.
2. Independent human annotation of supported district-date pairs.
3. Enough adjudicable positive predictions to estimate precision, not merely
   recall or specificity.
4. Prespecified precision and recall gates before predictions are opened.
5. A separate storage path with provenance and no self-corroboration in dedup.
6. A new locked test and a new versioned release. Existing releases stay frozen.
