# Nepal Landslide Inventory Project Handover

**Status date:** 2026-10-04
**Authoritative repository:** `/Users/aayush/Library/CloudStorage/Box-Box/nepal_landslide_inventory`
**Git branch:** `fix/review-immediate`
**Observed commit:** `b1303ac0ea2b1763d8ff14da1aebba8d71c189a2`
**Runtime:** Python 3.12.12 in `.venv`

## 1. Project objective

Build a reproducible, bilingual, web-derived landslide event inventory for
Nepal covering 2015-2026, evaluate it with locked human review, compare it with
independent administrative evidence, and test its association with antecedent
rainfall.

The final defensible primary claim is:

> A validated high-precision web-derived landslide event-detection inventory
> for Nepal.

The release also supports a validated district-assignment claim. It does not
support a complete-census claim, a high-precision full-record claim, uniformly
correct exact dates, or an operational rainfall-warning threshold.

## 2. Authoritative releases

| Component | Release | Status | Bundle lock |
|---|---|---|---|
| Canonical inventory | `nepal_landslide_inventory_v1.5.0_event_detection_validated_20261004` | Event detection validated; full record not validated | `95ba6f7516a77a2f0adea5ee35ecdf95e722c209ae55ce387dadbff8a8839585` |
| BIPAD agreement | `nepal_landslide_external_validation_v0.2.0_20261004` | Analysis complete against v1.5 | `4b272be42d7021c5eeb22844d745997c91d66d4cc04d2e959b0687ef68bbb0dc` |
| Rainfall analysis | `nepal_landslide_rainfall_v1.0.0_20261004` | Analysis complete against v1.5 | `2ea2ecae304231d69897db9af39b3dbde40c8c5b19922c1450c7a86511e92f22` |

Canonical inventory SHA-256:
`313745c27218be7989764cc9614b71cc69a9549ff05c483247a6c89bd276ae19`.

Do not substitute `data/outputs/canonical_events_final.csv`, a mutable SQLite
table, or an older release for the canonical CSV in the v1.5 release.

## 3. Final inventory

| Property | Final value |
|---|---:|
| Canonical records | 2,122 |
| Study period | 2015-03-07 to 2026-08-09 |
| Districts represented | 74 of 77 |
| Representative publishers | 16 |
| Collected articles in evidence database | 10,203 |
| Logged v1.5 release actions | 155 |
| Multi-article canonical clusters | 381 |
| June-September records | 1,722 (81.1%) |
| Top-three publisher share | 47.0% |

Districts without a retained record are Kanchanpur, Saptari, and Siraha.
This is a media-coverage result and is not evidence that landslides did not
occur there.

## 4. Validation result

The fresh v1.5 evaluation used a 150-row stratified probability sample from a
568-record previously unreviewed eligible frame. Strata crossed language,
period, event type, and single-versus-multi-article support. Estimates use
inverse-probability weights and within-stratum bootstrap confidence intervals.

| Metric | Weighted estimate | 95% CI | Decision |
|---|---:|---:|---|
| Event-existence precision | 0.958 | 0.923-0.986 | pass |
| Usable-record precision | 0.570 | 0.493-0.650 | fail |
| Single-event accuracy | 0.822 | 0.762-0.881 | fail |
| District accuracy | 0.910 | 0.865-0.953 | pass |
| Exact-date accuracy | 0.753 | 0.678-0.823 | fail |
| Municipality accuracy | 0.859 | 0.783-0.923 | descriptive |
| Event-type accuracy | 0.893 | 0.843-0.937 | descriptive |
| Hazard-type accuracy | 0.902 | 0.853-0.944 | descriptive |
| Deaths exact accuracy | 0.867 | 0.813-0.916 | descriptive |
| Duplicate-merge accuracy | 0.942 | 0.826-1.000 | descriptive |

Raw overlapping error counts in the sample include six non-events, 25
multi-event records, 12 district errors, and 32 date errors. The sample is
spent and must not be reused to validate a future repaired candidate.

## 5. Annotation reliability

A separate earlier 150-row canonical audit was independently reviewed by two
humans. It is an inter-rater study, not the fresh v1.5 performance sample.

| Field | Agreement | Cohen's kappa |
|---|---:|---:|
| Event existence | 0.973 | 0.874 |
| Usable-record status | 0.933 | 0.873 |
| Single physical event | 0.938 | 0.844 |
| District correctness | 0.969 | 0.897 |
| Date correctness | 0.823 | 0.613 |
| Event type | 0.977 | 0.953 |
| Hazard type | 0.969 | 0.705 |

The lower date agreement is consistent with the final v1.5 date limitation.

## 6. BIPAD external agreement

The v1.5 external analysis uses the same fixed normalized BIPAD snapshot as the
earlier comparison and does not recollect or silently merge administrative
records into the news inventory.

| Quantity | Value |
|---|---:|
| Eligible news events through common cutoff | 2,119 |
| BIPAD input rows | 5,345 |
| Harmonized BIPAD clusters | 4,095 |
| Tier-A candidate pairs | 482 |
| Tier-B candidate pairs | 360 |
| Strongly linked BIPAD clusters | 562 |
| Tier-A observed overlap | 0.2204 |
| Tier-A expected overlap under date permutation | 0.0927 |
| Tier-A chance-corrected overlap | 0.1276 |
| Empirical p-value | 0.0099 |

BIPAD is an incomplete administrative observation system and may partly depend
on media reports. The analysis reports overlap and chance-corrected agreement,
not precision, recall, or completeness against a ground truth.

## 7. Rainfall analysis

The rainfall analysis uses CHIRPS v2.0 Final daily district means for all 77
districts through 2026-07-31. Cases are matched to controls in the same
district, calendar month, and year, with controls at least seven days from any
reported event.

| Result | Value |
|---|---:|
| Primary case-days | 1,278 |
| Matched controls | 5,460 |
| Development period | through 2022-12-31 |
| Temporal test period | 2023 onward |
| Concurrent selected window | R3 |
| Concurrent threshold | 31.7 mm |
| Concurrent test AUC | 0.686 (0.647-0.722) |
| Concurrent sensitivity / specificity | 0.473 / 0.789 |
| Strictly antecedent window | R3 |
| Strictly antecedent threshold | 21.0 mm |
| Strictly antecedent test AUC | 0.646 (0.604-0.682) |
| Leave-one-year-out concurrent AUC | median 0.663, range 0.576-0.711 |

The v1.0 analysis added confidence `>=0.90` and event-date shifts of -3 and +3
days to the existing confidence and +/-1-day checks. Only 17 cases have
confidence `>=0.90`, so that subset is too sparse for a stable temporal result.
Across date shifts, the selected threshold ranges from 15.4 to 87.9 mm and the
window changes from R3 to R7. This is a direct reason not to call 31.7 mm an
operational warning threshold.

The refreshed integrity audit examined all 1,278 case-days, found no logically
impossible rows, and identified three potentially contaminated case-days
(0.23%). Removing them changes the R3 AUC by 0.0000 and its cutpoint by 0.0 mm.

## 8. Pipeline stages completed

- Multi-source collection and evidence storage for English and Nepali outlets.
- Publication-date normalization and language routing.
- English and Nepali event extraction.
- Event-specificity classification and secondary-event/parser work.
- Nepal scope filtering and district-location consistency checks.
- Event and hazard typing, including road-obstruction handling.
- Cross-source deduplication and collision adjudication.
- Manual correction application with immutable action logs.
- Canonical export to CSV and SQLite with equality and integrity checks.
- Multiple locked article- and event-level audits.
- Independent human second annotation and adjudication workflow.
- Exact-date release preflight and exclusion of unresolved reconstructed dates.
- Event-detection-scoped release freezing with explicit failed full-record status.
- BIPAD harmonization, candidate matching, chance correction, and frozen release.
- CHIRPS matched case-control analysis, temporal holdout, conditional models,
  resampled validation, source-panel checks, season checks, and date sensitivity.
- Generated manuscript tables, Methods/Data material, and paper-facing summary.

## 9. Major v1.5 remediation history

The v1.5 candidate started from the frozen 2,138-row v1.4 candidate.

| Action | Count |
|---|---:|
| Old events superseded | 38 |
| Release-ready reconstructed events added | 26 |
| Candidates merged into existing events | 9 |
| Reconstruction candidates excluded for unresolved exact dates | 24 |
| True-value corrections | 21 |
| Existing events excluded by true-value review | 4 |
| Structured-attribute corrections | 33 |
| Final canonical rows | 2,122 |

## 10. Additional work completed beyond the original stage prompts

- Repaired manual-audit input selection to prefer the refreshed verification
  sample and added regression coverage.
- Expanded and repaired source parsers, particularly for difficult publisher
  layouts and secondary-event evidence.
- Added deterministic collision, reconstruction, and exact-date preflight
  workflows instead of applying undocumented edits directly to canonical data.
- Added header-safe materialization for empty correction or exclusion outputs.
- Added release builders and integrity verification for every important bundle.
- Preserved the failed full-record promotion decision while creating a separate
  truthful event-detection-validated release status.
- Updated the BIPAD analysis to compare against the final v1.5 hash.
- Added +/-3-day rainfall sensitivity and a very-high-date-confidence subset.
- Repaired case-integrity auditing to use `raw_articles` in SQLite when the old
  corpus CSV is unavailable, preventing stale diagnostics from being bundled.
- Replaced hand-maintained paper numbers with generated v1.5 summaries and
  regression tests that detect manuscript/result drift.

## 11. Key paper artifacts

| Purpose | File |
|---|---|
| Paper summary | `docs/V15_PAPER_SUMMARY.md` |
| Methods, data, workflow, bias, validation | `docs/V15_METHODS_AND_DATA.md` |
| Generated manuscript core | `docs/RAINFALL_MANUSCRIPT_DRAFT_V15.md` |
| Generated rainfall tables | `docs/RAINFALL_MANUSCRIPT_TABLES.md` |
| Rainfall protocol | `docs/RAINFALL_ANALYSIS.md` |
| Validation interpretation | `docs/V15_FINAL_VALIDATION_RESULT.md` |
| Candidate assembly result | `docs/V15_CANDIDATE_RESULT.md` |
| Declarations needing author input | `docs/MANUSCRIPT_DECLARATIONS.md` |

The older `MANUSCRIPT_*_V04.md` and `RAINFALL_MANUSCRIPT_DRAFT.md` files are
historical. Do not copy their headline counts or rainfall results into a new
submission.

## 12. Reproduction commands

Run from the authoritative Box repository.

```bash
PYTHONPATH=src .venv/bin/pytest \
  tests/test_v15_event_detection_release.py \
  tests/test_v15_paper_summary.py \
  tests/test_v15_methods_data.py \
  tests/test_external_validation_release.py \
  tests/test_rainfall_pipeline_outputs.py \
  tests/test_manuscript_tables.py -q

PYTHONPATH=src .venv/bin/python scripts/build_v15_paper_summary.py
PYTHONPATH=src .venv/bin/python scripts/build_v15_methods_data.py
PYTHONPATH=src .venv/bin/python scripts/build_v15_rainfall_manuscript.py
PYTHONPATH=src .venv/bin/python scripts/build_manuscript_tables.py

.venv/bin/python scripts/verify_releases.py
```

Re-running `external_match`, `analysis`, or a release stage overwrites mutable
working outputs or creates a new release. Do so only when intentionally cutting
a new version, and never overwrite the three authoritative release directories.

## 13. Repository cautions

- The Box repository is authoritative. `/Users/aayush/Documents/nepal_landslide_inventory`
  is a second checkout historically used for completed manual CSV submissions.
- The working tree contains extensive uncommitted project changes. Do not run
  `git reset --hard`, `git checkout --`, or broad cleanup commands.
- `data/` is ignored by Git. Release bundles therefore require separate archive
  or repository deposition even when code is committed.
- Pytest may warn that `.pytest_cache` cannot be written inside Box. This has
  not affected test execution.
- Full news article text may contain copyright-protected material and personal
  information. Publish URLs, checksums, and derived fields, not the full corpus.
- A previous human label was mistakenly recorded as AI and later corrected;
  provenance statements should use the final human attribution.

## 14. Remaining submission work

- Select the target journal and restructure the generated core to its article
  format and word limits.
- Add authors, affiliations, ORCIDs, corresponding-author details, CRediT roles,
  funding, conflicts, and institutional ethics/privacy confirmation.
- Complete the literature review and reference list, including comparable web-
  mined landslide inventories and Nepal rainfall-threshold studies.
- Decide the public license for code and derived data.
- Resolve or replace any remaining unlicensed gazetteer dependency before public
  redistribution.
- Deposit the three authoritative release bundles and code snapshot in Zenodo
  or another repository and add DOI citations.
- Export final figures to the journal's required format and resolution.
- Run a final cross-document number check after journal formatting.
- Commit the intended source and documentation changes without accidentally
  including private article text or temporary review files.

## 15. Recommended paper framing

Lead with the inventory and its locked event-detection validation. Treat the
rainfall analysis as a substantive demonstration and convergent-validity layer,
not the basis for an early-warning product. Treat BIPAD as an incomplete second
observation system. Make reporting bias and date uncertainty central results,
not footnote caveats.

The project is ready for full manuscript writing. It is not yet ready for
submission until declarations, references, journal formatting, licensing, and
DOI deposition are complete.
