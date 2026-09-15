# Nepal Landslide Inventory and Rainfall Analysis

> **Historical guide warning (2026-09-14):** This document describes the earlier
> rainfall v0.2.0 result and repeatedly reports the superseded 45.4 mm threshold.
> Do not cite its rainfall numbers. The current frozen rainfall release is
> `nepal_landslide_rainfall_v0.8.0_20260915`, with a primary CHIRPS R5 threshold
> of 51.6 mm and temporal-test AUC 0.675. Use the v0.8.0 release documents.

## Complete project explanation in plain language

**Project status:** Complete for the frozen research scope
**Inventory release:** `nepal_landslide_inventory_v0.6.0_v7_20260915`
**Rainfall-analysis release:** `nepal_landslide_rainfall_v0.8.0_20260915`
(earlier releases are retained as historical baselines)
**Study area:** Nepal
**Inventory period:** 7 March 2015 to 9 August 2026
**Rainfall period:** 1 January 2015 to 31 July 2026

---

## 1. The project in one paragraph

This project created a Nepal landslide inventory from English- and
Nepali-language news reports and then tested whether rainfall before the
reported events could help distinguish landslide days from ordinary days.
The system collected 10,203 news articles, extracted information such as the
event date and district, removed irrelevant reports and duplicates, and
produced 2,885 unique landslide-related event records. The inventory was
checked using a manually labelled test set that was kept separate from system
development. The project then linked suitable event-days to CHIRPS satellite
rainfall for all 77 districts. A five-day rainfall accumulation of about
45.4 mm was selected using older data and tested on later data. It showed a
moderate relationship with media-reported landslide occurrence, but it is not
accurate enough to be used as a public warning threshold.

## 2. The question the project answers

The main research question is:

> Can a landslide inventory extracted from Nepalese news reports be used to
> identify a meaningful relationship between antecedent rainfall and reported
> landslide occurrence?

“Antecedent rainfall” simply means rain that fell before and on the day of an
event. The project examined totals over 1, 3, 5, and 7 days.

The work has two connected parts:

1. Build and validate a media-derived landslide inventory.
2. Link reliable event-days to rainfall and estimate an empirical rainfall
   threshold.

## 3. The complete workflow

```text
News websites and archives
          |
          v
Discover and download possibly relevant articles
          |
          v
Detect language and normalize dates
          |
          v
Extract hazard, date, location, casualties, and trigger
          |
          v
Remove foreign, irrelevant, vague, and multi-event reports
          |
          v
Check locations and apply reviewed corrections
          |
          v
Merge duplicate reports of the same event
          |
          v
Final inventory: 2,885 unique event records
          |
          +-----------------------+
          |                       |
          v                       v
Manual locked-test           CHIRPS daily rainfall
validation                   for all 77 districts
          |                       |
          +-----------+-----------+
                      |
                      v
        Matched case-control rainfall analysis
                      |
                      v
        Development-period threshold selection
                      |
                      v
        Independent later-period evaluation
                      |
                      v
             Results and frozen release
```

---

## Part I — Building the landslide inventory

## 4. What data were collected?

### 4.1 Main news collection

The main inventory was built from 10,203 collected articles representing 17
news sources. The collection used both English and Nepali keywords, including
terms equivalent to “landslide,” “mudslide,” “debris flow,” “slope failure,”
“पहिरो,” and “भूस्खलन.”

The article language routing was:

| Language route | Articles |
|---|---:|
| Nepali | 7,195 |
| English | 3,008 |
| **Total** | **10,203** |

The 17 represented news sources were:

| Source | Collected articles | Events for which it became the representative source |
|---|---:|---:|
| Deshsanchar | 1,200 | 311 |
| Ekantipur | 411 | 6 |
| The Himalayan Times | 1,011 | 260 |
| The Kathmandu Post | 180 | 48 |
| Khabarhub | 1 | 1 |
| MyRepublica | 1,013 | 374 |
| Nagarik | 731 | 336 |
| Nepali Times | 12 | 3 |
| NepalPress | 967 | 351 |
| NepalPress English | 124 | 45 |
| Onlinekhabar Nepali | 378 | 173 |
| Onlinekhabar English | 600 | 154 |
| Rajdhani | 800 | 162 |
| Ratopati | 361 | 52 |
| The Rising Nepal | 65 | 26 |
| Setopati | 1,561 | 545 |
| Ujyaalo | 788 | 267 |

“Representative source” does not mean that only one article described the
event. When several articles described the same event, one was retained as the
main record and all source URLs remained attached to the duplicate cluster.

### 4.2 Historical e-paper collection

The project also recovered 736 dated Kantipur e-paper issues. An issue is a
whole newspaper edition, so it was never treated as one landslide event.
Human review identified 89 event-specific article candidates inside those
issues. Eighty-eight were successfully ingested and processed through the same
pipeline as the other news articles.

### 4.3 External evidence sources

External records were collected separately for discovery and comparison.
They were not silently added to the main news inventory. This separation is
important: a government record cannot fairly be used both to create a news
event and then to “independently” validate the same event.

The exported external-evidence file contains 17,116 rows:

| External source | Rows | Purpose |
|---|---:|---|
| BIPAD | 5,345 | Government incident evidence inside the study window |
| NASA COOLR | 796 | Scientific mapped landslide features |
| Department of Roads/Navigate | 222 | Official road information |
| Nepal Police | 15 | Official response reports |
| Police road notices | 2 | Road-obstruction evidence |
| Kantipur e-paper | 736 | Historical newspaper issues |
| Wayback Ekantipur | 5,000 | Archived URL/capture evidence |
| Common Crawl Ekantipur | 5,000 | Web-crawl evidence |

The first BIPAD collection fetched 5,745 records. The external CSV applies the
fixed project study window, which is why 5,345 BIPAD rows appear in the final
bounded export.

Archive rows and e-paper issues are evidence containers, not automatically
confirmed hazard events. Similarly, the 796 COOLR polygons are mapped
features, not 796 independent media incidents.

### 4.4 Sources not included

Some desirable sources could not be completed because they required an
unavailable export, credential, stable archive, or permitted access. These
included parts of the Armed Police Force archive, DRR Portal, ReliefWeb,
MediaCloud, DesInventar, and additional inaccessible e-paper issues. They were
excluded from the frozen scope rather than guessed or mixed into the data.

This does not invalidate the completed project. It means the result is a
large, reproducible media inventory—not a complete census of every landslide
that occurred in Nepal.

## 5. How did article discovery work?

Different websites expose their archives differently. The collector therefore
used a combination of:

- site search and tag pages;
- archive pagination;
- dated article URLs;
- Google News discovery seeds;
- web archives such as the Internet Archive and Common Crawl; and
- reviewed e-paper issues.

Some websites use readable URLs containing dates or keywords. Others use
opaque identifiers such as `/id/148/`. Opaque URLs cannot be filtered by the
URL alone, so the system must fetch the page and inspect its title and text.

Every downloaded page retained provenance information such as its URL,
publisher, retrieval time, raw publication date, parsed text, and content
hash. Re-running collection uses deterministic identifiers so the same record
is updated instead of repeatedly inserted.

## 6. What information was extracted from an article?

For each possible event, the pipeline attempted to extract:

- publication date;
- reported event date;
- language;
- district and province;
- municipality, ward, and other place names when available;
- hazard type: landslide, debris flow, or rockfall;
- whether it was an ordinary landslide or a road-obstruction report;
- article role: first report, follow-up, or retrospective;
- possible trigger: rainfall, earthquake, anthropogenic activity, or unknown;
- reported deaths, missing people, and injuries;
- confidence values; and
- the source URL and title.

A blank value means the information was not safely available. It does not mean
zero. For example, a blank death field must not be interpreted as “no deaths.”

## 7. How were dates handled?

News sites contained dates in several formats, including Gregorian dates,
Bikram Sambat dates, dates embedded in URLs, and dates written in article
text. The normalization stage converted valid dates to the common
`YYYY-MM-DD` Gregorian format.

The event date and publication date are not necessarily the same. If an
article says “a landslide occurred yesterday,” the event date is inferred
relative to publication. Date confidence records how reliable the extraction
appeared. Invalid calendar values were rejected rather than forcing a date.

The rainfall analysis used only event dates with confidence of at least 0.78
for its primary analysis. A stricter confidence threshold and one-day date
shifts were tested separately.

## 8. How were irrelevant articles removed?

Searching for landslide words also finds material that is not a usable event.
Examples include:

- political “landslide victory” metaphors;
- stock-market “landslides”;
- forecasts and risk discussions where no event happened;
- exhibitions, meetings, and policy announcements;
- foreign events;
- seasonal totals and national roundups;
- floods or avalanches without a landslide-family event; and
- articles that mention several different events without one separable event.

The pipeline separated several questions:

1. Did a real hazard event occur?
2. Was it inside Nepal?
3. Was it a landslide, debris flow, or rockfall?
4. Did the article describe one specific event?
5. Could the event location and date be extracted?

This is why an article can mention a place but still have blank event-location
fields. For example, the location of an exhibition is not the location of a
landslide if no landslide occurred.

## 9. How were locations checked?

English and Nepali place names were matched against district and municipality
gazetteers. The system distinguished the event site from misleading locations
such as:

- the Kathmandu dateline from which a story was filed;
- the hospital to which an injured person was taken;
- the victim’s home district; or
- the office issuing a statement.

The final records all have a district. Municipality is present for 1,447 of the
2,885 events; it remains blank when the article did not provide enough reliable
detail. The inventory contains events from 76 of Nepal’s 77 districts. This is
coverage of represented media events, not evidence that the remaining district
had no landslides.

## 10. How were duplicate reports merged?

One landslide may be reported by several publishers or in several follow-up
articles. Counting every article as a new event would exaggerate the number of
landslides.

The deduplication stage compared date, location, title/body similarity,
municipality, casualties, and other evidence. Reports judged to describe the
same event were placed in one cluster. The final inventory contains:

- 2,885 duplicate clusters, one per canonical event;
- 411 clusters supported by more than one source; and
- a largest cluster containing 49 related reports.

Of the final events, 2,371 had a single supporting article and the rest had two
or more related reports.

## 11. Reviewed corrections

Five records received documented human corrections after validation. These
fixed verified dates or excluded verified foreign, multi-event, or aggregate
articles. The correction table records the old value, new value, evidence,
reviewer provenance, and content hash.

These corrections are a transparent final quality-control layer. They did not
change the already frozen classifier test labels or retrospectively improve
the reported validation score.

## 12. What is in the final inventory?

The frozen inventory contains **2,885 unique event records** from 7 March 2015
through 9 August 2026.

### 12.1 Events by year

| Year | Events |
|---|---:|
| 2015 | 88 |
| 2016 | 133 |
| 2017 | 123 |
| 2018 | 180 |
| 2019 | 138 |
| 2020 | 271 |
| 2021 | 334 |
| 2022 | 347 |
| 2023 | 254 |
| 2024 | 504 |
| 2025 | 334 |
| 2026 | 179 |

These values must not be interpreted directly as a trend in physical
landslides. Older articles are harder to recover, publishers differ in archive
depth, and 2026 is incomplete.

### 12.2 Hazard and event types

| Category | Events |
|---|---:|
| Landslide | 2,720 |
| Debris flow | 135 |
| Rockfall | 30 |
| **Total** | **2,885** |

The event-use classification contains 2,298 general landslide records and 587
road-obstruction records. Road-obstruction records were retained because road
blockages are an important way landslides are reported in Nepal, but a
sensitivity analysis also tested the result after removing them.

### 12.3 Trigger labels

| Extracted trigger | Events |
|---|---:|
| Rainfall | 1,014 |
| Anthropogenic activity | 452 |
| Earthquake | 219 |
| Unknown or not stated | 1,200 |

“Unknown” is intentionally preserved. The system does not assume that every
monsoon landslide was caused by rainfall merely because it happened during the
rainy season.

### 12.4 Events by province

| Province | Events |
|---|---:|
| Bagmati | 1,226 |
| Gandaki | 618 |
| Lumbini | 388 |
| Koshi | 310 |
| Sudurpashchim | 280 |
| Karnali | 279 |
| Madhesh | 13 |

These counts reflect both landslide occurrence and media-reporting behavior.
They are not direct estimates of provincial hazard rates.

### 12.5 Casualty fields

Deaths, missing people, and injuries were extracted only when the number could
be linked to the specific event. These fields are incomplete in news reports:

| Field | Records with a nonblank value |
|---|---:|
| Deaths | 392 |
| Missing | 183 |
| Injured | 147 |

The project therefore does not present the sum of these fields as a national
casualty total. Missing values are unknown, not zero, and some reports may
update casualty counts after the first article.

---

## Part II — Checking whether the inventory works

## 13. Why manual validation was necessary

Automated extraction can make mistakes. A scientific inventory therefore needs
more than a large row count; it needs an estimate of how often the system is
right and what it misses.

The final evaluation used a locked test set. Articles were sampled from both
kept and rejected groups and from both languages. Human labels and automated
predictions were kept separate during labeling. The test set was not used to
tune the final system after its score was viewed.

The truth definition counted an article as a positive headline event only if:

- a real landslide-family event occurred;
- it occurred in Nepal;
- the hazard was a landslide, debris flow, or rockfall; and
- the article described one specific event.

Of 388 primary answers, 387 were decidable and one was excluded as genuinely
unclear.

## 14. Validation results in simple language

| Measure | Result | 95% confidence interval | Plain-language meaning |
|---|---:|---:|---|
| Precision | 0.742 | 0.675–0.807 | About 74% of articles the system called positive were truly suitable headline events. |
| Recall | 0.822 | 0.744–0.910 | The system found about 82% of the suitable events represented in the sampled article population. |
| F1 score | 0.780 | 0.723–0.834 | A combined summary of precision and recall. |

These are population-weighted estimates. Weighting corrects for the fact that
the test sample deliberately included different numbers from different
language and pipeline-decision groups.

Among true headline articles for which a district answer was available:

- exact district accuracy was 0.822;
- the system supplied a district in 0.927 of applicable cases; and
- 101 of 123 labelled district answers were exactly correct in the unweighted
  sample.

Event-date extraction was not declared reportable. Only 18 test articles had
usable event-date truth, below the prespecified minimum of 30. Thirteen of
those 18 happened to be exact, but such a small subset is not strong enough for
a formal accuracy claim. This limitation is why the rainfall analysis used a
date-confidence rule and date-shift sensitivity tests.

## 15. What the validation does and does not prove

The validation supports the claim that the pipeline can identify suitable
landslide articles with useful accuracy. It does not prove that the final
inventory contains every landslide in Nepal. An unreported event cannot be
recovered from news, and a deleted or inaccessible article may remain missing.

The system can produce both:

- **false positives:** an article was included but should not have been; and
- **false negatives:** a suitable event article was rejected or missed.

The confidence intervals express sampling uncertainty around the estimated
performance. They do not include every possible source of bias, such as uneven
news access between remote and urban districts.

## 16. Comparison with BIPAD and COOLR

External matching was performed as a separate triangulation exercise against
the frozen v0.6.0 inventory. At the common 8 August 2026 cutoff, 2,880 eligible
canonical news events were compared with 5,345 BIPAD rows. Repeated BIPAD rows
were harmonized into 4,095 incident clusters. The matching produced 561 BIPAD
clusters with a strong Tier A or Tier B news link. Weaker district-and-date
candidates were retained as leads rather than declared matches.

BIPAD is also incomplete and may itself use media reports. Therefore BIPAD was
not treated as perfect ground truth, and the project does not call news/BIPAD
overlap “precision” or “recall.” COOLR was treated as spatial scientific
evidence; its polygons were not counted as independent reported events.
The exact canonical CSV hash is recorded in `external_agreement.json` so this
comparison cannot silently drift to a different working-database snapshot.

---

## Part III — Rainfall data

## 17. What rainfall product was used?

The project used **UCSB CHIRPS v2.0 Final daily precipitation** accessed via
NASA SERVIR ClimateSERV. CHIRPS combines satellite observations and rain-gauge
information to estimate rainfall on a regular grid.

Rainfall was summarized as a daily spatial average for each of Nepal’s 77
districts. The boundary file was Open Knowledge Nepal’s LocalBoundaries
district dataset in WGS84 coordinates.

The final rainfall table contains:

| Measure | Value |
|---|---:|
| Start date | 2015-01-01 |
| End date | 2026-06-30 |
| Days | 4,199 |
| Districts | 77 |
| District-day rows | 323,323 |
| Expected rows | 323,323 |
| Missing district-days | 0 |
| Coverage | 100% |

“100% coverage” means every expected district-date combination is present in
the downloaded table. It does not mean that satellite rainfall is perfectly
accurate at every slope.

## 18. What does district-average rainfall mean?

Imagine placing a rainfall grid over a whole district and averaging the grid
cells for each day. That value represents the district broadly. It may smooth
out a very intense storm over one small valley or hillside.

This scale matches the inventory because every final event has a district, but
many do not have a precise slope coordinate. Consequently, the analysis is a
district-day study, not a slope-failure or rain-gauge threshold study.

---

## Part IV — Rainfall analysis

## 19. What counted as a landslide case-day?

The primary analysis started with final inventory records and applied the
following rules:

- district and event date had to be available;
- date confidence had to be at least 0.78;
- explicitly earthquake-triggered events were excluded;
- explicitly anthropogenic-triggered events were excluded;
- rainfall had to be available for the required antecedent windows; and
- if several events were reported in the same district on the same day, they
  counted as one case-day.

Collapsing same-district, same-day events prevents a heavily reported day from
receiving extra statistical weight merely because several articles or event
records describe it.

The pipeline read all 2,885 events. There were 1,846 events meeting the primary
event/date/trigger rules before the rainfall join. Eighteen otherwise eligible
events occurred after the available rainfall end date of 31 July 2026; they
were excluded rather than assigned made-up rainfall. After joining, collapsing
district-days, and requiring complete windows, the primary analysis contained
1,508 case-days.

## 20. What was rainfall exposure?

For each case-day, the project calculated:

- **R1:** rainfall on the event day;
- **R3:** total rainfall across the event day and previous two days;
- **R5:** total rainfall across the event day and previous four days; and
- **R7:** total rainfall across the event day and previous six days.

All primary windows include the reported event day. Lagged versions ending the
day before the event were also retained for investigation.

## 21. Why were control days needed?

Looking only at rainy landslide days cannot show whether that rain was unusual.
The analysis therefore compared each landslide case-day with ordinary days on
which no media-reported event occurred.

For each case, up to five controls were sampled from:

- the same district;
- the same calendar month; and
- the same year.

Possible controls within seven days before or after any reported event in that
district were removed. This reduces the chance of choosing an unrecorded part
of the same rainfall episode as a “normal” day.

Matching within district, month, and year makes the comparison fairer. For
example, a July landslide day in Sindhupalchok is compared with other July days
in Sindhupalchok—not with a dry winter day in a different province.

The primary sample contained 1,514 case-days and 6,196 matched controls.
Fewer than five controls were available for some events because dense event
periods and the seven-day buffer removed possible controls.

## 22. Why were the data divided into development and test periods?

If a threshold is selected and judged using the same data, it can look better
than it really is. The project avoided this by splitting time:

- **Development:** through 31 December 2022; used to choose the rainfall
  window and threshold.
- **Temporal test:** from 1 January 2023 onward; used only to evaluate the
  already selected choice.

The development sample contained 872 case-days and 3,716 controls. The test
sample contained 642 case-days and 2,480 controls.

This is similar to studying old exam questions to choose a method and then
testing it on a later exam that was not used to choose the answers.

## 23. How was the threshold selected?

For each rainfall window, the system calculated a receiver operating
characteristic curve, usually called an ROC curve. It shows the trade-off
between detecting landslide days and wrongly flagging ordinary days at every
possible rainfall cutpoint.

The area under this curve is the **AUC**:

- 0.5 means rainfall separates the two groups no better than chance;
- 1.0 means perfect separation; and
- values between them show partial discrimination.

The best development window was chosen by AUC. A cutpoint within that window
was selected using Youden’s J, which balances sensitivity and specificity.
The 5-day window narrowly beat the 3-day window in development data by only
0.0003 AUC. The selected development threshold was **45.381465 mm**, reported
in ordinary text as **45.4 mm over five days**.

## 24. What do the evaluation terms mean?

- **Sensitivity:** Of the reported landslide case-days, how many exceeded the
  threshold?
- **Specificity:** Of the matched non-event control days, how many stayed below
  the threshold?
- **Precision:** Among above-threshold rows in this designed matched sample,
  how many were case-days?
- **Balanced accuracy:** The average of sensitivity and specificity.
- **AUC:** How well rainfall ranks case-days above control days across all
  possible thresholds.
- **95% confidence interval:** A range showing sampling uncertainty. If a
  similar study could be repeated many times, intervals constructed this way
  would contain the underlying value about 95% of the time under the model.

Because controls were deliberately sampled at roughly five per case,
rainfall-analysis precision is not the probability that a real-world
above-threshold day will have a landslide. It applies only to this matched
sample design.

## 25. Why was bootstrapping used?

Events in the same district are not fully independent. They share terrain,
climate, and reporting conditions. The analysis therefore resampled districts,
not just individual rows, in 1,000 bootstrap repetitions. This produced
district-clustered uncertainty intervals for the temporal-test results.

The development threshold was also bootstrapped. Its 95% interval was wide:
26.8 to 72.1 mm. This shows that the precise cutpoint is uncertain even though
the broader rainfall association is reproducible.

---

## Part V — Rainfall results

## 26. Main result

The development data selected a five-day accumulation threshold of 45.4 mm.
Applied unchanged to the later test period, the result was:

| Measure | Result | 95% confidence interval |
|---|---:|---:|
| Selected window | 5 days | — |
| Threshold | 45.4 mm | 26.8–72.1 mm |
| AUC | 0.693 | 0.657–0.722 |
| Sensitivity | 0.509 | 0.449–0.567 |
| Specificity | 0.764 | 0.718–0.809 |
| Balanced accuracy | 0.637 | 0.611–0.661 |
| Matched-sample precision | 0.359 | 0.305–0.414 |

The test-period classification counts were:

| | Threshold exceeded | Threshold not exceeded |
|---|---:|---:|
| Reported landslide case-day | 327 | 315 |
| Matched control day | 585 | 1,895 |

In simple language:

- about 51% of reported landslide case-days crossed the 45.4 mm threshold;
- about 76% of matched ordinary days remained below it; and
- rainfall separated case-days from controls moderately better than chance.

The threshold missed many reported events, so it should not be treated as a
standalone alarm rule.

## 27. Comparison of rainfall windows

In the temporal test data, AUC values were approximately:

| Rainfall window | Test AUC |
|---|---:|
| 1 day | 0.647 |
| 3 days | 0.694 |
| 5 days | 0.693 |
| 7 days | 0.685 |

Although the 3-day window was slightly higher in the test period, it was not
substituted after seeing the test result. The 5-day window remained the honest
primary answer because development data had selected it in advance.

The main scientific message is therefore not that five days is uniquely best.
Rather, several days of accumulated rainfall—especially three to five
days—carry a moderate signal for media-reported landslide occurrence.

## 28. Sensitivity analyses

Sensitivity analysis asks whether a conclusion changes when reasonable
assumptions are changed.

| Alternative assumption | Selected window | Threshold | Test AUC | Interpretation |
|---|---:|---:|---:|---|
| Primary design | 5 days | 45.4 mm | 0.693 | Main result |
| Use all dated events | 5 days | 51.6 mm | 0.689 | Similar discrimination |
| Require date confidence ≥0.80 | 5 days | 45.4 mm | 0.686 | Similar result with stricter dates |
| Shift event date one day earlier | 3 days | 20.0 mm | 0.664 | Weaker; reported timing matters |
| Shift event date one day later | 5 days | 47.1 mm | 0.692 | Almost unchanged |
| Include known non-rain triggers | 5 days | 46.5 mm | 0.679 | Weaker, as expected |
| Exclude road-obstruction events | 5 days | 54.4 mm | 0.690 | Similar AUC, lower sensitivity |

Most alternatives still selected a five-day window and produced AUC values
near 0.68–0.69. This supports the existence of a rainfall association. The
change after shifting dates earlier also confirms that news-derived event dates
remain an important source of uncertainty.

## 29. District-month association

As a secondary check, the project compared monthly district rainfall with the
number of reported case-days in that district and month. Spearman’s correlation
was **0.275** across 10,626 complete district-month rows.

This is a modest positive association: wetter district-months tended to have
more reported event-days, but the relationship was not strong. The value also
reflects reporting differences and many district-months with no reported
events. It was not used to define the rainfall threshold.

## 30. What is the correct conclusion?

The defensible conclusion is:

> Several days of district-average antecedent rainfall contain useful but
> moderate information about when media-reported landslides occur in Nepal.
> A development-selected five-day total of approximately 45.4 mm transferred
> moderately to later years, but the cutpoint is uncertain and is not an
> operational warning threshold.

The project demonstrates that a validated bilingual web-derived inventory can
support reproducible rainfall research while keeping reporting and measurement
limitations visible.

## 31. What must not be claimed?

The project does **not** show that:

- 45.4 mm will trigger a landslide everywhere in Nepal;
- rainfall below 45.4 mm is safe;
- rainfall above 45.4 mm guarantees a landslide;
- the inventory contains every landslide that happened;
- article counts alone measure changes in physical landslide frequency;
- BIPAD or the news inventory is perfect ground truth; or
- district-average CHIRPS rainfall equals rainfall at an individual slope.

---

## Part VI — Limitations in ordinary language

## 32. Media-reporting bias

News organizations are more likely to report events that kill people, block
important roads, occur near populated areas, or are easy for journalists to
reach. Remote, small, nonfatal, and older events are more likely to be absent.
English and Nepali outlets also have different geographic and editorial
coverage.

## 33. Uneven historical coverage

Recent web pages are generally easier to recover than older pages. The large
number of events in 2024 may partly represent better archive coverage and more
active sources. The annual event table should not be interpreted as a physical
trend without explicitly modelling reporting effort.

## 34. Event-date uncertainty

Articles do not always state the exact failure date. Some use words such as
“yesterday,” while follow-up reports may be published days later. The formal
locked test did not contain enough event-date truth to report a robust date
accuracy. Confidence filtering and one-day shifts reduce, but do not remove,
this limitation.

## 35. Location resolution

The analysis uses districts because district information is much more complete
than exact coordinates. Landslides are local slope failures, while districts
can cover large and topographically varied areas.

## 36. Rainfall measurement

CHIRPS is a gridded product, not a gauge at the exact landslide site. District
averaging smooths local peaks, particularly in mountainous terrain. Other
products, such as IMERG or local gauges, might produce different totals.

## 37. Control-day uncertainty

A control day means no event was reported in this inventory. A small or
unreported landslide may still have occurred. Such contamination generally
makes case and control rainfall look more similar, reducing measured
discrimination.

## 38. Trigger uncertainty

Many articles did not state a trigger, leaving 1,200 final records labelled
unknown. The primary analysis removed events explicitly known to be caused by
earthquakes or human activity, but some unknown events may also have had
non-rainfall causes.

---

## Part VII — Reproducibility and final deliverables

## 39. Frozen inventory release

The final inventory release is:

`data/releases/nepal_landslide_inventory_v0.6.0_v7_20260915/`

It contains the canonical CSV, validation labels and predictions, audit
reports, reviewed correction provenance, release manifest, and a database
snapshot. Important release facts are:

- 2,885 rows and 2,885 unique event IDs;
- no canonical event after the 10 August 2026 release cutoff;
- all locked URL, label, prediction, and uniqueness checks passed;
- canonical CSV SHA-256:
  `3b335babbfcbe0b50d2aad9023e08e55a2ca6e8e0881729615df33e2c9b9d0e8`;
- bundle lock:
  `3a6faabc734c5410324530668c8e4cc529342d5dec39838c4a720bc545b57a91`.

A SHA-256 hash is a digital fingerprint. If the file changes, its fingerprint
changes. The bundle lock therefore helps demonstrate which exact files belong
to the frozen release.

## 40. Frozen rainfall-analysis release

The final analysis release is:

`data/releases/nepal_landslide_rainfall_v0.8.0_20260915/`

It contains the rainfall input, district boundaries, joined case and control
tables, complete metrics, ROC coordinates, sensitivity results, figure,
reports, protocol, manuscript draft, and both release manifests.

Its checks confirm:

- complete rainfall coverage;
- all 77 districts present;
- no incomplete rainfall days; and
- a nonempty independent temporal test period.

The v0.8.0 rainfall release bundle lock is:

`5fc21229bb73125d0eaa807778a6a5a4f51e969a3336a953c0d39ebca3b3de2d`

## 41. Main files and what they mean

| File | Purpose |
|---|---|
| `data/outputs/canonical_events_final.csv` | Final working copy of the 2,885-event inventory |
| `data/outputs/inventory_audit_report.md` | Inventory quality summary |
| `data/outputs/locked_test_set_v7_score.json` | Final held-out extraction/classification evaluation |
| `data/external/chirps_daily_districts.csv` | Daily rainfall for 77 districts |
| `data/outputs/event_antecedent_rainfall.csv` | Primary case-days and their rainfall windows |
| `data/outputs/rainfall_controls.csv` | Matched non-event control days |
| `data/outputs/rainfall_threshold_metrics.csv` | Results for every window and split |
| `data/outputs/rainfall_sensitivity_summary.csv` | Robustness checks under alternative assumptions |
| `data/outputs/rainfall_primary_test_roc.csv` | ROC curve coordinates |
| `data/outputs/district_month_rainfall_association.csv` | Secondary monthly association data |
| `data/outputs/rainfall_conditional_models.csv` | Odds ratio per 10 mm within matched sets |
| `data/outputs/rainfall_resampled_validation.csv` | Year-by-year and district-group held-out results |
| `data/outputs/rainfall_season_stratified.csv` | Monsoon and non-monsoon results separately |
| `data/outputs/rainfall_matching_diagnostics.json` | How well the case/control matching actually worked |
| `data/outputs/inventory_reporting_composition.csv` | Which newspapers reported in which years |
| `data/outputs/inventory_district_summary.csv` | Events and case-days per district |
| `data/outputs/rainfall_results_figure.svg` | Main reproducible results figure |
| `data/outputs/inventory_map_figure.svg` | Map of reported events by district |
| `data/outputs/rainfall_distributions_figure.svg` | Seasonality and case/control rainfall |
| `data/outputs/rainfall_validation_figure.svg` | Held-out validation across years and districts |
| `data/outputs/rainfall_analysis_report.json` | Complete machine-readable analysis report |
| `docs/RAINFALL_MANUSCRIPT_DRAFT.md` | Scientific manuscript draft |

## 42. Database storage

The active uncompressed SQLite database is stored inside the Box project at
`data/raw_sqlite/landslide_inventory.sqlite` and is the default database used
by `scripts/run_local_db.sh`. The historical wrapper name is retained so
existing commands continue to work. The database is approximately 334 MiB,
which may exceed the per-file synchronization limit of some Box plans. The
portable CSVs, reports, code, and frozen release metadata are also retained in
the project. `LS_SQLITE_PATH` can still explicitly select a different database
copy when needed.

## 43. Rebuilding the analysis

The repository contains a configuration-driven command-line pipeline. Once the
frozen inventory and daily rainfall file are available, the rainfall analysis
is run through the `analysis` stage. Random seeds are fixed for control
sampling and bootstrapping so that repeated runs are reproducible.

The project test suite passed in full, and the final release manifests passed
their recorded integrity checks. Rebuilding with unchanged inputs is allowed.
Changing labels, extraction rules, event records, rainfall inputs, or analysis
settings requires a new version rather than silently replacing the frozen
release.

---

## Part VIII — Final status and lay summary

## 44. Is the project finished?

Yes. The project is complete for the agreed scope:

- news and archive collection is frozen;
- external evidence collection is documented;
- bilingual extraction and filtering are complete;
- duplicates and corrections are resolved;
- the final 2,885-event inventory is released;
- independent manual validation is complete;
- CHIRPS rainfall collection and quality checks are complete;
- threshold, temporal-test, bootstrap, sensitivity, and secondary analyses are
  complete;
- the strictly antecedent (event-day-excluded) co-primary analysis, the
  within-matched-set odds ratios, leave-one-year-out and district-held-out
  validation, season stratification, and matching diagnostics are complete; and
- the results, four figures, tables, manuscript draft, changelog, senior review,
  and checksummed releases are present.

Known genuine gaps, all requiring resources the project does not currently have:
comparison against a second rainfall product such as IMERG; terrain or elevation
effect modification, which needs a digital elevation model; sub-district exposure
for the 926 records that carry a municipality, which needs checksum-pinned
municipality geometry; and prospective validation.

Author information, journal choice, manuscript styling, public repository DOI,
and submission forms are publication-administration tasks. They are not missing
scientific analyses.

## 45. The result explained to a layperson

Thousands of news reports were searched to find accounts of real landslides in
Nepal. After removing unrelated articles and merging multiple reports of the
same incident, the project produced 2,885 unique records. A separate human
check showed that the automated system found most relevant articles, although
some incorrect inclusions and missed events remain.

The reliable event-days were then compared with satellite-based rainfall. To
make the comparison fair, each landslide day was matched with ordinary days in
the same district, month, and year. Older data were used to choose a rainfall
rule, and later data were reserved to see whether that rule still worked.

The chosen rule was approximately 45.4 mm of rain across five days. It detected
about half of reported landslide days while correctly leaving about three
quarters of comparison days below the threshold. This confirms that recent
rainfall is meaningfully related to reported landslide occurrence, but rainfall
alone cannot explain or predict every event. The threshold is a research
finding—not a warning system.

Four things are worth understanding about how strong that finding is.

**The five-day total includes the day of the landslide.** Satellite rainfall is
reported as a whole-day total, and news reports do not say what time of day a
slope failed. So part of that 45.4 mm may have fallen *after* the landslide
happened. If the rule is restricted to rain that definitely fell *before* the
reported day, the best version is about 19 mm over three days, and it works
slightly less well. That stricter number is the honest ceiling for anything
resembling early warning.

**One test period flatters the result.** The rule was checked on 2023–2026 and
scored 0.693 (where 0.5 is a coin flip and 1.0 is perfect). Repeating the whole
exercise leaving out each year in turn gives scores between 0.563 and 0.710,
with a middle value of 0.652. So 0.693 is a good year to have been tested on,
not the typical result. The *threshold itself*, however, is remarkably steady:
leaving out any single year still picks 45.4 mm.

**The number is a monsoon number.** During June to September the rule is 45.4 mm
over five days. Outside the monsoon the best cut-off drops to about 1.5 mm,
because in a dry month almost any rain at all stands out. There is no single
year-round rainfall number for Nepal.

**Counting news reports is not counting landslides.** The newspapers covered by
the project changed over the years: some stopped, some started, and Nepali-language
coverage grew far faster than English. Rising report counts over time therefore
reflect the newspapers as much as the weather, and this guide never presents them
as a landslide trend.

## 46. One-sentence final takeaway

**A validated bilingual media inventory of 2,885 Nepal landslide-related records
reveals a reproducible but moderate three-to-five-day antecedent rainfall signal,
with a development-selected five-day monsoon threshold of about 45.4 mm — around
0.65 discrimination once year-to-year variation is accounted for, and lower still
when rain falling on the day of the event is excluded — that must not be
interpreted as an operational warning threshold.**
