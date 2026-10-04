# Media-reported landslide occurrence and antecedent rainfall in Nepal: a district-day threshold analysis, 2015–2026

**Authors:** [add authors, affiliations, contributions, funding, competing
interests and any ethics or data-sharing declarations before submission]

**Analysis version:** 0.2.0 (2026-08-14). Supersedes v0.1.0, which is preserved
as a historical baseline. Primary results are unchanged; see
`RAINFALL_CHANGELOG.md`.

## Abstract

Timely landslide inventories are difficult to assemble in mountainous regions,
and precipitation thresholds depend on the completeness and temporal accuracy of
the event record. We linked a validated bilingual media-derived inventory of
landslides in Nepal to daily Climate Hazards Group InfraRed Precipitation with
Station data (CHIRPS) to test whether antecedent district-scale rainfall
discriminates reported landslide days from matched non-event days. The source
inventory contained 3,114 canonical event records reported between March 2015 and
August 2026. Primary cases required date confidence of at least 0.78, excluded
explicitly earthquake- and anthropogenic-triggered events, and collapsed multiple
records within a district-day. Daily district-mean rainfall was complete for all
77 districts from 1 January 2015 to 30 June 2026. We matched each of 1,514
case-days to up to five control days in the same district, calendar month and
year, excluding controls within seven days of any reported event. Windows and
cutpoints were selected using data through 2022 and evaluated without retuning
from 2023 onward. The development data selected a 5-day accumulation with a
45.4 mm cutpoint (district-clustered bootstrap 95% CI 26.8–72.1). In the temporal
test set (642 case-days, 2,480 controls) this produced an area under the ROC
curve of 0.693 (95% CI 0.657–0.722), sensitivity 0.509 and specificity 0.764.
Because windows ending on the reported event day can contain rain that fell after
failure, we report a co-primary strictly antecedent analysis: a 3-day
accumulation ending the previous day gave a 19.1 mm cutpoint and test AUC 0.664
(95% CI 0.628–0.697). Conditional logistic regression within matched sets gave an
odds ratio of 1.23 per 10 mm of 5-day rainfall (95% CI 1.19–1.26).
Leave-one-year-out refitting placed held-out AUC at a median of 0.652 (range
0.563–0.710), so the prespecified temporal-test value is a favourable draw; the
cutpoint itself was far more stable, selected at 45.4 mm in 11 of 12
year-holdouts. Results were robust to date confidence, date shifts,
road-obstruction exclusion, restriction to continuously reporting publishers, and
strictly matched control sampling. The 45.4 mm figure is a monsoon-season
research cutpoint at district scale; the non-monsoon optimum is an order of
magnitude lower, and neither is an operational warning threshold.

**Keywords:** landslide inventory; media mining; CHIRPS; antecedent rainfall;
rainfall threshold; Nepal; matched case-control; temporal validation

## 1. Introduction

Nepal experiences recurrent rainfall-triggered landslides, but assembling a
consistent event inventory across years, languages and administrative regions is
challenging. News reports provide rapid and geographically broad evidence,
although reporting intensity and event dates may be uncertain. Rainfall products
such as CHIRPS offer a spatially consistent daily record that can be linked to
such event observations.

Automated news mining has produced national landslide inventories in Italy and
Türkiye, demonstrating both the reach of media sources and their uneven spatial
and temporal completeness. The Italian study specifically identified linkage to
rainfall thresholds as a future use of sufficiently detailed event classes. In
Nepal, earlier threshold research used historical government, newspaper, field,
gauge or model-derived observations. Those studies established the importance of
event rainfall and antecedent wetness, but ranged from national
intensity–duration relationships to individual catchment and district models.

This study asks whether antecedent district-scale rainfall distinguishes days
with media-reported landslides from comparable non-event days. Its contribution
is not the inventory alone: it combines a separately validated media-derived
event record with a prespecified matched-control design, a temporal holdout, and
an explicit account of what a media instrument can and cannot support. The
objectives were to (1) calculate rainfall accumulations over several commonly
used windows, both including and excluding the reported event day, (2) estimate a
cutpoint using development years only, (3) quantify discrimination in later years
and place that single estimate against the year-to-year and district-to-district
range, and (4) test sensitivity to event date confidence, date shifts, known
non-rainfall triggers, road-obstruction reports, publisher turnover and the
structure of the matched control sample.

## 2. Data and methods

### 2.1 Media-derived landslide inventory

We used release v0.4.0 of the Nepal landslide inventory. It contains 3,114
canonical records from 17 publishers between 7 March 2015 and 9 August 2026,
spanning 76 of 77 districts; Siraha had no media-derived event but was retained
in rainfall quality control. The release contains 603 records typed as road
obstructions caused by landslides, and 926 records carry a municipality.

Canonical records are deduplicated *report clusters*, not verified distinct
physical failures. 754 records share a district-day with at least one other
record, so the inventory resolves 2,360 distinct district-days. This matters for
the count but not for the analysis: the rainfall design collapses records within
a district-day to a single case-day.

The bilingual article classifier was evaluated on a frozen stratified locked test
set. Population-weighted precision was 0.742 (95% CI 0.675–0.807), recall 0.822
(0.744–0.910) and F1 0.780 (0.723–0.834). District extraction among true headline
articles had exact accuracy 0.822 and coverage 0.927. Event-date extraction could
not be reported independently because only 18 locked-test rows had usable date
truth, below the prespecified minimum of 30. We therefore treated date uncertainty
explicitly rather than presenting all dates as equally reliable.

### 2.2 Rainfall and district boundaries

Daily precipitation came from UCSB CHIRPS v2.0 Final, accessed through the public
NASA SERVIR ClimateSERV API. CHIRPS combines satellite observations and station
data at 0.05° spatial resolution and reports precipitation in mm/day. For each
day we calculated the spatial mean over each district polygon.

District polygons came from the Open Knowledge Nepal LocalBoundaries dataset,
which contains the current 77-district structure in WGS84. The downloaded GeoJSON
was checksum-pinned. The resulting rainfall table contained 323,323 rows: 77
districts by 4,199 days from 1 January 2015 through 30 June 2026, with no missing
district-days. The rainfall product had not yet provided final values after 30
June 2026, so 84 otherwise eligible later events were excluded; missing rainfall
was never coded as zero.

### 2.3 Case definition and two exposure definitions

The observational unit was a district-day. Primary cases required
`conf_date >= 0.78` and excluded events explicitly classified as earthquake- or
anthropogenic-triggered. Events with unknown trigger were retained, because the
absence of an explicit rainfall statement in a report does not establish a
non-rainfall cause. Multiple canonical records on the same district-day were
collapsed to one case-day while retaining the contributing record IDs and count.
This produced 1,514 primary case-days with complete rainfall windows.

We used two exposure definitions throughout:

- **Concurrent** (primary): rainfall summed over 1, 3, 5 and 7 days ending on and
  including the reported event date.
- **Strictly antecedent** (co-primary): the same windows ending the day *before*
  the reported event date.

The distinction is material. CHIRPS reports a 24-hour total and media-derived
event dates carry no time of day, so a concurrent window can contain rainfall
that fell after the failure. Median event-day rainfall was 7.35 mm on case-days
against 1.13 mm on control days, so the event day carries real signal, but part
of it is unusable for anticipation. The strictly antecedent result bounds what
could in principle be known beforehand. This is a different question from the
date-shift sensitivity analyses, which move the whole window rather than removing
one specific day.

### 2.4 Matched controls

For each case-day we sampled up to five non-event control days from the same
district, calendar month and year. Candidate controls within seven days of any
reported event in that district were excluded. Sampling used a fixed random seed.
This matching removes the broad effects of district, season and year by design,
without assuming equal baseline rainfall or equal media coverage across Nepal,
and avoids comparing monsoon event days with arbitrary dry-season controls. It
yielded 6,196 controls.

Two structural properties of this scheme are reported rather than concealed.
First, 192 of the 1,514 cases (12.7%) had no eligible control: these are
district-months dense enough with reported events that the ±7-day buffer consumed
the pool, so they are not missing at random. Second, controls were drawn
independently per case from a shared stratum pool, so 20.1% of control rows
repeat a district-day already used by another case (6,196 rows over 4,948
distinct district-days; one day used eight times). A prespecified
`strict_matched_sets` sensitivity analysis repeats the study on complete strata
with each control district-day used at most once.

### 2.5 Threshold estimation and temporal validation

Data through 31 December 2022 formed the development set. For each accumulation
window and each exposure definition we estimated the cutpoint maximizing Youden's
J, then selected the window with the highest development AUC, breaking ties toward
the shorter window. The chosen window and cutpoint were evaluated without retuning
in records from 1 January 2023 through 30 June 2026. We report AUC, sensitivity,
specificity, balanced accuracy and matched-sample precision. Precision is not
interpreted as a population positive predictive value because the control ratio
was set by design.

We obtained 95% intervals by resampling districts with replacement 1,000 times.
This cluster bootstrap preserves within-district dependence better than a
row-level bootstrap. The threshold interval was estimated in development data and
is labelled as such in every emitted row; performance intervals were estimated in
the untouched temporal test set.

### 2.6 Design-faithful and resampled analyses

Because the design is matched, we also report the estimators the design implies.
Conditional logistic regression stratified by matched set conditions the stratum
intercepts away, so district, calendar month and year are removed by construction;
standard errors use a district-clustered sandwich, and the odds ratio is reported
per 10 mm. Within-stratum concordance — the probability that a case exceeds a
control from its own matched set — is the matched analogue of AUC.

Absolute risk, probability calibration and decision-curve net benefit are
deliberately not reported. All three require the marginal probability of a
landslide district-day. A media-derived inventory has an unknown and time-varying
detection probability, and the analytic sample is 1:5 by design, so those
quantities are not identifiable here and any value we printed would have no
referent.

To place the single temporal-test estimate in context we refitted the cutpoint
without each calendar year in turn and scored that year (leave-one-year-out), and
without each of five deterministic district groups and scored that group (spatial
holdout, assigned round-robin over sorted district names, so it depends on no
seed). No method choice was made on the basis of either scheme.

### 2.7 Sensitivity and secondary analyses

Prespecified sensitivity variants used all dated events; a date confidence of at
least 0.80; event dates shifted by −1 or +1 day; inclusion of known non-rainfall
triggers; exclusion of road-obstruction events; a balanced source panel; and
strict matched sets. Each variant selected its own window and cutpoint in
development years, under both exposure definitions, before temporal testing.

The **balanced source panel** addresses a specific threat: the two study periods
draw on partly different publishers, so a temporal contrast could reflect a change
in the reporting instrument rather than in time. We restricted cases to publishers
contributing at least 30 canonical records on both sides of the development
cut-off, a rule applied to the data at run time rather than to a hard-coded list.

As a secondary descriptive analysis we calculated Spearman correlation between
complete district-month rainfall totals and reported case-day counts, reported
both pooled and within the monsoon. This aggregate association was not interpreted
as a threshold. Season-stratified models were fitted separately inside and outside
the June–September monsoon; because matching already balances calendar month,
this tests whether a single year-round cutpoint is meaningful rather than
adjusting for confounding.

## 3. Results

### 3.1 Inventory description

Reported events concentrate in the middle hills. Bagmati contributed 1,226
canonical records (556 primary case-days), Gandaki 618 (311), Lumbini 388 (186),
Koshi 310 (155), Sudurpashchim 280 (149), Karnali 279 (150) and Madhesh 13 (7).
Seasonality is strong: 77.6% of records fall in June–September, with July the
modal month (Figure 3A).

Reporting effort is not stationary. Across the study period 17.9% of development
records come from publishers absent from the test period, and 17.0% of test
records come from publishers absent from development. The article-level language
mix shifted from 243 English and 45 Nepali articles in 2015 to 415 English and
1,282 Nepali in 2024. Annual record counts therefore must not be read as a
landslide trend, and we do not present them as one.

### 3.2 Primary and co-primary thresholds

The primary development sample contained 872 case-days and 3,716 matched controls.
Development AUC values for the concurrent exposure were 0.613, 0.642, 0.642 and
0.635 for the 1-, 3-, 5- and 7-day windows. The 5-day window was selected, although
its development AUC exceeded the 3-day value by only 0.0003. Its Youden cutpoint
was 45.4 mm (development bootstrap 95% CI 26.8–72.1), indicating substantial
cutpoint uncertainty even where the window-level signal was reproducible.

The temporal test set contained 642 case-days and 2,480 controls. At the frozen
45.4 mm threshold, 327 cases and 585 controls exceeded the cutpoint while 315
cases and 1,895 controls did not. Test AUC was 0.693 (95% CI 0.657–0.722),
sensitivity 0.509 (0.449–0.567), specificity 0.764 (0.718–0.809) and balanced
accuracy 0.637 (0.611–0.661). Matched-sample precision was 0.359 (0.305–0.414).

The co-primary strictly antecedent analysis selected a 3-day window with a 19.1 mm
cutpoint and gave test AUC 0.664 (95% CI 0.628–0.697), sensitivity 0.564 and
specificity 0.685. Removing the reported event day therefore costs about 0.03 of
AUC. The concurrent result is a *concurrent* rainfall association; the strictly
antecedent result is the part of it that could precede a failure.

The 3-day concurrent window produced a slightly higher descriptive test AUC of
0.694, but it was not substituted post hoc because the 5-day window had been
selected in development data. Across all four concurrent windows, temporal-test
AUC ranged from 0.647 to 0.694.

### 3.3 Within-matched-set association

Conditional logistic regression across all years gave an odds ratio of 1.227 per
10 mm of 5-day concurrent rainfall (95% CI 1.193–1.261, district-clustered),
using the 1,322 strata with at least one control. The strictly antecedent 3-day
odds ratio was 1.221 (1.188–1.255). Within-stratum concordance was 0.650 in
development and 0.703 in the temporal test for the concurrent exposure, and 0.627
and 0.671 for the strictly antecedent exposure.

Within-stratum concordance tracks the pooled AUC closely (0.650 against 0.642;
0.703 against 0.693), which indicates that the pooled ROC is not materially
distorted by the matched structure. The odds ratio adds what a cutpoint cannot
express: a graded association rather than a dichotomy.

### 3.4 Held-out validation and the development-to-test gap

Temporal-test AUC exceeded development AUC for every window and for every one of
the nine designs, by +0.030 to +0.053. This pattern is not evidence of good
generalization; it indicates that the two periods are not exchangeable.

The most obvious explanations do not account for it. It survives restriction to
the balanced source panel (+0.049), strict matched sets (+0.046), a higher date
confidence requirement (+0.041) and exclusion of road obstructions (+0.050). The
observable difference is case-mix: later-period case-days sit in drier
district-months (median all-day 5-day accumulation across case strata ≈40 mm in
2015–2020 against ≈30 mm in 2022–2025) while case-day rainfall stays near 50 mm,
so the within-stratum contrast is sharper. Broader reporting in later years
reaches events in marginal, drier settings where a wet day stands out more.

Leave-one-year-out refitting places held-out AUC at a median of 0.652, range
0.563–0.710, SD 0.053 for the concurrent exposure (Figure 4A). The prespecified
temporal-test value of 0.693 sits in the top quartile of that range, so it should
be read as a favourable draw rather than as the central estimate. Spatial holdout
across five district groups is tighter: median 0.667, range 0.640–0.677, SD 0.016
(Figure 4B), indicating that discrimination transfers across places more reliably
than across years.

The cutpoint behaves very differently from the discrimination. Leave-one-year-out
refits selected 45.38–45.42 mm in all twelve folds, and spatial folds ranged only
37.5–48.0 mm. The threshold replicates; the achievable discrimination does not.

### 3.5 Season stratification

Fitting separately by season shows that the headline figure is a monsoon quantity.
In June–September the cutpoint was 45.4 mm with test AUC 0.687, sensitivity 0.599
and specificity 0.671. Outside the monsoon the Youden cutpoint fell to 1.5 mm with
test AUC 0.718, sensitivity 0.673 and specificity 0.598 — in a dry month, any
rainfall at all separates event days from non-event days. A single year-round
national cutpoint is therefore not defensible.

### 3.6 Sensitivity analyses

The 5-day concurrent window was selected in seven of nine designs. Using all dated
events gave test AUC 0.689 at 51.6 mm. Requiring date confidence of at least 0.80
gave 0.686 at the same 45.4 mm cutpoint. Shifting event dates one day forward gave
0.692 at 47.1 mm. Including known non-rainfall triggers reduced AUC to 0.679, as
expected. Excluding road-obstruction records retained 0.690 but raised the cutpoint
to 54.4 mm and reduced sensitivity to 0.416. Restricting to the balanced source
panel gave 0.696 at 51.6 mm. Strict matched sets gave 0.683 at a 3-day, 31.6 mm
cutpoint. Shifting event dates one day backward selected a 3-day, 20.0 mm threshold
and reduced AUC to 0.664.

These patterns support a rainfall association while showing that reported event
timing affects the estimated cutpoint, and that neither publisher turnover nor
control reuse explains the result.

### 3.7 District-month association

Across complete district-month observations the Spearman correlation between
monthly rainfall total and reported case-day count was 0.275. Within the monsoon
alone it falls to 0.129. Most of the pooled coefficient is therefore the contrast
between wet and dry months rather than a within-season signal, and the remainder
still reflects zero-event district-months, reporting intensity and spatial
smoothing. We report it as an aggregate association only.

**Figure 1.** Temporal-test ROC curves for the four concurrent windows, and
temporal-test AUC under each prespecified design. The development period, not the
test set, selected each displayed window. Source:
`data/outputs/rainfall_results_figure.svg`.

**Figure 2.** Canonical records per district and by province. Counts carry media
coverage as well as hazard. Source: `data/outputs/inventory_map_figure.svg`.

**Figure 3.** Reported records by calendar month, and rainfall distributions for
cases and matched controls. Source:
`data/outputs/rainfall_distributions_figure.svg`.

**Figure 4.** Leave-one-year-out and spatially held-out AUC for both exposures,
against the single prespecified temporal-test value. Source:
`data/outputs/rainfall_validation_figure.svg`.

## 4. Discussion

Antecedent CHIRPS rainfall shows a moderate, reproducible ability to discriminate
media-reported landslide district-days in Nepal. The defensible summary is not
that 45.4 mm is a universal physical threshold. It is that several days of
accumulated district-scale rainfall carry useful information about the occurrence
of media-reported landslides, that this information transfers moderately across
years and somewhat more reliably across districts, and that the *cutpoint* is a
considerably more stable quantity than the *discrimination*.

Three features of the analysis should shape how strongly the result is read.

First, the prespecified temporal-test AUC of 0.693 is a favourable draw. The
leave-one-year-out distribution puts the honest central estimate near 0.65, with
year-to-year variation comparable to the width of the bootstrap interval. We
report both, and would encourage other media-derived threshold studies to report
a resampled distribution rather than a single split, because a single split can
easily land at either end of this range.

Second, part of the concurrent signal is not available in advance. Excluding the
reported event day costs about 0.03 of AUC. The concurrent number is the better
description of the rainfall–landslide association as recorded; the strictly
antecedent number is the honest ceiling for anticipation at this spatial and
temporal resolution.

Third, the estimate is season-specific. The 45.4 mm cutpoint describes the
monsoon. Outside it the optimal cutpoint is 1.5 mm, which is a statement about
how easily a rainy day is distinguished in a dry month rather than about slope
mechanics.

The analysis gained credibility from separating development and temporal-test
periods and from respecting that separation when the test data would have favoured
a different window. The matched design avoided comparing monsoon event days with
arbitrary dry-season controls. Reporting the conditional odds ratio alongside the
cutpoint gives a graded effect size the cutpoint alone cannot express.

The sensitivity analyses clarify the role of inventory uncertainty. Results were
stable when the date-confidence requirement changed and when dates were shifted
forward, but weaker when shifted backward. Including known earthquake and
anthropogenic triggers diluted discrimination as expected. Road-obstruction
reports did not explain the overall AUC, although removing them changed the
cutpoint and sensitivity. Restricting to publishers reporting throughout the study
period left the result essentially unchanged, which is the strongest available
evidence that the temporal comparison is not an artefact of publisher turnover.
Removing pseudo-replication in the control sample likewise left it essentially
unchanged.

Our 45.4 mm 5-day cutpoint should not be compared numerically as though it were
equivalent to earlier Nepal thresholds. Dahal and Hasegawa derived a lower-bound
intensity–duration relationship from 193 rainfall-linked landslides spanning
1951–2006 and reported high risk above 144 mm of daily precipitation. Gabet and
colleagues found interacting seasonal and daily thresholds in one Annapurna
catchment. A Kavre study found stronger association with 3-day antecedent rainfall
than with longer windows, whereas a physically based Rasuwa model favoured 15-day
antecedent rainfall. Our outcome, district-mean exposure, control sampling, study
period and statistical objective differ from each of these. The present cutpoint
measures discrimination in a media-derived district-day sample; it does not
estimate a physical lower boundary for slope failure.

## 5. Limitations

First, news coverage is not a census of landslides. Accessibility, casualties,
road importance, language and publisher presence influence which events appear,
and the mix of publishers changes over the study period.

Second, canonical records are deduplicated report clusters rather than verified
distinct physical failures; 754 records share a district-day with another record.
The rainfall analysis is unaffected because it works at district-day resolution,
but the headline count of 3,114 should be read accordingly.

Third, event-date extraction lacked enough locked-test truth for a reportable
standalone accuracy estimate. Confidence restrictions and date-shift analyses
reduce but do not eliminate this uncertainty.

Fourth, district-mean CHIRPS rainfall smooths local convective extremes and
topographic gradients; exposure at an individual failure location may differ
substantially. Only 926 of 3,114 records carry a municipality, and no municipality
geometry is currently pinned in the project, so sub-district exposure could not be
tested.

Fifth, control days may include unreported landslides. Such contamination would
generally reduce measured discrimination, so the reported values are conservative
in that direction.

Sixth, 12.7% of cases had no eligible control, and these are concentrated in the
densest reporting periods rather than being missing at random. They contribute to
the pooled ROC as unmatched positives; the conditional analyses exclude them, and
both are reported.

Seventh, discrimination is not stationary across years, and the reason lies partly
in reporting composition rather than in climate. Any application to a new period
should expect performance within the leave-one-year-out range rather than at the
value reported for 2023–2026.

Eighth, the empirical case-control cutpoint is not a calibrated warning threshold.
Absolute risk and net benefit are not identifiable from this design and are not
reported. Operational use would require slope-level locations, independent event
data, rain-gauge or IMERG comparison, terrain covariates, and prospective
validation.

## 6. Conclusions

A validated media-derived inventory linked to daily satellite rainfall reveals a
moderate antecedent-rainfall signal for reported landslide occurrence in Nepal. A
development-selected 5-day accumulation of 45.4 mm achieved a temporal-test AUC of
0.693, with a leave-one-year-out median of 0.652 and a within-matched-set odds
ratio of 1.23 per 10 mm. Excluding the reported event day reduces the signal to a
3-day, 19.1 mm cutpoint at AUC 0.664, which bounds what could be known before
failure. Results were stable under nine prespecified designs, including
restriction to continuously reporting publishers and to strictly matched controls.
The workflow demonstrates how web-derived hazard records can support reproducible
rainfall analysis while retaining explicit uncertainty about reporting, date
assignment, spatial scale, season and threshold interpretation.

## Data and code availability

The frozen inventory release is `nepal_landslide_inventory_v0.4.0_v6_20260810`.
The frozen analysis release is `nepal_landslide_rainfall_v0.2.0_20260814`, which
supersedes `nepal_landslide_rainfall_v0.1.0_20260813`; both are retained. Rainfall
acquisition and analysis are implemented in
`scripts/download_chirps_climateserv.py` and
`src/landslide_inventory/analysis/`. Configuration, input checksums, tests, joined
case/control tables, complete threshold metrics, conditional models, resampled
validation and machine-readable reports are included in the release bundle.
Public redistribution of source article text should follow each publisher's terms;
the derived event inventory contains source URLs and extracted fields.

## References to complete before submission

1. Funk C, Peterson P, Landsfeld M, et al. The climate hazards infrared
   precipitation with stations—a new environmental record for monitoring
   extremes. *Scientific Data*. 2015;2:150066.
   https://doi.org/10.1038/sdata.2015.66
2. CHIRPS dataset catalog:
   https://developers.google.com/earth-engine/datasets/catalog/UCSB-CHG_CHIRPS_DAILY
3. NASA SERVIR ClimateSERV API documentation:
   https://climateserv.servirglobal.net/develop-api
4. Open Knowledge Nepal LocalBoundaries:
   https://localboundries.oknp.org/
5. Dahal RK, Hasegawa S. Representative rainfall thresholds for landslides in
   the Nepal Himalaya. *Geomorphology*. 2008;100(3–4):429–443.
   https://doi.org/10.1016/j.geomorph.2008.01.014
6. Gabet EJ, Burbank DW, Putkonen JK, Pratt-Sitaula BA, Ojha T. Rainfall
   thresholds for landsliding in the Himalayas of Nepal. *Geomorphology*.
   2004;63(3–4):131–143. https://doi.org/10.1016/j.geomorph.2004.03.011
7. Shrestha S, Pradhan PM, Shrestha HK. Assessment of rainfall-induced shallow
   landslides in Kavre District, Nepal. *SCITECH Nepal*. 2023;17(1).
   https://doi.org/10.3126/scitech.v17i1.60493
8. Guo B, Pei X, Xu M, Li T. Analyzing rainfall threshold for shallow
   landslides using physically based modeling in Rasuwa District, Nepal.
   *Water*. 2022;14(24):4074. https://doi.org/10.3390/w14244074
9. Franceschini R, Rosi A, Catani F, Casagli N. Exploring a landslide inventory
   created by automated web data mining: the case of Italy. *Landslides*.
   2022;19:841–853. https://doi.org/10.1007/s10346-021-01799-y
10. Najatishendi E, Görüm T, Fidan S, Şanlı FB. Generating landslide archive
    inventories for Türkiye using web scraping and natural language processing
    techniques. *Natural Hazards*. 2026;122:27.
    https://doi.org/10.1007/s11069-025-07753-8
11. [Add a standard reference for conditional logistic regression in matched
    case-control designs, e.g. Breslow NE, Day NE, *Statistical Methods in Cancer
    Research, Volume I: The Analysis of Case-Control Studies*, IARC, 1980.]
