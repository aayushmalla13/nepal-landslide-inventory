# Rainfall analysis changelog

## v0.7.0 — 2026-09-15

Supersedes `nepal_landslide_rainfall_v0.6.0_20260904`. All earlier releases are
preserved as historical baselines.

This is a provenance-only release. The numerical analysis outputs, controls,
figures and manuscript results are unchanged from v0.6.0. The release now links
to `nepal_landslide_inventory_v0.5.0_v7_20260915`, whose canonical CSV SHA-256
(`3b335babbfcbe0b50d2aad9023e08e55a2ca6e8e0881729615df33e2c9b9d0e8`)
matches the canonical-input hash recorded by the rainfall analysis.

Earlier rainfall manifests named the immutable v0.4.0/v6 inventory release even
though their machine-readable input section correctly pinned the later canonical
CSV hash. No result was numerically ambiguous, but the named release linkage was
wrong. The v0.7.0 builder now refuses to create a bundle unless the configured
inventory release and rainfall report carry the same canonical hash.

## v0.6.0 — 2026-09-04

Supersedes `nepal_landslide_rainfall_v0.5.0_20260903`. All earlier releases are
preserved as historical baselines.

Two changes, one to the code and one to the evidence base.

### 1. Control sampling is no longer coupled across cases (code change)

`build_matched_controls` drew every case's controls from one shared
`random.Random(seed)` stream, shuffling each candidate pool in turn. Deterministic
given a fixed event list, but coupled: removing any event shifted the stream and
redrew the controls for every case after it.

This was found by an analysis that should have been unaffected by it. Truncating
the rainfall series to the IMERG record for the product comparison drops 181
events, all after 2025-09-30, which share no year, no stratum and no candidate day
with the 2015–2022 development split. Only 532 of that split's 3,587 controls
survived, and the fitted cutpoint moved 51.6 mm → 45.3 mm. Every sensitivity
analysis that adds or removes events was partly measuring a redrawn control
sample rather than the thing it varied.

Each case now draws from its own stream, keyed by SHA-256 of the seed and the
case's record id (`hash()` is salted per process and would not reproduce).
Covered by `tests/test_control_sampling_independence.py`.

**Effect on the headline result: essentially none, which is itself informative.**

| | v0.5.0 | v0.6.0 |
|---|---|---|
| Controls shared with the previous release | — | 682 of 6,164 |
| Development-selected window | 5 days | 5 days |
| **Primary threshold** | **51.6 mm** | **51.6 mm** (identical to 4 dp) |
| Threshold bootstrap CI | 43.9–61.4 mm | 33.7–61.7 mm |
| Temporal-test AUC | 0.670 | 0.675 |
| Sensitivity | 0.456 | 0.456 |
| Specificity | 0.766 | 0.772 |
| Primary case-days / matched controls | 1,508 / 6,164 | 1,508 / 6,164 |

A near-complete redraw of the matched controls left the cutpoint unmoved. The
threshold interval widens at the lower end, which is the more honest interval:
the previous one was narrowed by the sampler's coupling.

### 2. The single-rainfall-product limitation is retired

NASA IMERG Final Run v07 was downloaded for the full record (302,302 district-days,
3,926 days × 77 districts, 2015-01-01 to 2025-09-30, no gaps) and the analysis
re-run on it, against a CHIRPS run truncated to the identical period so that
product varies and period does not.

- The two products agree in bulk: a stable ratio of means of 1.152–1.153 at every
  window, Spearman 0.78 at R5, 89.7% agreement and Cohen's kappa 0.607 on
  exceeding 51.6 mm.
- **IMERG discriminates better at every window in both splits**, by +0.034 to
  +0.063 AUC. All eight paired, district-clustered bootstrap intervals exclude
  zero. The runs share one case-control design, so the comparison is paired and
  the design's own variability cancels.
- The cutpoint does **not** move by the products' 1.152 scale factor. Window-matched
  ratios scatter from 0.53 to 1.16, and the two runs select different windows
  (CHIRPS R5 at 51.6 mm; IMERG R3 at 28.3 mm).

The association is therefore not an artefact of CHIRPS. The specific number is
CHIRPS-specific. Full account in `docs/RAINFALL_PRODUCT_SENSITIVITY.md`;
measurement comparison in `docs/RAINFALL_PRODUCT_COMPARISON.md`.

Incidentally demonstrated, and now stated in the manuscript: under a control
redraw that changed nothing else, IMERG's R5 AUC moved by 0.0008 while its
cutpoint moved 38% (62.8 → 39.1 mm). Discrimination is stable; the Youden
cutpoint is not.

## v0.5.0 — 2026-09-03

Supersedes `nepal_landslide_rainfall_v0.4.0_20260903` (lock `a2a54cc7ec03…`).
All earlier releases are preserved. New lock `d0011abf0c85…`.

No change to the analysis code or to the inventory. This release extends the
**rainfall record** by one month, from 30 June to 31 July 2026, recovering
events that were previously excluded only because no rainfall existed to pair
them with.

### Provenance, checked rather than assumed

The extension was downloaded with a deliberate one-month overlap so the new
fetch could be verified against the existing series before being trusted. The
2,310 overlapping district-days (30 days × 77 districts) reproduce the stored
values **exactly**, to the last decimal place.

Every new day is served as **CHIRPS v2.0 Final**. There is no CHIRPS *Prelim*
in this release, so the mixed-product sensitivity analysis contemplated in
`EXTERNAL_DATA_BLOCKED.md` §1 is not needed and the whole series remains one
homogeneous product.

### Effect

| | v0.4.0 | v0.5.0 |
|---|---|---|
| Rainfall record ends | 2026-06-30 | **2026-07-31** |
| Events excluded for want of rainfall | 84 | **18** |
| Primary case-days / matched controls | 1,457 / 5,988 | 1,508 / 6,164 |
| Development-selected window | 5 days | 5 days |
| **Primary threshold** | **51.6 mm** | **51.6 mm** |
| Temporal-test AUC | 0.675 | 0.670 |
| Sensitivity | 0.448 | 0.456 |
| Specificity | 0.786 | 0.766 |
| Co-primary R3 antecedent | 19.1 mm, AUC 0.653 | 19.1 mm, AUC 0.645 |

**66 events recovered**, and the primary cutpoint did not move at all — it
remains 51.6 mm through an inventory revision, a casualty-extraction revision
and now a rainfall extension. That is worth stating carefully. It is *not*
evidence that 51.6 mm is a stable physical constant: v0.2.0's 45.4 mm was
equally unmoving right up until the inventory changed under it. It does say the
estimate is insensitive to adding a month of monsoon data, which is a narrower
and more defensible claim.

The small AUC decline (0.675 → 0.670) is expected: the recovered events are
concentrated in July 2026, deep in the temporal-test period, so they enter the
held-out set rather than the development set and make the test harder rather
than easier.

### A data-loss bug found and fixed

The downloader wrote its output with mode `"w"` and emitted only the rows for
the requested window. Running it incrementally therefore **destroyed the rest of
the series**: a run with `--start 2026-06-01` replaced a 2015-2026 file of
323,323 district-day rows with 4,697, silently. The full series was recoverable
from the frozen v0.2.0 release bundle, which is precisely what those bundles are
for.

`merge_and_write` now merges into the stored series, writes through a temporary
file so an interrupted run cannot truncate either, and requires an explicit
`--replace` to discard anything. A re-fetched district-day still overwrites the
stored one, so a Prelim day later superseded by Final can be corrected by
re-running. Four regression tests cover it.

## v0.4.0 — 2026-09-03

Supersedes `nepal_landslide_rainfall_v0.3.0_20260903` (lock `2658b66a0ff3…`),
which is preserved on disk, as are v0.1.0 and v0.2.0. New lock `a2a54cc7ec03…`.

Again no change to the analysis code. This release carries a second inventory
correction, this time to **casualty extraction**, cut separately from v0.3.0 so
that the district work and the casualty work can be attributed independently.

### What changed in the extractor

The Nepali casualty patterns matched `\d+` only. Nepali disaster reporting
writes small tolls as words — "तीन जनाको मृत्यु", "एक बालकको मृत्यु" — and
confirms deaths through body-recovery sentences that contain no death term at
all — "पाँच जनाको शव भेटिएको छ". English counts separated from their verb by an
apposition ("Four persons of a single family were buried to death") were missed
for the same reason.

**The digit-only patterns were not merely missing counts; they were producing
wrong ones.** With no correct match available, a loose fallback took whichever
digit sat near a death word, which was routinely a different quantity:

| Headline | Recorded | Correct |
|---|---:|---:|
| नौ जनाको मृत्यु, **४५** बेपत्ता | 45 | 9 |
| चार जनाको मृत्यु, **१०** घाइते | 10 | 4 |
| एक जनाको मृत्यु, **९** सवारी साधन पुरिए | 9 | 1 |
| दुई जनाको मृत्यु, **६ लाख** सत्तरी हजार सुरक्षित | 6 | 2 |

Missing counts, injured counts, vehicle counts and even a six-hundred-thousand
evacuation figure were being recorded as death tolls. All 45 changed death
values were inspected; every one is a correction.

### Explicit zeros, and the rule that governs them

An article that states nobody was harmed now records **0** rather than unknown,
because "a landslide happened and hurt nobody" is different information from "we
do not know". The project's standing rule that an unknown value is never
replaced by zero is preserved by four guards, each derived from a labelled
failure: a no-casualty phrase is necessary but never sufficient; no count may
have been extracted anywhere; no death vocabulary may appear anywhere; and the
claim must not be a roundup or be contradicted later in the article
("बाढीको कारणले मानवीय क्षति भएको छैन। तर पहिरो गएर इलाममा भने क्षति भएको").
58 articles record an explicit zero.

Measured on 78 labelled articles drawn seed-deterministically and excluding all
1,090 prior evaluation URLs: exact agreement 0.808, recall on counts a human
read 0.767, and **false zeros 0**, which is the number that has to stay at zero.
Development diagnostics only — see `docs/CASUALTY_EXTRACTION_2026-09-03.md`.

### Effect on the inventory and on the result

| | v0.3.0 | v0.4.0 |
|---|---:|---:|
| Articles with a death count | 1,410 | 2,246 |
| Articles with a missing count | 874 | 1,243 |
| Articles with an injured count | 544 | 839 |
| Canonical events | 2,950 | 2,885 |
| Primary case-days / controls | 1,471 / 6,049 | 1,457 / 5,988 |
| Primary threshold | 51.6 mm | 51.6 mm |
| Temporal-test AUC | 0.676 | 0.675 |
| Sensitivity / specificity | 0.447 / 0.785 | 0.448 / 0.786 |
| Co-primary R3 antecedent | 20.0 mm, AUC 0.652 | 19.1 mm, AUC 0.653 |

+836 death counts, +369 missing, +295 injured, and **none lost**. 28 articles
rose from class 2 to class 1 on newly recovered human impact.

The rainfall result is essentially untouched, which is the expected and correct
outcome: the threshold analysis uses district, date, trigger and event type, and
never reads a casualty count. Casualties reach it only through the class ladder,
and 28 promotions out of 6,399 class-1 articles cannot move a threshold. The
co-primary cutpoint returning to its v0.2.0 value of 19.1 mm is coincidence, not
a reversal.

The value of this release is therefore in the **inventory**, not the threshold:
death, missing and injured counts are now recorded for roughly twice as many
articles, and the counts that were already there are more often right.

## v0.3.0 — 2026-09-03

Supersedes `nepal_landslide_rainfall_v0.2.0_20260814`
(bundle lock `404ddfe66a11a42fa72a9b341fd1a8817f52d3370b454af87a99b3a68919870c`).
Versions 0.1.0 and 0.2.0 are preserved on disk unchanged as historical
baselines. The new bundle lock is recorded in this release's
`release_manifest.json`.

### Nothing about the method changed. The inventory did.

This release contains no change to the analysis code. It is the same design,
same seeds, same windows and same estimators as v0.2.0, run over a revised event
inventory. The inventory changed because district assignment was corrected:

* the municipality gazetteer was rebuilt from 142 to 753 local units;
* an explicit "<X> district" phrase in the body now outranks the filing
  dateline, which frequently names a neighbouring bureau;
* a place written inside a home-address attribution ("the deceased ... of
  Chandrpur Municipality-1, Rautahat", "सिन्धुपाल्चोक जिल्लाको मेलम्ची घर भएका
  चालक") is no longer read as the event location; and
* an already-established district is no longer overridden by a contradicting
  municipality.

Measured on the 123 labelled rows of the development set, district accuracy rose
from 0.813 to 0.862 with **no labelled row regressing**. Canonical events fell
3,114 → 2,950, almost entirely because better municipality resolution merged
clusters that were previously split. Full account and the ablation:
`docs/DISTRICT_ASSIGNMENT_2026-09-03.md`.

### The headline result moved, and the association did not

| Quantity | v0.2.0 | v0.3.0 |
|---|---|---|
| Canonical events read | 3,114 | 2,950 |
| Primary case-days / matched controls | 1,514 / 6,196 | 1,471 / 6,049 |
| Development-selected window | 5 days | 5 days |
| **Threshold** | **45.4 mm** | **51.6 mm** |
| Threshold 95% CI (development) | 26.8–72.1 mm | 27.1–71.7 mm |
| Temporal-test AUC | 0.693 (0.657–0.722) | 0.676 (0.638–0.706) |
| Sensitivity | 0.509 | 0.447 |
| Specificity | 0.764 | 0.785 |
| Matched-sample precision | 0.359 | 0.350 |
| Conditional OR per 10 mm (R5, all years) | 1.227 (1.193–1.261) | 1.215 (1.185–1.246) |
| Within-stratum concordance (all years, R5) | 0.671 | 0.662 |
| Dev→test AUC gap | +0.051 | +0.035 |
| Co-primary R3 strictly antecedent | 19.1 mm, AUC 0.664 | 20.0 mm, AUC 0.652 |
| Unmatched cases | 192 (12.7%) | 185 (12.6%) |
| Duplicate control rows | 20.1% | 18.7% |

The two thresholds are not statistically distinguishable — each lies inside the
other's bootstrap interval — and the conditional odds ratio, the estimator the
matched design implies, is unchanged within its confidence interval.

**What did change is the apparent stability of the cutpoint.** v0.2.0 reported
that leave-one-year-out selected 45.38–45.42 mm in all twelve folds. Under
v0.3.0 the same procedure spans 37.5–51.6 mm. The earlier tightness was a
property of that inventory, not of the rainfall–landslide relationship. Any
statement that survives this release must therefore treat the cutpoint as a
research estimate with a wide interval, never as an operational trigger — which
is what the manuscript already says, now with direct evidence behind it.

### Consequence for the inventory release

These are classifier changes, and `docs/FINAL_RELEASE.md` requires a new locked
test version after any classifier change. Inventory **v0.4.0 remains the current
inventory release**; the rebuilt inventory is working output only. Locked test
set **v7** (395 rows, seed 20260903, zero overlap with prior evaluation sets) has
been drawn and awaits labelling. Extraction-accuracy figures from locked v6
describe the previous extractor and must not be quoted beside v0.3.0 results
without saying so.

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
