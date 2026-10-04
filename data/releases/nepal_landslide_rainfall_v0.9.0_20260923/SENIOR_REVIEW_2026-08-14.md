# Senior scientific and technical review

**Project:** Media-reported landslide occurrence and antecedent rainfall in Nepal:
a district-day threshold analysis, 2015–2026
**Review date:** 2026-08-14
**Reviewed artefacts:** repository code, `config.yaml`, `docs/`, `data/outputs/`,
frozen releases `nepal_landslide_inventory_v0.4.0_v6_20260810` and
`nepal_landslide_rainfall_v0.1.0_20260813`, 553-test suite.
**Verification method:** every number below was recomputed from the project files
in a clean environment, not taken from the project's own summaries.

---

## 0. Verification of the current state

| Check | Result |
|---|---|
| Full test suite (`pytest`) | 553 passed, 0 failed |
| Analysis stage re-run from scratch | reproduces all headline results exactly (R5, 45.4 mm, test AUC 0.693, sens 0.509, spec 0.764) |
| Inventory release v0.4.0 manifest | 12/12 file checksums valid; bundle lock `3ed1d90c…` confirmed |
| Rainfall release v0.1.0 manifest | 16/16 file checksums valid; bundle lock `b22e9008…` confirmed |
| Working `canonical_events_final.csv` vs frozen copy | byte-identical (SHA-256 `5a8010a2…`) |
| Casualty fields | `deaths`/`missing`/`injured` blank where unknown (2,722 / 2,931 / 2,967 rows) — the "never impute zero" rule is genuinely honoured |
| Rainfall coverage | 323,323 rows = 77 districts × 4,199 days, zero incomplete days — confirmed |

**The project is in good shape.** Reproducibility discipline, release checksumming,
frozen-label hygiene, and separation of external evidence from the canonical
inventory are all better than typical for work at this stage. What follows is a
critique of the *inference*, not of the engineering.

---

## 1. What is scientifically strong

1. **The design is prespecified and the temporal holdout was respected.** The
   3-day window had a marginally higher *test* AUC (0.694 vs 0.693) and was
   correctly not substituted. That is the single clearest signal of methodological
   integrity in the project.
2. **Matching on district × calendar month × year** is the right instinct. It
   removes the dominant confounders (place, season, year) by design rather than by
   adjustment, and it avoids the common error of comparing monsoon event days with
   dry-season non-event days.
3. **Case-day collapsing.** Multiple canonical events in one district-day become
   one case-day, so heavily reported days do not receive extra statistical weight.
   Correct.
4. **Missing rainfall is never coded as zero**, and 84 otherwise-eligible events
   after the CHIRPS Final cut-off were excluded rather than joined to partial data.
5. **The threshold is consistently framed as a research result, not an operational
   warning threshold** — in the code, the JSON report, the protocol, and the
   manuscript.
6. **District-clustered bootstrap** rather than a row-level bootstrap.
7. **Zero heavy dependencies.** The whole analysis is pure Python + PyYAML. This
   is a real reproducibility asset and should be preserved.

---

## 2. Critical issues

These three change how the result must be interpreted. All are supported by
recomputation.

### C1 — The temporal holdout is confounded with a change of media sources and language

This is the most serious issue in the project.

Canonical events by representative source and year (recomputed):

| Source | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| himalayan-times | 37 | 70 | 41 | 22 | 16 | 34 | 12 | 8 | 1 | 7 | 11 | 1 |
| deshsanchar | 2 | 0 | 1 | 38 | 44 | 30 | 92 | 104 | **0** | **0** | **0** | **0** |
| rajdhani | 0 | 0 | 0 | 1 | 0 | 53 | 30 | 25 | 26 | 27 | **0** | **0** |
| nepalpress | 0 | 0 | 0 | 0 | 0 | 0 | 46 | 42 | 60 | 107 | 62 | 34 |
| online-khabar | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 26 | 84 | 42 | 21 |
| ratopati | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 19 | 33 |
| ekantipur | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 6 |

Article-level language routing per year: 243 EN / 45 NP in 2015 versus
415 EN / 1,282 NP in 2024.

The "development" period (2015–2022) is therefore an English-media-weighted
inventory built largely from *himalayan-times*, *myrepublica*, *deshsanchar* and
*rajdhani*; the "temporal test" period (2023–2026) is a Nepali-media-weighted
inventory built largely from *setopati*, *nepalpress*, *ujyaalo*, *online-khabar*
and *ratopati*. **The split at 2022-12-31 is not only a split in time — it is a
split in the reporting instrument.**

The consequence is visible in the results and is currently unremarked in the
manuscript: **test AUC exceeds development AUC for every one of the four windows.**

| Window | Development AUC | Temporal-test AUC |
|---|---|---|
| R1 | 0.613 | 0.647 |
| R3 | 0.642 | 0.694 |
| R5 | 0.642 | 0.693 |
| R7 | 0.635 | 0.685 |

A held-out period that outperforms the training period, uniformly, is not
evidence of good generalization; it is evidence that the two periods are not
exchangeable. Any competent reviewer will ask about this. The manuscript reports
the development AUCs in §3.1 but never draws the comparison.

Recomputing the underlying cause: within their own matched strata, later-year
cases sit in *drier* district-months (median all-day R5 in case strata: 46.8 mm in
2016, 30.1 mm in 2022, 31.5 mm in 2025) while case-day rainfall stays near 50 mm.
Broader reporting in later years captures events in marginal, drier settings where
a wet day stands out more sharply against its own month — mechanically sharpening
the within-stratum contrast.

**Verdict (updated after implementation, 2026-08-14).** I built the balanced
source panel this finding called for and ran it. Restricting cases to the seven
publishers contributing ≥30 canonical records on *both* sides of the cut-off
(`myrepublica`, `nagarik`, `nepalpress`, `onlinekhabar-en`, `rajdhani`,
`setopati`, `ujyaalo`) gives a temporal-test AUC of **0.696** against the primary
0.693, and the development-to-test gap is **unchanged** at +0.049.

**Publisher turnover therefore does not explain the result.** The strong version
of this criticism is refuted by the data, and that refutation is itself a
valuable addition to the paper — it is the single best answer to the reviewer
question this section anticipates.

What survives is the weaker and still-necessary version: the +0.03 to +0.05
development-to-test gap is real, present in all nine designs, and was unremarked.
It also survives strict matched sets (+0.046), higher date confidence (+0.041)
and road-obstruction exclusion (+0.050). The observable explanation is case-mix —
later-period case-days sit in drier district-months (median all-day 5-day
accumulation across case strata ≈40 mm in 2015–2020 against ≈30 mm in 2022–2025)
while case-day rainfall stays near 50 mm, sharpening the within-stratum contrast.
The claim of "temporal transferability" must still be replaced with a bounded
claim, but the bound comes from the leave-one-year-out distribution in §4 rather
than from a publisher confound.

### C2 — The reported "antecedent" rainfall includes rain that may have fallen *after* the landslide

Windows R1/R3/R5/R7 end **on and include** the reported event day. CHIRPS daily is
a 24-hour total, so for a landslide that fails at, say, 09:00, the event-day value
includes the remaining 15 hours of rainfall. Media-derived event days carry no
time-of-day information, so the fraction of the event-day total that postdates
failure is unknown and unknowable in this design.

The code already computes strictly-antecedent windows (`r{w}_lag1_mm`, ending the
day *before* the reported event). **They are written to the CSVs and then never
analysed.** Recomputing them:

| Predictor | Development AUC | Temporal-test AUC | Youden threshold |
|---|---|---|---|
| R5 including event day | 0.642 | 0.693 | 45.4 mm |
| **R5 strictly antecedent** | **0.618** | **0.662** | **43.7 mm** |
| R3 including event day | 0.642 | 0.694 | 31.6 mm |
| **R3 strictly antecedent** | **0.622** | **0.664** | **19.1 mm** |

Median event-day rainfall is 7.35 mm on case days versus 1.13 mm on control days —
so roughly ΔAUC ≈ 0.03 of the headline discrimination is carried by the event day
itself.

This matters for interpretation, not for validity: the current result is a
*concurrent* rainfall association, and the strictly-antecedent result is the only
one that bounds what could in principle be known *before* a failure. Both should be
reported, and the distinction should be explicit.

**Note that the date-shift sensitivity analyses do not cover this.** Shifting the
event date by −1 day moves the whole window and changes which case-days exist;
excluding the event day from a fixed window is a different question.

### C3 — A matched design analysed with unmatched statistics, plus two structural defects in the control sample

Recomputed from `event_antecedent_rainfall.csv` and `rainfall_controls.csv`:

- **192 of 1,514 cases (12.7 %) have zero matched controls.** Controls per case:
  5 controls → 1,150 cases; 4 → 54; 3 → 37; 2 → 38; 1 → 43; **0 → 192**.
  These cases are not dropped — they enter the pooled ROC as unmatched positives.
  They are also not missing at random: they are exactly the district-months so
  dense with reported events that the ±7-day buffer consumed the whole pool, i.e.
  the wettest, most active periods.
- **20.1 % of control rows are repeated district-days.** 6,196 control rows cover
  only 4,948 distinct district-days; 800 district-days are reused, one of them
  8 times. Controls are drawn independently per case from a shared stratum pool,
  so overlap is expected and heavy. Duplicated rows carry identical rainfall and
  are counted as independent observations.
- **The analysis then discards the matching entirely**: AUC, sensitivity and
  specificity pool all rows, and the reported effect measure is a cutpoint rather
  than a within-stratum association.

To be fair to the current analysis, I checked whether ignoring the matching
actually distorts the headline: within-stratum concordance (probability a case
exceeds its own matched controls) is 0.650 in development and 0.703 in test,
against pooled AUCs of 0.642 and 0.693. **The pooled estimate is close to the
conditional one, so the headline number is not materially wrong.** But the
*estimator is not the one the design calls for*, no odds ratio is reported, and
the two structural defects above are undocumented.

---

## 3. Important but non-critical issues

| # | Issue | Evidence |
|---|---|---|
| I1 | `rainfall_analysis_report.json` embeds absolute paths (`/Users/aayush/Library/CloudStorage/Box-Box/…`). A checksummed release that hard-codes one machine's filesystem is not portable. | report lines 4–5 |
| I2 | Output floats are not rounded, so summation order makes byte-level output machine-dependent (`46.121096` vs `46.121095999999994` on re-run). Bundle-lock hashes will not reproduce across platforms even when the science is identical. | verified by re-running on Linux vs the macOS-generated files |
| I3 | The threshold 95 % CI (26.8–72.1 mm) is estimated in *development* data but is printed inside the `primary_temporal_test_result` block, where it reads as a test-set interval. | report lines 246–248 |
| I4 | No leave-one-year-out or spatially held-out validation, so the reader cannot tell whether AUC 0.693 is typical or a favourable draw. **It is a favourable draw** — see §4. | recomputed |
| I5 | No season-stratified result. Matching on calendar month controls season, but it also hides that the threshold is entirely a monsoon quantity. Recomputed: monsoon (JJAS) Youden threshold 45.4 mm, test AUC 0.687; non-monsoon threshold **1.5 mm**, test AUC 0.718. A single national cutpoint is not defensible across seasons. | recomputed |
| I6 | Descriptive analysis is thin for a paper whose main asset is the inventory: no map, no province table, no source/language coverage table, no case-versus-control rainfall distribution figure. | `docs/` |
| I7 | 1,272 canonical event pairs share a district *and* a date (a further 1,157 pairs are 1 day apart). Only 926 of 3,114 events carry a municipality. "3,114 unique events" is a count of deduplicated *report clusters*, not of distinct physical landslides. The manuscript does not make that distinction. | recomputed |
| I8 | The district-month Spearman ρ = 0.275 is presented without adjustment for reporting effort, which is the dominant source of between-district variation in a media inventory. | manuscript §3.3 |

---

## 4. The single most useful new number: leave-one-year-out validation

Refitting the Youden cutpoint on all years but one and evaluating on the held-out
year (R5, primary sample):

| Held-out year | Cases | Threshold | AUC (incl. event day) | AUC (strictly antecedent) |
|---|---|---|---|---|
| 2015 | 45 | 45.4 | 0.573 | 0.583 |
| 2016 | 79 | 45.4 | 0.624 | 0.594 |
| 2017 | 72 | 45.4 | 0.623 | 0.643 |
| 2018 | 98 | 45.4 | 0.563 | 0.535 |
| 2019 | 82 | 45.4 | 0.672 | 0.652 |
| 2020 | 163 | 45.4 | 0.577 | 0.549 |
| 2021 | 176 | 45.4 | 0.705 | 0.673 |
| 2022 | 157 | 45.4 | 0.674 | 0.634 |
| 2023 | 135 | 45.4 | 0.677 | 0.683 |
| 2024 | 269 | 45.4 | 0.698 | 0.636 |
| 2025 | 188 | 45.4 | 0.710 | 0.687 |
| 2026 | 50 | 45.4 | 0.633 | 0.600 |

**Median 0.652, range 0.563–0.710, SD 0.053.**

Two conclusions follow, and both strengthen the paper:

1. **The headline 0.693 sits in the top quartile of the achievable year-to-year
   range.** The honest central estimate of out-of-year discrimination is ≈0.65,
   with year-to-year variation (±0.05) comparable to the width of the reported
   bootstrap CI. Reporting 0.693 alone is optimistic; reporting it *alongside* the
   LOYO distribution is defensible and more informative.
2. **The cutpoint itself is remarkably stable: 45.4 mm was selected in 11 of 12
   leave-one-year-out fits.** This is a genuinely positive, currently unreported
   result — the *threshold* replicates far better than the *discrimination* does.

---

## 5. Analyses I recommend **against** adding

Because the brief asks for justification, not volume:

- **Decision-curve analysis / net benefit.** Net benefit requires the marginal
  probability of a landslide district-day. A media-derived inventory with unknown
  and time-varying detection probability cannot identify that prevalence, and the
  sample is 1:5 by design. A decision curve computed here would be a number with no
  referent. **Declined, with the reasoning documented.**
- **Probability calibration.** In a matched case-control sample the intercept — and
  therefore absolute risk — is not identifiable. Conditional logistic regression
  gives an interpretable slope (odds ratio) but deliberately conditions the
  intercept away. **Declined; report the OR, state why calibration is not
  reportable.**
- **IMERG cross-comparison.** Scientifically valuable and explicitly worth doing,
  but requires new data acquisition against an external API. **Deferred to future
  work, flagged in limitations.**
- **Elevation / terrain effect modification.** No DEM is present in the repository
  and none can be derived from the current inputs. **Deferred.**
- **Sub-district (municipality-scale) rainfall.** Only 926 of 3,114 events carry a
  municipality, and `resources/municipalities_*.csv` is a name gazetteer with no
  geometry. Municipality polygons would have to be sourced and checksum-pinned
  first. **Deferred, with the requirement stated.**

---

## 6. Prioritised implementation plan

**Tier 1 — required before submission (changes interpretation)**

1. Add a **strictly-antecedent (event-day-excluded) analysis** as a co-primary
   result, using the already-computed lagged windows.
2. Add **conditional logistic regression** stratified by matched set, with
   district-clustered robust standard errors, reporting the odds ratio per 10 mm;
   add within-stratum concordance as the design-faithful discrimination measure.
3. Add **leave-one-year-out validation** and report the AUC distribution beside the
   single temporal-test value.
4. Add a **reporting-composition analysis** (source × year, language × year) and a
   **source-holdout sensitivity** restricted to publishers present in both periods,
   so the temporal claim can be separated from the instrument change.
   *(Implemented. Outcome: the temporal result is unchanged — see the updated
   verdict in C1.)*
5. Add **matching diagnostics** (unmatched cases, control reuse) and a **strict
   matched-set sensitivity analysis** (complete sets only, controls sampled without
   replacement within a stratum).
6. Add **monsoon / non-monsoon stratification**.

**Tier 2 — reproducibility and integrity**

7. Replace absolute paths with repository-relative paths plus input SHA-256s.
8. Round emitted numerics to fixed precision so bundle locks reproduce
   cross-platform.
9. Label the development-set provenance of the threshold CI.
10. Add district-held-out (spatial) validation.

**Tier 3 — descriptive and presentation**

11. District choropleth map, province/season/type summary tables, source and
    language coverage tables, case-versus-control rainfall distribution figure.
12. Rewrite manuscript §3–§5 around the corrected framing; add a changelog
    comparing v0.1.0 with the new release.

**Tier 4 — future work, flagged not implemented**

13. IMERG comparison; DEM-based terrain modification; municipality-scale exposure;
    prospective validation.

---

## 7. Status after implementation

All Tier 1–3 items were implemented on 2026-08-14 and released as
`nepal_landslide_rainfall_v0.2.0_20260814`; v0.1.0 is preserved. The primary
result reproduced exactly and is unchanged. Two of the three critical findings
were confirmed and acted on (C2 strictly antecedent exposure, C3 matched-sample
estimators and diagnostics). The strong form of C1 was **tested and refuted** by
the analysis it motivated; the weaker form was confirmed and is now reported.
Test suite: 553 → 592, all passing. See `RAINFALL_CHANGELOG.md`.

## 8. Bottom line

The engineering and the reproducibility discipline are strong, and the frozen
releases verify. The scientific weakness was not in the pipeline but in three
claims: that the 2023–2026 period constitutes a clean temporal validation, that
the rainfall measured is antecedent (it includes the event day), and that a
matched design had been analysed as such (it had not).

After implementation: the second and third are confirmed and corrected. The first
turned out to be more interesting than the criticism — the periods really are not
exchangeable, and test AUC really does exceed development AUC in every design, but
the cause is not the publisher turnover that first appears to explain it. Reported
performance should be read against the leave-one-year-out range (median 0.652,
0.563–0.710) rather than the single 0.693.

None of this invalidates the finding that several days of accumulated
district-scale rainfall discriminate reported landslide days. All of it changes
how strongly, and in what terms, that finding may be stated.
