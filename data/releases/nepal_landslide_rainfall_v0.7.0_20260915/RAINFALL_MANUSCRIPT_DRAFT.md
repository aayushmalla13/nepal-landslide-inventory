# Media-reported landslide occurrence and antecedent rainfall in Nepal: a district-day threshold analysis, 2015–2026

**Authors:** [add authors, affiliations, contributions, funding, competing
interests and any ethics or data-sharing declarations before submission]

**Analysis version:** 0.7.0 (2026-09-15). Supersedes v0.6.0, v0.5.0, v0.4.0,
v0.3.0, v0.2.0 and v0.1.0, all preserved as historical baselines. Version 0.7.0
is a provenance-only release: it links the unchanged v0.6.0 numerical analysis
to the checksummed human-v7 inventory release that supplied its canonical input.
Between v0.2.0 and
v0.5.0 the event inventory was corrected in two independent respects (district
assignment and casualty extraction) and the rainfall record was extended by one
month; the primary cutpoint moved from 45.4 mm to 51.6 mm. Version 0.6.0 removed
cross-case coupling from control sampling and added a paired CHIRPS-IMERG product
comparison; the primary cutpoint remained 51.6 mm. See
`RAINFALL_CHANGELOG.md`, `DISTRICT_ASSIGNMENT_2026-09-03.md` and
`CASUALTY_EXTRACTION_2026-09-03.md`.

## Abstract

Timely landslide inventories are difficult to assemble in mountainous regions,
and precipitation thresholds depend on the completeness and temporal accuracy of
the event record. We linked a validated bilingual media-derived inventory of
landslides in Nepal to daily Climate Hazards Group InfraRed Precipitation with
Station data (CHIRPS) to test whether antecedent district-scale rainfall
discriminates reported landslide days from matched non-event days. The source
inventory contained 2,885 canonical event records reported between March 2015 and
August 2026. Primary cases required date confidence of at least 0.78, excluded
explicitly earthquake- and anthropogenic-triggered events, and collapsed multiple
records within a district-day. Daily district-mean rainfall was complete for all
77 districts from 1 January 2015 to 31 July 2026. We matched each of 1,508
case-days to up to five control days in the same district, calendar month and
year, excluding controls within seven days of any reported event. Windows and
cutpoints were selected using data through 2022 and evaluated without retuning
from 2023 onward. The development data selected a 5-day accumulation with a
51.6 mm cutpoint (district-clustered bootstrap 95% CI 33.7–61.7). In the temporal
test set (669 case-days, 2,577 controls) this produced an area under the ROC
curve of 0.675 (95% CI 0.640–0.702), sensitivity 0.456 and specificity 0.772.
Because windows ending on the reported event day can contain rain that fell after
failure, we report a co-primary strictly antecedent analysis: a 3-day
accumulation ending the previous day gave a 23.7 mm cutpoint and test AUC 0.649
(95% CI 0.615–0.679). Conditional logistic regression within matched sets gave an
odds ratio of 1.22 per 10 mm of 5-day rainfall (95% CI 1.19–1.25).
Leave-one-year-out refitting placed held-out AUC at a median of 0.645 (range
0.565–0.705) and selected cutpoints between 45.3 and 45.5 mm. Results were robust
to date confidence, date shifts, road-obstruction exclusion, restriction to
continuously reporting publishers, and strictly matched control sampling. We also
report a direct test of how much the cutpoint depends on the inventory itself: a
documented revision of district assignment, which improved district accuracy on
labelled data and regressed nothing, moved the point estimate by 14%. The 51.6 mm
figure is a monsoon-season research cutpoint at district scale; the non-monsoon
optimum is far lower, and neither is an operational warning threshold.

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

We used release v0.5.0 of the Nepal landslide inventory. It contains 2,885
canonical records from 17 publishers between 7 March 2015 and 9 August 2026,
spanning 76 of 77 districts; Siraha had no media-derived event but was retained
in rainfall quality control. The release contains 603 records typed as road
obstructions caused by landslides, and 926 records carry a municipality.

Canonical records are deduplicated *report clusters*, not verified distinct
physical failures. 754 records share a district-day with at least one other
record, so the inventory resolves 2,319 distinct district-days. This matters for
the count but not for the analysis: the rainfall design collapses records within
a district-day to a single case-day.

The bilingual article classifier was evaluated on a frozen stratified locked test
set of 395 articles (v7), annotated by a human rater and scored once.
Population-weighted precision was 0.626 (95% CI 0.552–0.701), recall 0.759
(0.682–0.843) and F1 0.686 (0.624–0.750). District extraction among true headline
articles had exact accuracy 0.828 with coverage 0.922 (n=127), and event-date
extraction 0.824 with coverage 0.976 (n=83); the date figure clears the
prespecified minimum of 30 truth rows that earlier locked sets did not.

Two features of this evaluation should be read together with those numbers.

First, **annotation provenance**. Locked set v7 is the first evaluation set in
this project labelled by a person. The earlier locked set (v6) and the
development set used for tuning were both annotated by a large language model.
Those model-labelled sets gave a higher precision for the same pipeline family
(0.742, 95% CI 0.675–0.807 on v6), and we regard the human-labelled figure as
the trustworthy one: a model annotator and an extraction pipeline share failure
modes, so agreement between them overstates accuracy against human judgement. We
report v6 only to make that gap explicit, not as a performance baseline, because
the two sets differ in annotator as well as in sample and pipeline version.

Second, **what the precision loss consists of, and why the analysis unit
matters**. Under the prespecified headline definition only a single-event
article is a positive; multi-event articles and roundups are negatives. Of the
false positives, 78% are articles the annotator marked `multi` or `roundup` —
genuine Nepali landslide reports covering more than one failure — and only 8%
describe no landslide event at all. Agreement on event granularity is 0.486,
with the pipeline predicting `single` for 80% of articles against a true rate of
42%. The classifier's weakness is in counting events, not in detecting them.

Annotation reliability was measured independently on a blind,
decision-by-language-stratified subset of 120 locked-v7 articles. A second human
annotator agreed with the first on 85.0% of derived headline decisions (Cohen's
kappa 0.656) and 78.3% of event-granularity labels (kappa 0.706). Hazard-subtype
agreement was lower (71.7%; kappa 0.544). Exact district and event-date agreement
was 98.1% and 94.1%, respectively, among rows where both raters supplied a value.
These estimates precede adjudication, and the frozen v7 labels were not changed
after the comparison.

That distinction is decisive here, because the analysis unit is the district-day
rather than the article. We therefore measured event validity directly, on a
separate human-labelled sample of 100 articles drawn from the retained inventory
itself (stratified, with inclusion weights; see Data and code availability).
**95.5% of retained articles (95% CI 90.0–99.4) report a real landslide event in
Nepal**, against the 62.6% article-level headline precision. Every one of the 47
articles in that sample that the annotator judged multi-event was a real Nepali
landslide; the two figures differ almost entirely because the headline
definition additionally requires the article to describe exactly one failure.

An article reporting three landslides in a district on one day therefore yields
the same, correct district-day as one reporting a single failure, and excluding
it would remove a true case-day rather than a false one. We consequently retain
multi-event articles in the inventory, and report both measures: the strict
article-level figure for comparability with classification studies, and the
event-validity figure as the quantity relevant to this design.

### 2.2 Rainfall and district boundaries

Daily precipitation came from UCSB CHIRPS v2.0 Final, accessed through the public
NASA SERVIR ClimateSERV API. CHIRPS combines satellite observations and station
data at 0.05° spatial resolution and reports precipitation in mm/day. For each
day we calculated the spatial mean over each district polygon.

District polygons came from the Open Knowledge Nepal LocalBoundaries dataset,
which contains the current 77-district structure in WGS84. The downloaded GeoJSON
was checksum-pinned. The resulting rainfall table contained 325,710 rows: 77
districts by 4,230 days from 1 January 2015 through 31 July 2026, with no missing
district-days. Eighteen otherwise eligible events fell after the available
rainfall record and were excluded; missing rainfall was never coded as zero.

As an independent check on the choice of rainfall product, the analysis was also
run on NASA IMERG Final Run v07 over the period both products cover; see §3.8.

### 2.3 Case definition and two exposure definitions

The observational unit was a district-day. Primary cases required
`conf_date >= 0.78` and excluded events explicitly classified as earthquake- or
anthropogenic-triggered. Events with unknown trigger were retained, because the
absence of an explicit rainfall statement in a report does not establish a
non-rainfall cause. Multiple canonical records on the same district-day were
collapsed to one case-day while retaining the contributing record IDs and count.
This produced 1,508 primary case-days with complete rainfall windows.

We used two exposure definitions throughout:

- **Concurrent** (primary): rainfall summed over 1, 3, 5 and 7 days ending on and
  including the reported event date.
- **Strictly antecedent** (co-primary): the same windows ending the day *before*
  the reported event date.

The distinction is material. CHIRPS reports a 24-hour total and media-derived
event dates carry no time of day, so a concurrent window can contain rainfall
that fell after the failure. In the development split, median event-day rainfall
was 7.40 mm on case-days against 1.19 mm on control days, so the event day
carries real signal, but part
of it is unusable for anticipation. The strictly antecedent result bounds what
could in principle be known beforehand. This is a different question from the
date-shift sensitivity analyses, which move the whole window rather than removing
one specific day.

### 2.4 Matched controls

For each case-day we sampled up to five non-event control days from the same
district, calendar month and year. Candidate controls within seven days of any
reported event in that district were excluded. Sampling used a fixed random seed
and an independent deterministic random stream keyed to each case, so adding or
removing one case cannot redraw controls for unrelated cases.
This matching removes the broad effects of district, season and year by design,
without assuming equal baseline rainfall or equal media coverage across Nepal,
and avoids comparing monsoon event days with arbitrary dry-season controls. It
yielded 6,164 controls.

Two structural properties of this scheme are reported rather than concealed.
First, 200 of the 1,508 cases (13.3%) had no eligible control: these are
district-months dense enough with reported events that the ±7-day buffer consumed
the pool, so they are not missing at random. Second, controls were drawn
independently per case from a shared stratum pool, so 18.8% of control rows
repeat a district-day already used by another case (6,164 rows over 5,005
distinct district-days; one day used eight times). A prespecified
`strict_matched_sets` sensitivity analysis repeats the study on complete strata
with each control district-day used at most once.

### 2.5 Threshold estimation and temporal validation

Data through 31 December 2022 formed the development set. For each accumulation
window and each exposure definition we estimated the cutpoint maximizing Youden's
J, then selected the window with the highest development AUC, breaking ties toward
the shorter window. The chosen window and cutpoint were evaluated without retuning
in records from 1 January 2023 through 31 July 2026. We report AUC, sensitivity,
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

The primary development sample contained 839 case-days and 3,587 matched controls.
Development AUC values for the concurrent exposure were 0.614, 0.643, 0.646 and
0.636 for the 1-, 3-, 5- and 7-day windows. The 5-day window was selected, although
its development AUC exceeded the 3-day value by only 0.003. Its Youden cutpoint
was 51.6 mm (development bootstrap 95% CI 33.7–61.7), indicating substantial
cutpoint uncertainty even where the window-level signal was reproducible.

The temporal test set contained 669 case-days and 2,577 controls. At the frozen
51.6 mm threshold, 305 cases and 587 controls exceeded the cutpoint while 364
cases and 1,990 controls did not. Test AUC was 0.675 (95% CI 0.640–0.702),
sensitivity 0.456 (0.400–0.508), specificity 0.772 (0.739–0.804) and balanced
accuracy 0.614 (0.584–0.639). Matched-sample precision was 0.342 (0.290–0.396).

The co-primary strictly antecedent analysis selected a 3-day window with a 23.7 mm
cutpoint and gave test AUC 0.649 (95% CI 0.615–0.679), sensitivity 0.511 and
specificity 0.719. Removing the reported event day therefore costs about 0.03 of
AUC. The concurrent result is a *concurrent* rainfall association; the strictly
antecedent result is the part of it that could precede a failure.

The 3-day concurrent window produced a slightly higher descriptive test AUC of
0.678, but it was not substituted post hoc because the 5-day window had been
selected in development data. Across all four concurrent windows, temporal-test
AUC ranged from 0.635 to 0.678.

### 3.3 Within-matched-set association

Conditional logistic regression across all years gave an odds ratio of 1.220 per
10 mm of 5-day concurrent rainfall (95% CI 1.190–1.250, district-clustered),
using the 1,308 strata with at least one control. The strictly antecedent 3-day
odds ratio was 1.204 (1.173–1.236). Within-stratum concordance was 0.651 in
development and 0.673 in the temporal test for the concurrent exposure, and 0.618
and 0.651 for the strictly antecedent exposure.

Within-stratum concordance tracks the pooled AUC closely (0.660 against 0.675 for
the concurrent exposure; 0.632 against 0.649 for the strictly antecedent one),
which indicates that the pooled ROC is not materially
distorted by the matched structure. The odds ratio adds what a cutpoint cannot
express: a graded association rather than a dichotomy.

### 3.4 Held-out validation and the development-to-test gap

Temporal-test AUC exceeded development AUC for every sensitivity design, by
+0.015 to +0.037 for the development-selected concurrent windows. This pattern is not evidence of good
generalization; it indicates that the two periods are not exchangeable.

The most obvious explanations do not account for it. It survives restriction to
the balanced source panel (+0.020), strict matched sets (+0.028), a higher date
confidence requirement (+0.017) and exclusion of road obstructions (+0.015). The
observable difference is case-mix: later-period case-days sit in drier
district-months (median all-day 5-day accumulation across case strata ≈40 mm in
2015–2020 against ≈30 mm in 2022–2025) while case-day rainfall stays near 50 mm,
so the within-stratum contrast is sharper. Broader reporting in later years
reaches events in marginal, drier settings where a wet day stands out more.

Leave-one-year-out refitting places held-out AUC at a median of 0.645, range
0.565–0.705, SD 0.048 for the concurrent exposure (Figure 4A). The prespecified
temporal-test value of 0.675 sits above that median but within the range, so it
should be read as a mildly favourable draw rather than as the central estimate.
Spatial holdout across five district groups is tighter: median 0.656, range
0.637–0.681, SD 0.016 (Figure 4B), indicating that discrimination transfers
across places more reliably than across years.

Leave-one-year-out refits selected 45.3–45.5 mm and spatial folds selected
45.3–47.4 mm. These narrow ranges describe the current independently seeded
control design, not universal physical stability. Version 0.6.0 was introduced
because earlier shared-stream sampling coupled unrelated cases: adding or
removing one event could redraw later controls and widen or shift cutpoint ranges
for reasons unrelated to rainfall. The corrected sampler leaves the primary
51.6 mm estimate unchanged while making sensitivity comparisons interpretable.

### 3.5 Season stratification

Fitting separately by season shows that the headline figure is a monsoon quantity.
In June–September the cutpoint was 51.6 mm with test AUC 0.658, sensitivity 0.526
and specificity 0.687. Outside the monsoon the Youden cutpoint fell to 12.6 mm with
test AUC 0.722, sensitivity 0.473 and specificity 0.841. A single year-round
national cutpoint is therefore not defensible.

### 3.6 Sensitivity analyses

The 5-day concurrent window was selected in seven of nine designs. Using all dated
events gave test AUC 0.672 at 51.6 mm. Requiring date confidence of at least 0.80
gave 0.665 at a 50.5 mm cutpoint. Shifting event dates one day forward gave
0.678 at 46.9 mm. Including known non-rainfall triggers reduced AUC to 0.659, as
expected. Excluding road-obstruction records retained 0.660 but raised the cutpoint
to 54.2 mm and reduced sensitivity to 0.418. Restricting to the balanced source
panel gave 0.667 at 51.6 mm. Strict matched sets gave 0.672 at a 3-day, 31.3 mm
cutpoint. Shifting event dates one day backward selected a 3-day, 21.8 mm threshold
and gave AUC 0.658.

These patterns support a rainfall association while showing that reported event
timing affects the estimated cutpoint, and that neither publisher turnover nor
control reuse explains the result.

### 3.7 District-month association

Across complete district-month observations the Spearman correlation between
monthly rainfall total and reported case-day count was 0.276. Within the monsoon
alone it falls to 0.128. Most of the pooled coefficient is therefore the contrast
between wet and dry months rather than a within-season signal, and the remainder
still reflects zero-event district-months, reporting intensity and spatial
smoothing. We report it as an aggregate association only.

### 3.8 Independent rainfall product

To test whether the association is a property of CHIRPS, the analysis was
repeated on NASA IMERG Final Run v07 (GPM_3IMERGDF), an independent satellite
product built from passive-microwave rather than thermal-infrared retrievals.
District means were computed as unweighted means of the 0.1° cell centres falling
inside each district polygon (1,356 cells over Nepal), giving 302,302 district-days
from 1 January 2015 to 30 September 2025 with no missing days.

Because IMERG Final publishes with several months' latency, its record ends ten
months before the CHIRPS record. Comparing the two as they stand would confound
product with period, so CHIRPS was truncated to the identical window and that
truncated run, not the primary result, is the comparator. Both runs share one
case–control design — the same events, the same drawn control district-days and
the same seed — so only the rainfall values differ.

As measurements the two products agree closely in bulk. On the 302,302 common
district-days the ratio of means is stable across every exposure (1.153 at R1 and
R3, 1.152 at R5 and R7), Spearman correlation rises with window length from 0.62
daily to 0.80 at R7, and the two agree on 89.7% of district-days as to whether
51.6 mm was exceeded at R5 (Cohen's κ = 0.607).

Discrimination, however, is not equal. Because the designs are identical the
comparison is paired: each of 1,000 district-clustered bootstrap iterations
resamples districts once and scores both products on that same resample, so the
sampling variability of the design cancels rather than being carried into two
marginal intervals. IMERG discriminated better at every window in both splits, by
+0.052 to +0.063 AUC in development and +0.034 to +0.052 on the held-out temporal
test; all eight paired intervals excluded zero. At R5 on the temporal test, AUC
was 0.658 for CHIRPS and 0.693 for IMERG (difference +0.035, 95% CI +0.018 to
+0.057).

The cutpoint did not follow the products' scale factor. Window-matched ratios of
the IMERG to the CHIRPS cutpoint were 0.53 (R1), 0.89 (R3), 0.76 (R5) and 1.16
(R7) against a bulk ratio of means of 1.152, and the two runs selected different
windows in development: R5 at 51.6 mm for CHIRPS, R3 at 28.3 mm for IMERG.

The rainfall–landslide association is therefore not an artefact of CHIRPS; it is
present, and somewhat stronger, in an independent product over the same districts
and days. The specific cutpoint is product-specific. Two caveats apply: the two
runs differ in spatial aggregation as well as in product — CHIRPS district means
are ClimateSERV's area-weighted server-side means, IMERG's are unweighted cell-centre
means — so the AUC gap is an upper bound on the product effect alone; and
Bhaktapur (one grid cell) and Kathmandu (three) have almost no IMERG spatial
support and are excluded from per-district readings.

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
that 51.6 mm is a universal physical threshold. It is that several days of
accumulated district-scale rainfall carry useful information about the occurrence
of media-reported landslides, that this information transfers moderately across
years and somewhat more reliably across districts, and that the *cutpoint* is
somewhat more stable than the *discrimination* — though, as §5 sets out, it is
markedly less stable to revision of the inventory than to resampling within it.

Three features of the analysis should shape how strongly the result is read.

First, the prespecified temporal-test AUC of 0.675 is a mildly favourable draw.
The leave-one-year-out distribution puts the honest central estimate near 0.64,
with year-to-year variation comparable to the width of the bootstrap interval. We
report both, and would encourage other media-derived threshold studies to report
a resampled distribution rather than a single split, because a single split can
easily land at either end of this range.

Second, part of the concurrent signal is not available in advance. Excluding the
reported event day costs about 0.03 of AUC. The concurrent number is the better
description of the rainfall–landslide association as recorded; the strictly
antecedent number is the honest ceiling for anticipation at this spatial and
temporal resolution.

Third, the estimate is season-specific. The 51.6 mm cutpoint describes the
monsoon. Outside it the optimal cutpoint is 12.6 mm, which is a statement about
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

Our 51.6 mm 5-day cutpoint should not be compared numerically as though it were
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
distinct physical failures; 566 records share a district-day with another record.
The rainfall analysis is unaffected because it works at district-day resolution,
but the headline count of 2,885 should be read accordingly.

Third, event-date extraction lacked enough locked-test truth for a reportable
standalone accuracy estimate. Confidence restrictions and date-shift analyses
reduce but do not eliminate this uncertainty.

Fourth, district-mean CHIRPS rainfall smooths local convective extremes and
topographic gradients; exposure at an individual failure location may differ
substantially. Only 1,447 of 2,885 records (50.2%) carry a municipality. Municipality geometry
is now vendored and checksum-pinned (747 local-unit polygons), so the boundary
side of a sub-district analysis is solved; what is still missing is gridded
rainfall, since the project holds district means rather than the underlying
CHIRPS grid. Sub-district exposure therefore remains untested, and would in any
case apply only to the half of records naming a municipality — which are not a
random half.

Fifth, control days may include unreported landslides. Such contamination would
generally reduce measured discrimination, so the reported values are conservative
in that direction.

Related, and quantified here for the first time: the inventory **under-counts
multi-district days**. An estimated 29% of retained articles report several
distinct failures, and each contributes a single district-day even when the
failures span more than one district. The events themselves are real — 95.5% of
retained articles report a genuine Nepali landslide — so this is a completeness
limitation, not a validity one, and it acts in the same conservative direction
as control contamination: case-days that should exist are instead absent from
the case set, and some of them will sit among the controls. Recovering them
would require extracting several district-days from one article, which the
current pipeline does not attempt.

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
data, terrain covariates, and prospective validation. The satellite-product
comparison that also belonged on that list has since been carried out and is
reported above.

Ninth, and most consequentially for how the headline number should be read, the
cutpoint is sensitive to how it is estimated as well as to what it is estimated
from. Between versions
0.2.0 and 0.5.0 of this analysis the extraction pipeline was corrected in two
independent respects: district assignment (a filing dateline was outranking an
explicit "<X> district" phrase in the body; a victim's home address was being
read as the event location; a municipality was overriding an already-established
district) and casualty extraction. Neither change touched the analysis code, the
design, the seeds or the rainfall data. District accuracy on the 123 development-set
articles carrying district truth rose from 0.813 to 0.862 with no labelled
article regressing, so the revision is an improvement by the only measure
available at the time. Those development labels were produced by a language
model, not by a human rater; the human-labelled locked set v7 subsequently put
district exact accuracy at 0.828, close to the development figure. It nonetheless moved
the primary cutpoint from 45.4 mm to 51.6 mm, a shift of 14%.

The two estimates are not statistically distinguishable — each lies inside the
other's bootstrap interval — so this is not a contradiction. But it quantifies
something that threshold studies rarely report: how much of a published cutpoint
is a property of the rainfall–landslide relationship and how much is a property
of the particular event list. For a media-derived inventory the answer is that a
defensible, accuracy-improving revision of the event list is worth roughly as
much movement as the sampling uncertainty. Any single cutpoint from any such
study, including this one, should be read with that in mind.

Two further observations sharpen this into the strongest argument in the paper
against operational use of any specific number.

First, the cutpoint is product-dependent. Re-estimating it on NASA IMERG over an
identical period gives 39.1 mm at R5 against CHIRPS's 51.6 mm, and IMERG's own
development-selected window is R3 rather than R5. The two products agree closely
in bulk — their ratio of means is a stable 1.152 at every window — yet that bulk
agreement does not propagate to the cutpoint, because the cutpoint depends on the
joint distribution of case and control exposures near the optimum rather than on
the mean of the field.

Second, and more starkly, the cutpoint is not stable to a redraw of the matched
controls. Correcting a defect in the control sampler — which changed no data, no
product, no period and no method, only which non-event district-days were drawn —
moved the IMERG R5 cutpoint from 62.8 mm to 39.1 mm, a shift of 38%, while its
AUC moved by 0.0008. Discrimination is a stable property of the
rainfall–landslide relationship; the Youden cutpoint is a fragile statistic of a
particular sample.

The consistent element across the inventory revision, the product change and the
control redraw is the *association*, not the number. Reported AUC values move
within a narrow band while the cutpoint moves by tens of percent. Threshold
studies that publish a single value without this kind of perturbation analysis are
reporting a quantity considerably less stable than their confidence intervals
imply — and these are arguments that only versioned, reproducible releases make
it possible to state quantitatively.

## 6. Conclusions

A validated media-derived inventory linked to daily satellite rainfall reveals a
moderate antecedent-rainfall signal for reported landslide occurrence in Nepal. A
development-selected 5-day accumulation of 51.6 mm achieved a temporal-test AUC of
0.675, with a leave-one-year-out median of 0.645 and a within-matched-set odds
ratio of 1.22 per 10 mm. Excluding the reported event day reduces the signal to a
3-day, 23.7 mm cutpoint at AUC 0.649, which bounds what could be known before
failure. Results were stable under nine prespecified designs, including
restriction to continuously reporting publishers and to strictly matched controls.
The workflow demonstrates how web-derived hazard records can support reproducible
rainfall analysis while retaining explicit uncertainty about reporting, date
assignment, spatial scale, season and threshold interpretation.

## Data and code availability

The frozen inventory release is `nepal_landslide_inventory_v0.5.0_v7_20260915`.
The frozen analysis release is `nepal_landslide_rainfall_v0.7.0_20260915`, which
supersedes v0.6.0, v0.5.0, v0.4.0, v0.3.0, v0.2.0 and v0.1.0; all are retained. Rainfall
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
