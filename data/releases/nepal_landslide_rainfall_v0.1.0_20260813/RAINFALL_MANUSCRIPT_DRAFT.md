# Media-reported landslide occurrence and antecedent rainfall in Nepal: a district-day threshold analysis, 2015–2026

**Authors:** [add authors and affiliations]

## Abstract

Timely landslide inventories are difficult to assemble in mountainous regions,
while precipitation thresholds depend on the completeness and temporal accuracy
of the event record. We linked a validated bilingual media-derived inventory of
landslides in Nepal to daily Climate Hazards Group InfraRed Precipitation with
Station data (CHIRPS) to test whether antecedent district-scale rainfall
discriminated reported landslide days from matched non-event days. The source
inventory contained 3,114 canonical events reported between March 2015 and
August 2026. Primary rainfall cases required date confidence of at least 0.78,
excluded explicitly earthquake- and anthropogenic-triggered events, and
collapsed multiple events within a district-day. Daily district-mean rainfall
was complete for all 77 districts from 1 January 2015 to 30 June 2026. We
calculated 1-, 3-, 5-, and 7-day accumulations ending on the event day and
matched each case to up to five control days in the same district, month, and
year, excluding controls within seven days of any reported event. Windows and
cutpoints were selected using data through 2022 and evaluated without retuning
from 2023 onward. The development data selected a 5-day threshold of 45.4 mm
(district-clustered bootstrap 95% CI 26.8–72.1). In the temporal test set (642
case-days and 2,480 controls), this threshold produced an area under the ROC
curve of 0.693 (95% CI 0.657–0.722), sensitivity of 0.509, and specificity of
0.764. Results were similar when all dated events were included, when a higher
date-confidence requirement was applied, when road-obstruction events were
excluded, and when dates were shifted forward by one day; shifting dates back
one day reduced discrimination. Media-derived event timing combined with
satellite rainfall therefore captured a reproducible but moderate rainfall
signal. The estimated cutpoint is a research threshold at district scale, not
an operational warning threshold.

**Keywords:** landslide inventory; media mining; CHIRPS; antecedent rainfall;
rainfall threshold; Nepal; temporal validation

## 1. Introduction

Nepal experiences recurrent rainfall-triggered landslides, but assembling a
consistent event inventory across years, languages, and administrative regions
is challenging. News reports provide rapid and geographically broad evidence,
although reporting intensity and event dates may be uncertain. Rainfall
products such as CHIRPS offer a spatially consistent daily record that can be
linked to such event observations.

Automated news mining has produced national landslide inventories in Italy and
Türkiye, demonstrating both the reach of media sources and their uneven spatial
and temporal completeness. The Italian study specifically identified linkage
to rainfall thresholds as a future use of sufficiently detailed event classes.
In Nepal, earlier threshold research used historical government, newspaper,
field, gauge, or model-derived observations. Those studies established the
importance of event rainfall and antecedent wetness, but ranged from national
intensity-duration relationships to individual catchment and district models.

This study asks whether antecedent district-scale rainfall distinguishes days
with media-reported landslides from comparable non-event days. Its contribution
is not the inventory alone: it combines a separately validated media-derived
event record with a prespecified matched-control design and a temporal holdout.
The objectives were to (1) calculate antecedent rainfall over several commonly
used windows, (2) estimate a rainfall cutpoint using development years only,
(3) quantify discrimination in later years, and (4) test sensitivity to event
date confidence, date shifts, known non-rainfall triggers, and road-obstruction
reports.

## 2. Data and methods

### 2.1 Media-derived landslide inventory

We used release v0.4.0 of the Nepal landslide inventory. It contains 3,114
unique canonical events from 17 representative sources between 7 March 2015
and 9 August 2026. Events span 76 districts; Siraha had no media-derived event
but was retained in rainfall quality control. The release contains 603 events
typed as road obstructions caused by landslides. All canonical records are
single-event records with a district and event date.

The bilingual article classifier was evaluated on a frozen stratified locked
test set. Population-weighted precision was 0.742, recall 0.822, and F1 0.780.
District extraction among true headline articles had exact accuracy 0.822 and
coverage 0.927. Event-date extraction could not be reported independently
because only 18 locked-test rows had usable date truth. We therefore treated
date uncertainty explicitly rather than presenting all dates as equally
reliable.

### 2.2 Rainfall and district boundaries

Daily precipitation came from UCSB CHIRPS v2.0 Final, accessed through the
public NASA SERVIR ClimateSERV API. CHIRPS combines satellite observations and
station data at 0.05° spatial resolution and reports precipitation in mm/day.
For each day, we calculated the spatial mean over each district polygon.

District polygons came from the Open Knowledge Nepal LocalBoundaries dataset,
which contains the current 77-district structure in WGS84. The downloaded
GeoJSON was checksum-pinned. The resulting rainfall table contained 323,323
rows: 77 districts by 4,199 days from 1 January 2015 through 30 June 2026. There
were no missing district-days. The rainfall product had not yet provided final
values after 30 June 2026, so 84 otherwise eligible later events were excluded;
missing rainfall was never coded as zero.

### 2.3 Case definition and antecedent rainfall

The observational unit was a district-day. Primary cases required
`conf_date >= 0.78` and excluded events explicitly classified as earthquake- or
anthropogenic-triggered. Events with unknown trigger were retained because the
absence of an explicit rainfall statement in a report does not establish a
non-rainfall cause. Multiple canonical events on the same district-day were
collapsed to one case-day while retaining the contributing event IDs and event
count. This produced 1,514 primary case-days with complete rainfall windows.

We summed rainfall over 1, 3, 5, and 7 days ending on and including the reported
event date. We also retained equivalent windows ending one day before the
reported event for diagnostics.

### 2.4 Matched controls

For each case-day, we sampled up to five non-event control days from the same
district, calendar month, and year. Candidate controls within seven days of any
reported event in that district were excluded. Sampling used a fixed random
seed. This matching controls the broad effects of district, season, and year
without assuming equal baseline rainfall or equal media coverage across Nepal.
Dense event periods sometimes supplied fewer than five eligible controls,
yielding 6,196 primary controls overall.

### 2.5 Threshold estimation and temporal validation

Data through 31 December 2022 formed the development set. For each accumulation
window, we estimated a cutpoint that maximized Youden's J. We selected the
window with the highest development ROC area under the curve (AUC). The chosen
window and cutpoint were then evaluated without retuning in records from 1
January 2023 through 30 June 2026. We report AUC, sensitivity, specificity,
balanced accuracy, and matched-sample precision. Precision is not interpreted
as population positive predictive value because the control ratio was set by
design.

We obtained 95% intervals by resampling districts with replacement 1,000 times.
This cluster bootstrap preserves within-district dependence better than a
row-level bootstrap. The threshold interval was estimated in development data;
performance intervals were estimated in the untouched temporal test set.

### 2.6 Sensitivity and secondary analyses

Prespecified sensitivity variants used all dated events, a date confidence of
at least 0.80, event dates shifted by −1 or +1 day, inclusion of known
non-rainfall triggers, and exclusion of road-obstruction events. Each variant
selected its window and cutpoint in development years before temporal testing.
As a secondary descriptive analysis, we calculated Spearman correlation
between complete district-month rainfall totals and reported case-day counts.
This aggregate association was not interpreted as a threshold.

## 3. Results

### 3.1 Primary threshold

The primary development sample contained 872 case-days and 3,716 matched
controls. Development AUC values were 0.613, 0.642, 0.642, and 0.635 for the
1-, 3-, 5-, and 7-day windows, respectively. The 5-day window was selected,
although its development AUC exceeded the 3-day value by only 0.0003. Its
Youden cutpoint was 45.4 mm (95% CI 26.8–72.1), indicating substantial
cutpoint uncertainty even though the window-level signal was reproducible.

The temporal test set contained 642 case-days and 2,480 controls. At the frozen
45.4-mm threshold, 327 cases and 585 controls exceeded the cutpoint, while 315
cases and 1,895 controls did not. Test AUC was 0.693 (95% CI 0.657–0.722),
sensitivity 0.509 (95% CI 0.449–0.567), specificity 0.764 (95% CI
0.718–0.809), and balanced accuracy 0.637 (95% CI 0.611–0.661). Matched-sample
precision was 0.359 (95% CI 0.305–0.414).

The 3-day window produced a slightly higher descriptive test AUC of 0.694, but
it was not substituted post hoc because the 5-day window had been selected in
development data. Across all four windows, temporal-test AUC ranged from 0.647
to 0.694.

### 3.2 Sensitivity analyses

The 5-day window was selected in six of seven designs. Using all dated events
gave a test AUC of 0.689 at 51.6 mm. Requiring date confidence of at least 0.80
gave AUC 0.686 at the same 45.4-mm primary cutpoint. Shifting event dates one
day forward gave AUC 0.692 at 47.1 mm. Including known non-rainfall triggers
reduced AUC to 0.679. Excluding road-obstruction events retained AUC 0.690 but
raised the cutpoint to 54.4 mm and reduced sensitivity to 0.416. Shifting event
dates one day backward selected a 3-day, 20.0-mm threshold and reduced AUC to
0.664. These patterns support a rainfall association while also showing that
reported event timing affects the estimated cutpoint.

### 3.3 District-month association

Across complete district-month observations, the Spearman correlation between
monthly rainfall total and reported case-day count was 0.275. The modest
positive association is consistent with the event/control analysis, but the
aggregate coefficient also reflects zero-event districts/months, reporting
intensity, and spatial smoothing.

**Figure 1.** Temporal-test ROC curves for the four primary antecedent windows
and test AUC under each prespecified sensitivity design. The development period,
not the temporal test set, selected each displayed sensitivity window. Source:
`data/outputs/rainfall_results_figure.svg`.

## 4. Discussion

Antecedent CHIRPS rainfall showed moderate ability to discriminate
media-reported landslide district-days in Nepal. The primary result favored a
5-day accumulation, but 3- and 5-day development AUC values were essentially
tied and the cutpoint confidence interval was wide. The defensible conclusion
is therefore not that 45.4 mm is a universal physical threshold. Rather,
several days of accumulated district-scale rainfall contain useful information
about the occurrence of media-reported landslides, and that information
generalized moderately to later years.

The analysis gained credibility from separating development and temporal-test
periods. Selecting the best test-period window would have produced a slightly
higher 3-day AUC but an optimistically chosen result. The matched design also
avoided comparing monsoon event days with arbitrary dry-season controls.

The sensitivity analyses clarify the role of inventory uncertainty. Results
were stable when the date-confidence requirement changed and when dates were
shifted forward, but weaker when shifted backward. Including known earthquake
and anthropogenic triggers diluted rainfall discrimination as expected.
Road-obstruction reports did not explain the overall AUC, although removing
them changed the cutpoint and sensitivity.

Our 45.4-mm 5-day cutpoint should not be compared numerically as though it were
equivalent to earlier Nepal thresholds. Dahal and Hasegawa derived a lower-bound
intensity-duration relationship from 193 rainfall-linked landslides spanning
1951–2006 and reported high risk above 144 mm of daily precipitation. Gabet and
colleagues found interacting seasonal and daily thresholds in one Annapurna
catchment. A Kavre study found stronger association with 3-day antecedent
rainfall than longer windows, whereas a physically based Rasuwa model favored
15-day antecedent rainfall. Our outcome, district-mean exposure, control
sampling, study period, and statistical objective differ from each of these.
The present cutpoint measures discrimination in a media-derived district-day
sample; it does not estimate a physical lower boundary for slope failure.

## 5. Limitations

First, news coverage is not a complete census of landslides. Accessibility,
casualties, road importance, language, and publisher presence influence which
events appear. Second, event-date extraction lacked enough locked-test truth
for a reportable standalone accuracy estimate. Confidence restrictions and
date-shift analyses reduce but do not eliminate this uncertainty. Third,
district-mean CHIRPS rainfall smooths local convective extremes and topographic
gradients; exposure at an individual failure location may differ substantially.
Fourth, control days may include unreported landslides. Such contamination
would generally reduce measured discrimination. Fifth, the empirical
case-control cutpoint is not a calibrated warning threshold and should not be
used operationally without slope-level locations, independent event data,
rain-gauge/IMERG comparison, and prospective validation.

## 6. Conclusions

A validated media-derived inventory linked to daily satellite rainfall revealed
a temporally transferable, moderate antecedent-rainfall signal for reported
landslide occurrence in Nepal. A development-selected 5-day accumulation of
45.4 mm achieved test AUC 0.693, with results broadly stable under major
sensitivity variants. The workflow demonstrates how web-derived hazard records
can support reproducible rainfall analysis while retaining explicit uncertainty
about reporting, date assignment, spatial scale, and threshold interpretation.

## Data and code availability

The frozen inventory release is
`nepal_landslide_inventory_v0.4.0_v6_20260810`. Rainfall acquisition and
analysis are implemented in `scripts/download_chirps_climateserv.py` and
`src/landslide_inventory/analysis/`. Configuration, checksums, tests, joined
case/control tables, complete threshold metrics, and machine-readable reports
are included in the project workspace. Public redistribution of source article
text should follow each publisher's terms; the derived event inventory contains
source URLs and extracted fields.

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
   *Water*. 2022;14(24):4074.
   https://doi.org/10.3390/w14244074
9. Franceschini R, Rosi A, Catani F, Casagli N. Exploring a landslide inventory
   created by automated web data mining: the case of Italy. *Landslides*.
   2022;19:841–853. https://doi.org/10.1007/s10346-021-01799-y
10. Najatishendi E, Görüm T, Fidan S, Şanlı FB. Generating landslide archive
    inventories for Türkiye using web scraping and natural language processing
    techniques. *Natural Hazards*. 2026;122:27.
    https://doi.org/10.1007/s11069-025-07753-8
