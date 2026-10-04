# Rainfall analysis changelog

## v0.2.0 — 2026-08-14

Supersedes `nepal_landslide_rainfall_v0.1.0_20260813`
(bundle lock `b22e9008a3cb96ce355fcf59c8b7b0a8b372a4810ff6e1a0744dc4cac1e273d1`).
Version 0.1.0 is preserved on disk unchanged as the historical baseline. The new
bundle lock is recorded in this release's `release_manifest.json`.

### The headline result did not change

| Quantity | v0.1.0 | v0.2.0 |
|---|---|---|
| Primary case-days / matched controls | 1,514 / 6,196 | 1,514 / 6,196 |
| Development-selected window | 5 days | 5 days |
| Threshold | 45.4 mm | 45.4 mm |
| Threshold 95% CI (development) | 26.8–72.1 mm | 26.8–72.1 mm |
| Temporal-test AUC | 0.693 (0.657–0.722) | 0.693 (0.657–0.722) |
| Sensitivity | 0.509 (0.449–0.567) | 0.509 (0.449–0.567) |
| Specificity | 0.764 (0.718–0.809) | 0.764 (0.718–0.809) |
| Balanced accuracy | 0.637 | 0.637 |
| Matched-sample precision | 0.359 | 0.359 |
| District-month Spearman ρ | 0.275 | 0.275 |

The v0.1.0 analysis was re-run from scratch in a clean environment before any
change was made; it reproduced every headline figure exactly. What follows is
therefore additive, not a correction of the previous numbers.

### What is new

**1. Strictly antecedent co-primary analysis.** Windows ending the day *before*
the reported event were already computed in v0.1.0 (`r{w}_lag1_mm`) and written
to the case/control tables, but were never analysed. They now form a co-primary
result, because a window that includes the reported event day can contain rain
that fell after the failure.

| Exposure | Window | Threshold | Development AUC | Temporal-test AUC |
|---|---|---|---|---|
| Concurrent (includes event day) | 5 days | 45.4 mm | 0.642 | **0.693** (0.657–0.722) |
| Strictly antecedent (excludes it) | 3 days | 19.1 mm | 0.622 | **0.664** (0.628–0.697) |

About 0.03 of AUC is carried by the event day itself. Median event-day rainfall
is 7.35 mm on case-days against 1.13 mm on control days.

**2. Conditional (within-matched-set) models.** Conditional logistic regression
stratified by matched set, with district-clustered sandwich standard errors, is
the estimator the matched design implies. New file
`rainfall_conditional_models.csv`.

| Split | Exposure | Odds ratio per 10 mm | 95% CI | Within-stratum concordance |
|---|---|---|---|---|
| All years | R5 concurrent | 1.227 | 1.193–1.261 | 0.671 |
| Development | R5 concurrent | 1.200 | 1.161–1.240 | 0.650 |
| Temporal test | R5 concurrent | 1.275 | 1.218–1.336 | 0.703 (0.662–0.740) |
| All years | R3 antecedent | 1.221 | 1.188–1.255 | 0.645 |
| Temporal test | R3 antecedent | 1.305 | 1.233–1.381 | 0.671 (0.628–0.707) |

Within-stratum concordance (0.650 development, 0.703 test) tracks the pooled AUC
(0.642, 0.693) closely, which confirms that the v0.1.0 pooled estimate was not
materially distorted by ignoring the matching. The odds ratio is new
information: the pooled cutpoint never expressed an effect size.

Absolute risk, calibration and decision-curve net benefit remain deliberately
unreported. They require a marginal probability of a landslide district-day that
a media-derived inventory cannot identify. The exclusion is now stated in the
machine-readable report under `analysis_roles.not_reported`.

**3. Leave-one-year-out and spatial validation.** New file
`rainfall_resampled_validation.csv`.

| Scheme | Exposure | Folds | Median AUC | Range | SD | Threshold range |
|---|---|---|---|---|---|---|
| Leave-one-year-out | R5 concurrent | 12 | 0.652 | 0.563–0.710 | 0.053 | 45.38–45.42 mm |
| Spatial (5 district folds) | R5 concurrent | 5 | 0.667 | 0.640–0.677 | 0.016 | 37.5–48.0 mm |
| Leave-one-year-out | R3 antecedent | 12 | 0.622 | 0.560–0.690 | 0.046 | 19.1–22.7 mm |
| Spatial (5 district folds) | R3 antecedent | 5 | 0.632 | 0.622–0.656 | 0.013 | 20.1–23.0 mm |

Two conclusions, both new:

- The prespecified temporal-test AUC of 0.693 sits in the **top quartile** of the
  year-to-year range. The honest central estimate of out-of-year discrimination
  is ≈0.65, with interannual variation comparable to the width of the bootstrap
  interval. Reporting 0.693 alone was optimistic.
- The **cutpoint** replicates far better than the discrimination does: 45.4 mm
  was selected in 11 of 12 leave-one-year-out fits, and spatial folds vary by
  only ±5 mm.

**4. Matching diagnostics and a strict matched-set sensitivity analysis.** New
file `rainfall_matching_diagnostics.json`. Two structural properties of the
control sampling were previously undocumented:

- **192 of 1,514 cases (12.7 %) had no eligible control.** Controls per case:
  5 → 1,150; 4 → 54; 3 → 37; 2 → 38; 1 → 43; 0 → 192. These are not missing at
  random — they are district-months dense enough with reported events that the
  ±7-day buffer consumed the pool — and in a pooled ROC they enter as unmatched
  positives.
- **20.1 % of control rows repeat a district-day.** 6,196 rows cover 4,948
  distinct district-days; 800 days are reused, one of them 8 times.

The new `strict_matched_sets` variant (complete strata, each control day used
once) gives temporal-test AUC 0.683 at a 3-day, 31.6 mm cutpoint — close enough
to the primary result to show that neither defect is driving it.

**5. Balanced source panel.** The development and temporal-test periods draw on
partly different publishers: 17.9 % of development events come from titles absent
from the test period (`deshsanchar`, `khabarhub`, `nepali-times`), and 17.0 % of
test events come from titles absent from development (`ekantipur`,
`online-khabar`, `ratopati`). The article-level language mix also shifts, from
243 English / 45 Nepali in 2015 to 415 / 1,282 in 2024.

Restricting to the seven publishers contributing ≥30 canonical events on both
sides of the cut-off (`myrepublica`, `nagarik`, `nepalpress`, `onlinekhabar-en`,
`rajdhani`, `setopati`, `ujyaalo`) gives temporal-test AUC **0.696** —
indistinguishable from the primary 0.693. **Publisher turnover does not explain
the result.** New file `inventory_reporting_composition.csv`.

**6. The development-to-test AUC gap is now reported.** Temporal-test AUC exceeds
development AUC for every window and every one of the nine designs, by +0.030 to
+0.053. This was present in v0.1.0 and unremarked. It survives the balanced
source panel (+0.049), strict matched sets (+0.046), higher date confidence
(+0.041) and road-obstruction exclusion (+0.050), so it is not an artefact of
publisher turnover, pseudo-replication, date quality or event typing.

The observable explanation is case-mix: later-period case-days sit in *drier*
district-months (median all-day 5-day accumulation across case strata ≈ 40 mm in
2015–2020 against ≈ 30 mm in 2022–2025) while case-day rainfall stays near
50 mm, so the within-stratum contrast is sharper. Broader reporting in later
years reaches events in marginal, drier settings. Per-period distributions are
now emitted in `rainfall_case_control_distributions.csv`.

**7. Season stratification.** New file `rainfall_season_stratified.csv`.

| Season | Threshold | Development AUC | Temporal-test AUC | Sensitivity | Specificity |
|---|---|---|---|---|---|
| Monsoon (JJAS) | 45.4 mm | 0.627 | 0.687 | 0.599 | 0.671 |
| Non-monsoon | 1.5 mm | 0.699 | 0.718 | 0.673 | 0.598 |

The headline 45.4 mm is a monsoon quantity. Outside the monsoon the optimal
cutpoint is an order of magnitude lower, because in a dry month any rain at all
separates event days. A single national year-round cutpoint is not defensible,
and the manuscript now says so.

**8. Secondary aggregate correlation is now bounded.** Alongside the pooled
district-month Spearman ρ = 0.275, the monsoon-only coefficient is reported:
**ρ = 0.129**. Most of the pooled association is the contrast between wet and dry
months rather than a within-season signal.

**9. Descriptive analysis and three new figures.** District, province and month
summaries; per-period case/control rainfall distributions; a district choropleth;
a seasonality and distribution figure; and a held-out validation figure. Figure
code moved from `scripts/plot_rainfall_results.py` into
`src/landslide_inventory/analysis/figures.py` so it is importable and tested;
the script remains as the entry point.

**10. Inventory granularity is now stated.** 754 of 3,114 canonical records share
a district-day with another record (2,360 distinct district-days). Canonical
records are deduplicated *report clusters*, not verified distinct physical
failures. The rainfall analysis was always collapsing these to one case-day; the
manuscript now says what the 3,114 figure does and does not mean.

### Reproducibility fixes

- `rainfall_analysis_report.json` recorded absolute paths under
  `/Users/aayush/Library/CloudStorage/Box-Box/…`. It now records
  repository-relative paths plus the SHA-256 of each input, so a release can be
  verified anywhere.
- Emitted numerics are rounded at fixed precision. Floating-point summation order
  differs between platforms (`46.121096` on macOS against
  `46.121095999999994` on Linux for the same input), which made byte-level
  bundle-lock hashes machine-specific even when the science was identical.
- The threshold confidence interval is estimated in development data. Every
  emitted row now carries `threshold_fitted_on` and `threshold_ci_split` so it
  cannot be read as a test-set interval.
- Window selection ties are broken toward the shorter window, so the choice never
  depends on iteration order. The primary 3-day and 5-day development AUCs differ
  by 0.0003.
- The release manifest now carries input checksums, the co-primary result, the
  matching diagnostics, the resampled-validation summary, a `supersedes` pointer,
  and three additional integrity checks (co-primary present, input paths
  repository-relative, conditional models converged).

### Tests

39 new tests (553 → 592, all passing):

- `tests/test_matched_analysis.py` — conditional logistic regression validated
  against the closed-form McNemar matched-pair odds ratio; null-effect recovery;
  separation and quasi-separation handling; sandwich-versus-model standard
  errors; concordance tie handling; matching diagnostics; strict matched-set
  determinism and single-use guarantee.
- `tests/test_resampled_validation.py` — deterministic district folds
  independent of input order; fold coverage; exposure selection actually changes
  the fitted cutpoint; spread summaries.
- `tests/test_rainfall_pipeline_outputs.py` — full stage run on a synthetic study
  area: relative paths and input checksums, declared analysis roles including the
  documented exclusions, both exposures present, one cutpoint per
  variant/window (a guard against retuning on the holdout), rounded emission,
  determinism on re-run, and figure rendering.
- `tests/test_rainfall_analysis.py` — lagged windows exclude the event day;
  source-panel filtering; balanced-panel rule; source carried through
  `read_events`; rounding; bootstrap helpers honour an alternative exposure.

### What did not change

The frozen inventory release `nepal_landslide_inventory_v0.4.0_v6_20260810`, the
locked-v6 evaluation artefacts, all labels, all predictions, and the v0.1.0
rainfall release are untouched. Both prior manifests were verified before and
after this work: 12/12 and 16/16 file checksums valid, bundle locks confirmed.
