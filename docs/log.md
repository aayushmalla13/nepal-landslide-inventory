# Working Log — Nepal Landslide Inventory

Purpose: running context for any contributor (human or Claude) picking up this repo.
Read this **after** `docs/TECHNICAL_REVIEW.md` and before touching code.

Newest entries at the bottom of each session. Session headers are dated.

---

## Standing context (read first)

**The problem, in one paragraph.** The pipeline turns 4,453 scraped Nepali/English news
articles into canonical landslide events (1,071 at review time; **1,002 now**, of which
**758 are headline landslide events** — the rest are 114 `road_obstruction`, 105
`aggregate_report` and 25 non-landslide hazards, all retained but excluded from
headline counts).

The engineering is sound; the science layer is improving but not yet publishable.
Class-1 precision was 0.516 and **has not been re-measured** — every metric in the repo
is still in-sample, because the 200-row evaluation set was re-scored after the rules were
tuned on it. Kathmandu's rank was fixed on 2026-08-06 — the headline table now reads
Chitwan 48, Kathmandu 33, Palpa 33, Baglung 32 — but by removing construction
errors, not by validation.
See `docs/TECHNICAL_REVIEW.md` §0.

**VALIDATED RESULT (2026-08-07, all 395 rows labelled, 362 scored):**
weighted **precision 0.806, recall 0.401, F1 0.536**. 95% CI: precision [0.74, 0.87],
recall [0.41, 0.54]. Confusion tp 107 / fp 24 / fn 118 / tn 113. The 33 excluded rows
are exactly those with no stored article text.

This is the project's first out-of-sample number. It is **not** comparable to the
review's 0.516 class-1 precision — different definition, different sample, and this one
is weighted to population. By language: en 0.779/0.372, np 0.827/0.426 — **Nepali is not
the weaker path**, which is a real result for a bilingual pipeline.

**EXTERNAL VALIDATION (2026-08-07).** Nepal's DRR Portal, quoted by The Himalayan
Times, records **4,629 landslides and 1,906 deaths for 2011–Aug 2025** — i.e. ~130
deaths/year. Our inventory now reports **130 deaths/year**. A ratio of 1.00 against
a completely independent national source, where before the casualty fix we were at
567/year. That is the strongest validation available without the BIPAD export, and
it belongs in the paper.

Event completeness is ~22% of DRR-recorded landslides (70/yr vs 315/yr). That is
expected and reportable: a news-derived inventory captures *newsworthy* landslides,
not every recorded incident. Do not present it as a shortfall — present it as what
the method measures.

**Before scoring, always run `--stage refresh_predictions`.** The prediction file is
written when the sample is drawn and goes stale the moment the pipeline changes. The
first score ran against predictions from before the metaphor fix and reported the
already-fixed `by landslide` bug as a live failure — 8 of 9 apparent disagreements were
against code that no longer existed.

**The governing constraint.** Do not tune any rule before a locked, held-out test set
exists (§9, "the single best next step"). Every tuning pass without one destroys more
of the project's ability to state a defensible number in the paper.

**Key invariants to preserve.**

- Determinism: `utils/hashing.stable_hash`, sorted iteration, seeded sampling. Do not
  introduce unsorted set iteration or unseeded randomness anywhere in the pipeline.
- The gazetteer layer (`gazetteer.py`, `gazetteer_municipality.py`, `resources/*.csv`)
  is the highest-quality asset in the repo. Extend it; do not rewrite it.
- `data/` is gitignored (378 MB). Datasets are versioned by snapshot file + a
  `DATA_VERSION` pointer, never by committing the SQLite.

**Landmines.** (Struck-through items were fixed on 2026-08-06; kept so the history
of each is visible rather than silently disappearing.)

- Filter stages (`event_specificity.py`, `scope_filter.py`) **still** run
  `UPDATE article_events SET district = NULL, ...` on demotion. They now log the
  pre-mutation values to `article_decisions` first, so provenance survives — but
  `article_events` is not yet immutable. Making it so is review §7 Redesign item 3
  and requires reworking `dedup` and `location_consistency`.
- **Never add a short bare substring to an exclusion pattern list.** `'by landslide'`
  cost 128 real events. Run `--stage pattern_audit` before and after any change to
  `METAPHOR_PATTERNS`, `ROUNDUP_PATTERNS`, `RISK_PATTERNS`, `CONTEXT_ONLY_PATTERNS`,
  `FOLLOWUP_PATTERNS` or `FOREIGN_TERMS`.
- `http_status` was consulted nowhere, which is how 615 HTTP 429 error pages became
  articles. `validation/article_quality.is_ingestible_article` is now the gate; use it.
- ~~`config.py` hard-fails unless there are exactly 8 sources with exactly the expected
  slugs.~~ Fixed 2026-08-08 — now a **subset** check. Dropping one of the original eight
  still hard-fails (every coverage baseline here assumes them); adding sources is
  allowed, plus a new duplicate-slug check. This had been silently blocking the
  highest-value work in the project.
- **Nepali compounds contain their own parts.** हिमपहिरो (avalanche) contains पहिरो
  (landslide); बाढीपहिरो (flood-landslide) contains both. Any substring check over
  Nepali hazard terms must test the most specific compound first, or it silently
  absorbs a whole hazard class. This is what put Everest and Manaslu avalanches in a
  landslide inventory.
- **A dateline is not a location.** `_find_explicit_district` no longer falls back to
  it. If you add another "last resort" district source, check first whether returning
  `None` is more honest — a null district is measurable, a wrong one is invisible.
- ~~`config.yaml → keywords.exclude` is dead config.~~ Fixed — now read by
  `event_specificity.metaphor_exclude_terms`.
- ~~`canonical_events_final.csv` is produced by no code.~~ Fixed — `--stage export_final`.
- ~~The study window is stated three different ways.~~ Fixed — 2015–2026 everywhere,
  `config.yaml` authoritative.

---

## Session 2026-08-06 — post-review immediate items

**Operator:** Aayush · **Agent:** Claude (Cowork)

**Agreed scope for this session** (§9 "Immediate — this week"):

1. git baseline commit + working branch
2. DB snapshot before any stage re-run
3. Freeze locked test set drawn from `raw_articles` (including dropped rows)
4. Fix `by landslide` + audit all pattern lists for substring collisions
5. Add `article_decisions` table; stop destructive updates
6. Purge crawler garbage (KP section pages, phantom 2026 rows)
7. Resolve `canonical_events_final.csv` provenance

Explicitly **out of scope** this session: §8.1 event-site role classification and
§8.2 cross-language dedup. Those are the next two pieces of work and are the highest
value remaining after the above.

### What was done

All seven immediate items are complete. Commits on branch `fix/review-immediate`,
baseline tagged `pre-review-baseline`. Test suite: 341 passing (was 296, and one
was failing on any machine but the original author's).

| # | Item | Commit | Outcome |
|---|---|---|---|
| 1 | git baseline | `ef733ad` | 102 files committed, tagged. `data/` stays gitignored (378 MB). |
| 2 | DB snapshot | — | `landslide_inventory.snapshot_20260806_pre_fix.sqlite`, md5-verified. |
| 3 | Locked test set | `9d94854` | 395 rows drawn from `raw_articles`, hash-locked, blind. |
| 4 | Pattern collisions | `baf9562` | 211 of 235 `metaphor` exclusions released; 3 true positives newly caught. |
| 5 | `article_decisions` | `ba1a621` | Filter provenance preserved; stages become repeatable. |
| 6 | Crawler garbage | `07e4854` | 809 of 4,453 rows (18.2%) are not usable articles. |
| 7 | Final CSV provenance | `84d780d` | Reproduced field-for-field from code; `export_final` stage added. |

### Findings that change the picture

**1. The biggest data-quality problem is not in the review.**
615 of the 992 himalayan-times rows are HTTP 429 rate-limit error pages stored
as articles. Body is the literal string `You have exceeded the rate limit.
Please try again later.` (57 chars), title empty, `http_status = 429`,
`parse_success = 0`. The *median* himalayan-times row is an error page. Nothing
in the pipeline consulted `http_status`. 51 class-1 events rest on a
himalayan-times row too thin to extract from — classified from the title alone.

These 615 URLs are real articles that were never actually retrieved. They should
be **re-fetched with backoff**, not discarded. Doing so may materially change
the source balance and the year distribution.

**2. Two review findings did not survive measurement.** Both are in §4.4.

- *"The KP rows are not articles."* True of 9 of 75. The other 66 are real
  articles with a median 4,496-character body that simply are not about
  landslides. The KP problem is **archive depth** — every KP row is from 2026 —
  not garbage ingestion.
- *"The 485 phantom 2026 articles carry the scrape date."* They do not.
  `published_date_raw` holds real timestamps (`2026-03-24 18:03:16`) and the
  published month matches the fetched month. They are genuinely recent articles.
  The real issue is that `config.yaml` admits 2015–2026 while the README and
  `paper_metadata` claim 2015–2024 (§3.5).

**3. The `by landslide` bug was worse than estimated, and had siblings.**
The review estimated ~200 lost events; the measured figure is 211 released of
235. The new `--stage pattern_audit` also ranks every other pattern by suspected
false negatives. Top remaining offenders are all FOLLOWUP road-reopening terms
(`सञ्चालनमा` 93, `खुल्यो` 37, `खुलेको` 35) — but these are **not** substring
collisions. They are the Narayangadh–Muglin road-obstruction articles, i.e. the
event-definition question in §4.2. The audit tells you where to look; it does
not tell you what you are looking at.

**4. The audit metric needed a Nepal anchor.** Its first cut flagged `'india'`
and `'china'` as top offenders at ~0.8 collision rates. Inspection showed those
exclusions were *correct* — "15 bodies found after landslide buries scores in
China" has abundant incident evidence and is exactly what the foreign filter is
for. The metric now also requires a gazetteer district and no foreign country in
the title. Recorded in the module docstring so it is not re-derived.

### The constraint that blocks a clean measurement

Running `event_specificity` with the fix drops `metaphor` from 235 to 54 — but
**the 181 released articles do not return to class 1**. Their `district` and
`event_date_ad` were NULLed by an earlier run, so they can no longer score above
threshold. Provenance recovery from the new decision log is only 2,231/4,453 for
district; the rest was destroyed before the log existed.

This is §2.2's cost, made measurable. **A clean end-to-end number requires
re-running `extract`** (spaCy over 4,453 documents). The DB has been restored to
the pre-fix snapshot; the code is committed and ready to run.

### New stages

```
--stage locked_test_set   draw/verify the held-out test set (refuses to redraw)
--stage pattern_audit     rank exclusion patterns by suspected false negatives
--stage article_quality   report non-articles in raw_articles (flags, never deletes)
--stage event_typing      label event_type / hazard_type / extraction_basis
--stage export_final      regenerate canonical_events_final.csv from the DB
```

### Second half of session: clean re-run + operator decisions

The `extract` re-run went ahead (spaCy model copied out of `.venv` into the
sandbox; ~90 s for 4,453 docs), followed by `event_specificity` →
`location_consistency` → `filter_scope` → `dedup`. DB snapshotted first as
`landslide_inventory.snapshot_20260806_pre_extract.sqlite`.

**Post-re-run numbers** — these are the first clean ones, because the fresh
extract restored the district/date fields the old destructive runs had NULLed.

| | before | after | Δ |
|---|---:|---:|---:|
| class-1 articles | 1174 | 1250 | +76 |
| canonical events | 1071 | 1127 | +56 |
| multi-source clusters | 69 | 81 | +12 |
| `metaphor` exclusions | 235 | 56 | −179 |

The large `no_location_signal` → `context_only` shift (−1041/+1041) is a
*relabelling*, not a decision change: totals are identical. With districts
populated again, `has_location_anchor` is true, so the no-location branch stops
firing and rows fall through to a more accurate reason.

**Decisions taken** (commit `b5308e2`):

1. **Study window → 2015–2026.** `config.yaml` is authoritative; README and
   `paper_metadata` now follow it. The temporal-coverage caveat is recorded in
   the README next to the claim.
2. **Road obstructions → kept, typed.** `event_type = 'road_obstruction'`,
   retained in the dataset, excluded from headline counts and BIPAD.
   Conservative: any casualty count, casualty word, or house/land damage keeps
   the row as `landslide`.
3. **Title-only extractions → kept, flagged.** `extraction_basis =
   'title_only'` with a 0.6 confidence multiplier. 33 of 1,127 events.
4. Both labels are carried in `canonical_events_final.csv`.

**Effect on the district table** (headline events only):

Chitwan 89 → 58 as 31 road obstructions move out; Sindhupalchok rises to #3.
**Kathmandu is still #1 at 73.** That is the dateline-bias problem in §4.1 and
it needs the §8.1 event-site role classifier — deliberately out of scope here.

`by landslide` no longer appears in the pattern audit's critical/high list. The
top remaining entries are the FOLLOWUP road terms, which decision 2 has now made
deliberate rather than accidental.

Tests: 355 passing.

### Third pass: the Kathmandu diagnosis, and why §8.1 was the wrong next step

Before starting §8.1 (event-site role classification, the review's stated
priority) I checked what was actually driving Kathmandu's 73 headline events.
**Zero of them came from an English dateline** — because `nlp_en/extract.py`
already implements dateline detection and a Kathmandu veto. Part of §8.1 was
quietly already done, which is why the review's diagnosis appeared not to
reproduce.

The 73 turned out to be five different problems needing five different fixes,
and §8.1 addressed only ~8 of them. Two cheaper, unambiguous bugs outranked it.

**Bug 1 — the dateline veto was cosmetic.** `_find_explicit_district` ended with
`return dateline_fallback`. A Kathmandu dateline was skipped so a real district
could win, but if no other district was found *anywhere*, the dateline was
returned as the event district — exactly the case where it is least
trustworthy. 27 class-1 English rows had a district only because of that line,
**all 27 Kathmandu**, and they were nationwide roundups, government relief
notices and Nepse share-market metaphors. Now returns `None`; the dateline
survives in `find_dateline_district()` for provenance.

**Bug 2 — avalanches were landslides by construction.** Nepali for avalanche is
हिमपहिरो / हिउँपहिरो, literally *snow-landslide*. It **contains** पहिरो, the
collection keyword, so every avalanche was collected as a landslide — and
`हिमपहिरो` was additionally listed in the title-event-signal tuple in
`event_specificity.py`, which *confirmed* them as events. 25 headline events
were avalanches, Everest and Manaslu included. New `hazard_type` field
(landslide / debris_flow / rockfall / avalanche / flood / other_hazard), matching
the locked test set's vocabulary so labels and output compare directly. Avalanche
must be tested first or any landslide-first check swallows all of them.

**Result — Kathmandu is no longer the #1 landslide district.**

| # | before | after |
|---|---|---|
| 1 | Kathmandu (73) | **Chitwan (58)** |
| 2 | Chitwan (58) | **Kathmandu (49)** |
| 3 | Sindhupalchok (45) | Sindhupalchok (48) |

Canonical events 1127 → 1112; headline events 1003 → **962** (124
`road_obstruction` + 26 non-landslide hazard excluded). Neither fix tuned a
threshold — both removed something wrong by construction, so neither burns the
test set.

**What is left in the remaining 49 Kathmandu events:** ~6 are genuinely
Kathmandu (Tarebhir, Tarkeshwor, Tokha, Naikap, Chandragiri — the valley rim
does have landslides). The rest are wrong-district cases for §8.1
(Kakani → Nuwakot; **"Makawanpur" not normalising to Makwanpur — a gazetteer
alias gap, probably a one-line fix**), a few surviving nationwide roundups, and
policy/relief articles that should be `context_only`.

Tests: 377 passing.

### Fourth pass: cross-language dedup (§8.2)

`token_set_ratio` scores every cross-language pair at ~0 because Devanagari and
Latin share no tokens, and the one cross-language path in the old code was gated
*behind* that check, so it was unreachable. 1,034 of 1,112 clusters were
singletons.

New `unify/similarity.py` compares **facts instead of scripts**: gazetteer-
normalised municipality and ward (already canonical English on both sides — the
old code used municipality only as a veto, never as evidence), casualty vectors,
Devanagari digit normalisation, a fixed transliteration table for place names
outside the gazetteer, and hand-rolled TF-IDF cosine replacing `token_set_ratio`
for bodies.

| | before | after |
|---|---:|---:|
| canonical events | 1112 | **1010** |
| multi-article clusters | 78 | **129** |
| en–np merge rate | 0 | **136/612 (22.2%)** |

All six known cross-language duplicates merged, including Baglung 2024-08-06
(6 deaths) which had been counted **six times** across three outlets.

**Scoped deliberately:** the structured path runs **only** on cross-language
pairs. Path 1 is *structurally* blind across scripts; within a language it can
see, and whether it sees *well* needs weights fitted on a labelled dev set.
Applying unfitted weights to same-language pairs would confound a structural fix
with an untested retuning.

**Three bugs found while building it** — all caught by tests or by reading
output, not by assumption:

1. *Renormalisation trap.* With one signal available it became the whole score,
   so a fuzzy place-name match alone hit 0.92 and merged. District and date are
   already the blocking key, so that is not evidence. Added a strong-evidence
   gate.
2. *Casualty tolerance.* Exact match vetoed correct merges when tolls were
   revised — Baglung was 6 in myRepublica and 7 in setopati, same day, same
   municipality. Now tolerance 1.
3. *`cluster_id` UNIQUE violation* from the new content-stable id. The
   collisions turned out to be **missed merges**, so the count is now logged as
   an under-merge metric (87 clusters).

**Honest cost.** Clusters with ≥6 members went 4 → 8, and the largest is wrong —
it mixes Jhyaplekhola, Nagdhunga–Naubise and two nationwide roundups. That
cluster existed at size **9 before** this change: a pre-existing
`token_set_ratio` over-merge that this grew by one. The root cause is upstream —
nationwide roundups should not be class-1 events at all.

**Process note, worth internalising.** The first two dedup runs appeared to
succeed. They had actually crashed on an `IntegrityError` and rolled back; the
unchanged counts were stale data. The crash was invisible because the run output
was piped through `grep`. Read full output when verifying a write.

### Fifth pass: the casualty field, and a dataset assessment

**The casualty field was unusable and is now credible.** It is the primary
scientific variable of a fatal-landslide inventory, and it read 6,242 deaths
across 862 events — 25.6 per fatal event, against a real Nepali toll of roughly
100–150 deaths a year. Three independent causes, found by inspecting the
high-death tail rather than by reading code:

1. **Both extractors kept the largest number in the article**
   (`if best_value is None or value > best_value`). News bodies carry this
   event's toll in the lead and the season-to-date national total further down;
   the maximum returns the second. A one-woman death in Morang became 90; "at
   least three killed" in Sindhupalchok became 249. Now: lead first, first match
   not largest, body only as a per-field fallback, running-total context vetoed.
2. **Aggregate reports were entering as events.** "Floods, landslides claim 1000
   plus lives in five years" contributed **480 deaths to Bardiya**, a Terai
   district. New `event_type = 'aggregate_report'` (105 events), checked *before*
   the casualty branch because an aggregate always has a casualty count.
3. **The foreign filter was blind in Nepali.** `सुडानमा पहिरोले... १००० जनाको
   मृत्यु` — a Sudan landslide killing ~1,000 — was an event in **Parbat
   district**. Nepali outlets report foreign disasters in Nepali, so an
   English-only foreign list is structurally blind to the articles most likely to
   leak. ~90 bilingual country terms added.

| | before | after |
|---|---:|---:|
| total deaths | 6,242 | **1,363** (~124/yr) |
| mean per fatal event | 25.6 | **6.5** |
| foreign events in inventory | 1 | 0 |

The district table is now geomorphologically sensible: Chitwan 48, then a flat
mid-hill tail (Kathmandu 33, Palpa 33, Baglung 32, Dhading 32, Gulmi 31).
Terai share excluding Chitwan is **3.0%** — the physiographic sanity check the
review asked for (§4.5) now passes.

### Dataset assessment — what this data can and cannot support

**Credible now:** 758 headline events, 71 of 77 districts, ~124 deaths/yr
matching the national figure, 3% Terai share.

**The binding constraint is spatial resolution.**

| | coverage |
|---|---:|
| district | 758 (100%) |
| municipality | 302 (40%) |
| ward | 1 (0.1%) |
| **coordinates** | **0 (0%)** |

`geocode/` is an empty stub. Nepal's median district is ~1,800 km²; a landslide
scar is 10²–10⁴ m². District-level location is roughly **seven orders of
magnitude coarser than the object being inventoried**.

This is decisive for scope. The dataset **cannot** support landslide
susceptibility mapping, slope/terrain analysis, rainfall-threshold work
(CHIRPS), or comparison with mapped inventories such as Roback et al. (2018) —
all of which need point locations. It **can** support district–year fatal-event
counts, cross-inventory comparison with BIPAD (including capture–recapture), and
reporting-bias analysis.

**Terminology recommendation.** In the geomorphology literature "landslide
inventory" implies mapped polygons or points. Calling this one that will draw a
reviewer's first objection. It is a *news-derived fatal landslide event
database* at district resolution. Naming it accurately costs nothing and removes
the objection.

**Two other coverage facts for the methods section:** 79% of events come from
just two outlets (setopati 45%, myrepublica 34%) while ekantipur contributes 1
and kathmandu-post 0 — the "eight bilingual sources" claim is not supported by
the data. And 2024 (152) is still 4.5× 2016 (34), so the temporal distribution
remains a coverage artifact, not a landslide signal.

### Correction to my own assessment: district resolution is the design

I previously wrote that the missing coordinates rule out the paper's downstream
analysis. That was measured against a susceptibility-mapping standard **this
project never claimed**. Reading `config.yaml` properly:

```
geocode.district_shapefile_path      ocha_districts.shp
analysis.chirps_district_month_path  chirps_district_month.csv
analysis.correlation_method          spearman
bipad.match_windows_days             [1, 3, 7]
```

The intended analysis is **district-month landslide counts against district-month
CHIRPS rainfall, by Spearman**, plus BIPAD cross-comparison. District resolution
is the design, not a shortfall. Susceptibility mapping was never in scope, so
the absence of point coordinates is not a defect. I withdraw that framing.

**The real statistical problem is sparsity, not resolution.**

| aggregation | cells | non-zero | mean count |
|---|---:|---:|---:|
| district-month | 10,164 | 535 (5.3%) | 0.075 |
| district-year | 847 | 326 (38%) | 0.89 |
| district-monsoon-season | 847 | 276 (33%) | 0.70 |

79% of events fall in Jun–Sep, so eight months a year contribute almost nothing
but inflate the zero mass. **A Spearman correlation on a surface that is 95%
zeros is driven by the zeros and will be badly attenuated** — it will understate
a real rainfall–landslide association and may report near-null.

Recommendation, in order of preference:

1. **Aggregate to district–monsoon-season** and correlate against seasonal
   rainfall totals. Only aggregation with enough signal per cell.
2. If month resolution is required, **model counts directly** — negative
   binomial or zero-inflated Poisson with an articles-per-source-year exposure
   offset — rather than correlating. That also absorbs the reporting-effort
   confound (§4.4) instead of leaving it in the residual.
3. Report Spearman on district-month only as a robustness check, with the
   zero fraction stated.

Municipality-level geocoding would still help (302 of 758 events have one), but
it is an improvement, not a prerequisite.

### Sixth pass: the first real score, and what the errors say

30 rows labelled. Weighted **precision 0.870, recall 0.553**.

**Precision looks healthy; recall is the problem, and it has one dominant cause.**
Of 7 false negatives, **5 are `kept_class2`** — the pipeline found the event, judged
it real, and then declined to promote it to class 1.

Corpus-wide this is large: **1,033 of 1,260 class-2 rows have both district and
date**, so the demotion is not failed extraction.

| demoted by | n |
|---|---:|
| `followup` | 428 |
| `event_specific` (i.e. specificity kept it, extract ladder demoted it) | 351 |
| `roundup` | 221 |

Tracing the 351 through `_qualifies_for_specific_class_one` (nine sequential
vetoes) gives two mechanisms:

1. **`_is_cumulative_toll_update` fires on single-event reports that state a
   toll** — "11 killed, 20 others still missing in Gumthang landslide",
   "55 die in Taplejung landslides". These are events, not running totals.
2. **The ladder requires `deaths/missing/injured > 0`**, so a displacement-only
   event can never reach class 1 — "150 households displaced as fresh landslide
   looms large in Parbat", which the annotator labelled a real event with zero
   deaths.

Mechanism 2 is the `LABELING_GUIDE` vs `manual_label_policy` conflict
resurfacing as measurable recall loss: the code implements *casualties
required*, while `docs/ANNOTATION_RUBRIC.md` — now authoritative — does not.

**Neither is fixed yet, deliberately.** Adjusting `_is_cumulative_toll_update`
until these five rows pass is fitting to the test set — the exact failure that
makes the old 200-row set unusable. The casualty requirement is a *definitional*
mismatch rather than a tuning question and can be corrected on principle, but its
effect has to be measured corpus-wide, not against the rows that revealed it.

### Seventh pass: the validated result

All 395 rows labelled by the operator over two rounds. **Precision 0.806, recall 0.401.**

**Recall is the problem and 88% of it sits in two buckets:**

| where the 118 false negatives are | n | |
|---|---:|---|
| `dropped_specificity` | 54 (46%) | followup 19, context_only 18, risk_only 13, roundup 9 |
| `kept_class2` | 50 (42%) | **all 50 have `specificity_reason = event_specific`** |

The second is the bigger finding. Specificity judged all 50 to be specific
events; the extract-stage class ladder then refused to promote them. Corpus-wide
**1,033 of 1,260 class-2 rows have both district and date**, so this is not
failed extraction — it is review §3.2's conflation, where `class` answers both
*is this an event?* and *did we extract two fields?* at once.

**Precision is healthy and its errors are one thing:** 18 of 24 false positives
are roundups the annotator rejected as running totals — mostly follow-ups that
restate an ongoing toll ("17 still missing in Kalikot, two more bodies
retrieved") which `aggregate_report` does not yet catch.

**Nothing has been tuned against these labels.** The two fixes this diagnosis
implies — the cumulative-toll veto misfiring on single-event reports, and the
casualty requirement contradicting `docs/ANNOTATION_RUBRIC.md` — remain unmade
so the measurement stays honest. Making them is the next session's work, and the
result must be re-measured on a *fresh* draw, not this set.

**Two annotation-workflow lessons**, both my errors:
- The first tool showed a 400-char snippet and a link; when links were dead the
  operator correctly marked 162 rows unclear. The full text was in the database
  the whole time. Round 2 showed it and 129 of those resolved.
- `trigger_true` was a free-text box with no stated vocabulary, so 152 rows hold
  prose ("Incessant monsoon rainfall"). `check_labels.normalize_trigger` maps
  them; it does not affect the headline metric.

`--stage check_labels` now guards spreadsheet editing: out-of-vocabulary values,
Excel mangling Devanagari, reformatted dates, deleted rows.

### Eighth pass: ladder fixes, and the LLM question answered with data

**Two principled fixes** (not tuned to the labels):
1. `_is_cumulative_toll_update` treated the phrase "death toll" as proof of a
   running total. A single-event story routinely says "the death toll in the
   Gumthang landslide has reached 11". Now requires a toll **and** a period or
   wider-area scope. Nepali toll phrases added.
2. The ladder's hard casualty requirement contradicted `ANNOTATION_RUBRIC.md`
   and was redundant with `_has_strong_fallback_impact`. Removed, so
   displacement-only events can qualify.

**Effect: precision 0.806 → 0.801, recall 0.401 → 0.413.** Only 6 of 395
decisions changed. Modest — and the diagnosis is worth more than the gain.

**The dominant remaining blocker is not a bug.** Re-tracing the 46 still-missed
class-2 rows, `_is_road_disruption_title` accounts for 24 — which is the
operator's own road-obstruction policy. An annotator asked "did a landslide
happen?" says yes; the pipeline excludes by design. The scorer now reports the
sensitivity:

| | precision | recall |
|---|---:|---:|
| all rows | 0.801 | 0.413 |
| excluding road-title articles | 0.800 | **0.452** |

So ~4 recall points are the price of a definition, not a defect. **State this in
the methods section rather than reporting 0.413 unqualified.**

**Should you use an LLM?** Splitting the 140 errors answers it:

| | n | can an LLM help? |
|---|---:|---|
| definitional (road policy) | ~24 | No — a policy is not a prediction |
| mechanical (gate bugs) | ~28 | No — rules already had it right |
| **judgement** | **~88** | **Yes — this is reading comprehension** |

So: `unify/llm_adjudicator.py`, adjudicating **only** the judgement calls.
Responses cached on disk keyed by hash(model, prompt, article) so runs replay
with no network; model id and prompt version recorded per row; rules remain the
fallback when there is no key. `--stage benchmark_adjudicator` scores it against
the rules on the same labelled rows.

**Not yet benchmarked** — no API key in the working environment. 332 rows are
queued. Adopt it only if it wins that benchmark, and report both numbers either
way.

**Measurement honesty:** this is the second score on the same locked rows. One
principled change then one measurement is defensible; iterating is not. Treat
0.413 as mildly optimistic and draw `DESIGN_VERSION = v2` before publishing.

### Ninth pass: BIPAD rewritten as cross-inventory agreement (§6)

`bipad/validation.py` computed `precision = matches/canonical_count` and
`recall = matches/bipad_count`, asserting BIPAD is ground truth. New
`bipad/agreement.py` implements all six §6.2 layers and **never reports
precision or recall against BIPAD**.

**Three correctness bugs fixed, each with a test:**

- The hazard filter **failed open** (`if not disaster_value: return True`). If
  the export's hazard column wasn't among the expected names, every flood, fire
  and epidemic counted as a landslide — silently, producing a plausible recall
  number. Now fails closed.
- **Bikram Sambat dates parsed as AD.** `date_bs` is in the column list and
  `2081-03-25` is a valid-looking AD string, so it landed ~57 years out. Now
  raises `BikramSambatDateError`.
- **Ambiguous date orders resolved silently** (`%d-%m-%Y` before `%m-%d-%Y`).
  Now returns None and the unparseable count is reported.

Plus the missing study-window filter, with every exclusion counted.

**The demonstration that justifies Layer 3.** Run against the real 772-event
inventory with a synthetic BIPAD export having 60% true overlap:

| tier | observed | chance | corrected | z |
|---|---:|---:|---:|---:|
| pooled | 0.742 | 0.742 | **0.000** | — |
| A (muni + 1 day) | 0.251 | 0.059 | **0.192** | 28.7 |
| B | 0.000 | 0.000 | 0.000 | — |
| C (district + 7 days) | 0.602 | 0.719 | −0.116 | −25.0 |

Pooled overlap reads **0.742 — higher than the true 0.60 — and is entirely
chance.** With ~870 BIPAD incidents across 77 districts on monsoon-clustered
dates, almost any news event finds *some* BIPAD row within a week in the same
district. **Tier C is noise, and Tier C is what the old code called "recall".**

Only Tier A carries signal, so chance correction is computed **per tier**;
pooling lets the loosest tier dominate and hides this entirely. If you take one
thing from this rewrite into the paper, it is that table.

Layer 1 collapses per-household BIPAD rows to incidents (ratio 1.77 synthetic)
and reports it as a finding about the two units. Layer 4 is Chapman
capture–recapture with the independence assumption stated — media-triggered
BIPAD reporting makes it a **lower bound**. Layer 5 is district-year Spearman
plus Bland–Altman. Layer 6 samples both unmatched sets for the discussion.

The old module is left in place; switching `--stage bipad` is a one-line change
once a real export exists.

### Tenth pass: the data problem, diagnosed

**The inventory is a two-source corpus before 2020.** Articles per source-year
showed holes that follow the discovery method exactly:

| method | sources | earliest |
|---|---|---|
| tag pagination | myrepublica, setopati | 2012, 2017 |
| **Google News RSS** | himalayan-times, ekantipur, kathmandu-post, rising-nepal | 2015\*, 2019, 2019, 2022 |

Google News RSS `site:` queries return only recent items and **never backfill
archives** (§9.11, now confirmed). eKantipur and the Kathmandu Post — two of
Nepal's largest outlets — contribute essentially nothing before 2025.

**This is the cause of the 4.5× 2024/2016 ratio.** Not landslide activity, not
recency bias in reporting — four of eight sources simply have no pre-2023 data
in the corpus. The "eight bilingual sources" claim is unsupported for 2015–2019.

\* himalayan-times reaches 2015 but 615 of its 992 rows are 429 error pages.

**The 429s were a one-branch bug.** `scrape/fetcher.py` returned immediately on
any `HTTPError`, so a 429 was accepted as the site's answer and its error page
stored as the article body. Now retries with backoff, honours `Retry-After`, and
stores **no text** on final failure so a failed row cannot be mistaken for an
article. Recovering these is worth ~600 articles concentrated in 2015–2020 — the
years that most need them.

**`scripts/verify_entry_points.py`** checks candidate archive URLs before they
go into config (200? 10+ article links? does pagination advance?) and emits
ready-to-paste YAML. Tag slugs change, so the candidates in it are hypotheses,
not verified URLs.

**`docs/COLLECTION_RUNBOOK.md`** has the four steps in order. All of it runs on
the operator's machine — this sandbox cannot reach any Nepali news domain.

**Free LLM: use a local model.** `ollama_caller()` added, and `build_caller()`
prefers local over hosted over rules. For this project local is better *on the
merits*: a hosted API is a moving target while a local model is a pinned
artefact that replays offline years later, which is what a reproducibility claim
needs. Temperature 0, fixed seed, `qwen2.5:7b` for Devanagari. The quality trade
at 7B is exactly what `--stage benchmark_adjudicator` measures.

### Open decisions for the operator

Items 1–4 were decided and applied this session (see above). Remaining:

1. **Label the locked test set.** Rubric reconciled
   (`docs/ANNOTATION_RUBRIC.md`), tool built (`tools/annotate.html`). This is
   the only remaining hard blocker on every number in the paper.
2. **The roundup over-merge.** Nationwide roundups ("At least 148 are dead in
   floods and landslides in Nepal") are still entering as class-1 events with a
   district, and they attract merges. Fixing them upstream in
   `event_specificity` would shrink the largest clusters and is probably the
   next-highest-value item.
2. **Re-fetch the 615 himalayan-times HTTP 429 URLs**, with backoff. They are
   real articles that were never retrieved. This is the single largest remaining
   data-quality item and it may materially change the source balance, the year
   distribution, and the `title_only` count — many thin bodies share the same
   rate-limiting cause. Not attempted here because it needs live network access
   to the outlet.
2. **`landslide_inventory_final_snapshot_20260423.sqlite`** differs from the
   working DB and has no generating code. Needs a `DATA_VERSION` pointer or
   deletion.
3. **`canonical_events_final.orphaned_20260423.csv`** is kept only so the
   reproduction can be re-checked. Delete once you are satisfied with it.
4. **Label the locked test set.** Nothing downstream can be measured until this
   happens.

### For whoever picks this up next

The locked test set at `data/outputs/locked_test_set_v1_labels.csv` is **drawn
but not labelled**. It is the gate on everything else: §5 says do not tune a
single rule before it exists, and it now exists. Label it (blind — the
predictions are in a separate file, keep them there), double-annotate ≥100 rows
for Cohen's κ, and only then start measuring.

~~The highest-value piece of work remaining is §8.1.~~ Superseded — see the
third pass above. Kathmandu is now #2 at 49 headline events, fixed by removing
the dateline fallback and separating avalanches, not by role classification.

§8.1 is still worth doing, but it is now a *smaller* job than the review implies:
the dateline machinery already exists and is enforced, so what remains is the
genuinely-wrong-district residue (Kakani → Nuwakot, Langtang → Rasuwa,
Helambu → Sindhupalchok). Start with the gazetteer alias gap — "Makawanpur" not
normalising to Makwanpur is likely a one-line fix with immediate effect.

Ahead of it in value now: **§8.2 cross-language dedup**. Multi-source clusters went 69 → 81 after
the re-run, but that is still ~7% of 1,127. `token_set_ratio` cannot match
Devanagari against Latin, so an ekantipur and a Kathmandu Post report of the same
event score ~0 and can never merge. Since bilingual coverage correlates with
severity, large events are systematically double-counted relative to small ones.

Neither was attempted in this session.

### Environment note

The repo targets Python 3.12; the sandbox used here had only 3.10, so
`datetime.UTC` was shimmed for test runs. Nothing about that shim is in the
repo. The `.venv/` in the project root is a macOS venv and will not run on
Linux.

---

## Session 2026-08-08 — the re-collection landed, and the age bug it exposed

### What the re-collection bought

`scripts/recollect.sh collect` completed against the politer crawl rate. The
before/after, measured with `recollect.sh check`:

| | before | after |
|---|---|---|
| articles | 4,453 | **4,889** |
| usable (http 200, 200+ chars) | — | **4,646** (95%) |
| headline landslide events | 772 | **951** |
| HTTP 429 pages stored as articles | 615 | **0** |
| en–np dedup merge rate | 22.9% | **24.9%** (207/832) |
| 2024 / 2016 event ratio | 4.5× | **1.9×** |

**The ratio is the result that matters.** `scripts/recollect.sh` set 2× as the
threshold at which the temporal analysis stops being an artefact of Google News
recency bias. 2016 went 34 → 79 events, almost all from himalayan-times (+45)
and myrepublica (+34) — i.e. exactly the outlets the 429 storm had gutted. The
year curve is now flat enough to analyse, and the residual skew is small enough
to state as a limitation rather than a disqualification.

Spatial quality held while the corpus grew by 10%, which is the check that
matters more than the totals:

- Kathmandu fell to **6th** (37 events), behind Chitwan 55, Baglung 41,
  Dhading 41, Myagdi 40, Gulmi 37. It was #1 before the dateline fix.
- Terai share excluding Chitwan: **2.9%** (was 3.0%). Physiographically correct.
- 2026 monthly: Jan 1, Mar 11, Apr 2, May 2, Jun 3, **Jul 24**, Aug 8 — a
  monsoon peak in a partial year, as expected.

### The number that regressed, and why

Deaths/year moved **130 → 150**, so the DRR Portal cross-check — the project's
strongest external validation, previously a ratio of exactly 1.00 — drifted to
~1.15. Rather than accept it, I looked at where the deaths were: **68% of the
1,800 total sat in 50 events, and 38 of the 60 deadliest carried a deaths value
that appears nowhere in their own title.**

Reading those articles found a second casualty failure mode, distinct from the
aggregate-total bug fixed on 2026-08-06. **Ages were being read as death counts.**

```
"Tikaram BK, 65, Ramu Kumari BK, 55, ... and Nanda Kali Parajuli, 65
 were killed in Bhadaure"
```
→ 65 deaths, in an article headlined *"Death toll in Kaski landslides climbs
to 20"*.

```
"मृतककी ९० वर्षीया सासू टुलकीमाया"   (the deceased's 90-year-old mother-in-law,
                                      who survived)
```
→ 90 deaths, the largest single figure in the entire inventory, for an article
reporting **one** woman's death.

The Nepali case is structural, not incidental: the reverse pattern is
`(?:मृत्यु|मृत)[^0-9]{0,8}(\d+)`, so *any* digit within eight characters of a
death word becomes a toll — and Nepali reporting convention puts the victims'
family's ages exactly there.

### The fix — `_is_age_context`, in both extractors

Nepali is easy and unambiguous: an age is followed by वर्ष / बर्ष and their
adjectival forms. A count of dead people is never followed by "years".

English needed care, because a **dateline produces the same shape as an age
apposition**: `"Landslide buries two houses in Gulmi, 4 dead"` is a real count,
and a naive "capitalised word, comma, number" rule eats it. Three conditions
separate them:

1. the number is in digits (word numerals are never ages in this corpus);
2. it is preceded by a capitalised token and a comma;
3. a **complete** apposition — `Name, NN,` — appears nearby, either because this
   number is itself followed by a comma or because an earlier victim in the same
   list was.

One name-then-number is a place and a count. A *run* of them is a casualty list.
`"at least 3, including 2 children, were killed"` fails condition 2 (lowercase);
`"in Gulmi, 4 dead"` fails condition 3. Both are covered by tests.

**Measured effect** (re-extracting all 951 headline events against the new code,
without writing to the database):

| | before | after |
|---|---|---|
| total deaths | 1,800 | **1,603** |
| deaths / year | 150 | **134** |
| DRR Portal ratio | 1.15 | **1.03** |
| events changed | — | 4 |
| events where deaths *increased* | — | **0** |

Four events, 197 phantom deaths, and the cross-check returns to ~1.0 against an
independent national source. That a fix touching four rows moves a headline
statistic by 11% is itself the finding: the casualty field is dominated by its
tail, so tail errors are the only casualty errors worth hunting.

### Known limitation this fix exposes (do not treat as a regression)

The four corrected events now report **no deaths** rather than their true small
values, because the veto removes the wrong number and nothing else matches:

| article | truth | recorded |
|---|---|---|
| "Death toll in Kaski landslides climbs to 20" | 20 | none |
| "काठमाडौंमा पहिरो जाँदा एकको मृत्यु" | 1 | none |
| "…पाँच मजदुरको मृत्यु" | 5 | none |
| "मोरङको…महिलाको मृत्यु" | 1 | none |

Two separate gaps, both real and both small:

- **Nepali word numerals are not parsed at all** — एक, दुई, पाँच. English word
  numerals are (`_parse_count` handles "four dead").
- **"Death toll … climbs to N"** does not match either English pattern, because
  the terms list has `dead`/`deaths`/`killed` and `\b` stops `Death toll` from
  matching `dead`.

Recording *unknown* instead of *90* is the right trade — a missing value is
honest, a fabricated one is not — but both gaps are worth closing, and the
second is nearly free.

### Landmine for the next contributor

**Do not audit the casualty field by its mean.** Mean deaths per fatal event was
6.9 both before and after a fix that removed 197 deaths, because the errors live
in five rows out of 259. The diagnostic that actually works:

```python
# how many of the deadliest events carry a number absent from their own title?
```

38 of 60 before the fix — **and still 38 of 60 after it**, which is the part
worth understanding. It is a *rank-based* metric over the top 60, so removing
the worst offenders simply promotes the next candidates into the window. It
diagnoses **where to look**; it does not measure progress. For progress, use the
total and the DRR ratio, which did move (1,800 → 1,603; 1.15 → 1.03).

### Where this leaves the outstanding work

`scripts/recollect.sh` Step 1 is **done and verified**. Step 2 —
`scripts/verify_entry_points.py`, finding real archive entry points for
eKantipur (~9 missing years) and Kathmandu Post (~11) — is now unambiguously the
highest-value item left, and it is the one that needs a human at a browser.
Everything else (test set v2, the local-LLM benchmark, the `analysis` stage,
real BIPAD agreement) is downstream of having the corpus settled.

### Step 2 was the wrong plan — what probing the sites actually showed

`docs/DO_THIS_NEXT.md` Step 2 assumed each configured source had an archive door
we simply had not found. Probed live on 2026-08-08 (browser with JS rendering,
so this is not a "the crawler can't run JavaScript" artefact):

| probe | result |
|---|---|
| `kathmandupost.com/tag/landslide` | returns the homepage. No tag archive exists. |
| `kathmandupost.com/national?page=60` | page parameter ignored; serves today's stories |
| `ekantipur.com/sitemap.xml` | 404 |
| `ekantipur.com/Kantipur-Archive` | a *retrospective column*, not a site archive |
| Google News RSS `after:`/`before:` | **works** — a 2016-06/2016-10 window returned only 2016 items |

That last one looked like the answer until the item links turned out to be
`news.google.com/rss/articles/CBMi…` encoded redirects rather than article URLs.
Google changed that encoding in 2024 and it is not resolvable without an extra
request per item. Almost certainly why the path was abandoned.

**And the Google News path contributes nothing at all.** Not "recency-biased" —
zero:

```
discovered_urls by method     raw_articles by method
  sitemap      2015             sitemap      2014
  search       1615             search       1567
  googlenews     16             googlenews      -- absent
```

Those 16 rows are the feed URLs themselves. `collect.py:67` skips
`method == 'googlenews'` before fetching. Every article in this project came
from a sitemap or a site search. Any statement in older docs about Google News
coverage bias is describing a path that was never carrying traffic.

### The real hole, which is worse and more interesting than the stated one

Usable articles (http 200, 200+ chars) by source and year:

```
source              15   16   17   18   19   20   21   22   23   24   25   26
ekantipur            ·    ·    ·    ·    1    1    ·    ·    1    ·   11  397
kathmandu-post       2    ·    ·    ·    ·    ·    2    ·    ·    ·    ·   84
online-khabar        ·    ·    ·    ·    ·    ·    ·    ·   49  175   78   75
ratopati             ·    ·    ·    1    ·    ·    ·    ·    1    1   70  286
setopati             ·    ·   63   64   85  240  223  150  166  331  153   53
himalayan-times    140  172  112   78   62  128   29   14   11   33   17    7
myrepublica         97  119   90  115   82  102   79   79   83  156   10    ·
rising-nepal         ·    ·    ·    ·    ·    ·    ·   31    ·    4    ·   14
```

Two structural facts, neither previously written down:

1. **Nepali-language coverage barely exists before 2023.** Setopati is the only
   Nepali source with depth, and it starts in 2017. Everything else is 2023+.
2. **Both English workhorses collapse in 2025–26** (myrepublica 10 then 0;
   himalayan-times 17 then 7), while the Nepali sources spike there. The
   apparent 2026 corpus is almost entirely Nepali; the apparent 2015–2019 corpus
   is entirely English.

**This puts a caveat on a result recorded above.** The session of 2026-08-07
recorded "en 0.779/0.372, np 0.827/0.426 — Nepali is not the weaker path". That
was measured over a corpus whose Nepali half is essentially 2024–2026 and whose
English half is essentially 2015–2020. It is not a like-for-like language
comparison; it partly compares eras and outlets. The operator elected (2026-08-08)
to fix the corpus before re-scoring, which is the right order — the v1 test set is
already spent and should not be scored a third time against a moving corpus.
Re-derive this number on a year-matched subset once coverage is balanced, and
until then do not put the bilingual claim in the paper.

### `scripts/prospect_sources.py` — the replacement for Step 2

Adding outlets is no longer optional: a bilingual inventory whose Nepali half is
three years long cannot support a bilingual claim, and no amount of tuning fixes
that. The new script probes ~19 additional Nepali and English outlets and reports
**archive depth** — earliest and latest year demonstrably reachable — rather than
"does this URL return 200". A tag page with 40 links from last month scores zero
here; a sitemap index reaching 2014 is the whole game.

It checks the two shapes that already work in this repo, in order of proven value:
sitemaps first (how myrepublica and himalayan-times got their 2015–2024 depth,
and `discovery.py` already has the machinery), then search/tag endpoints (the
setopati and ratopati shape).

Strongest prior in the list: **nagariknews.nagariknetwork.com** — same publisher
as myrepublica, whose `sitemap_news` discovery already works here, so an
identical sitemap shape would cost almost no new code and is Nepali-language with
real depth. Others worth watching: gorkhapatra (state daily, oldest paper in
Nepal, sibling of rising-nepal), himalkhabar, pahilopost and lokaantar (all
2015-onward digital natives), and nepalitimes on the English side.

Run it on a networked machine; the sandbox cannot reach Nepali domains.

```
PYTHONPATH=src .venv/bin/python scripts/prospect_sources.py --lang np
```

### Confirmed after the operator's rebuild (2026-08-08, 14:09)

481 tests pass. The age veto persisted through a full rebuild exactly as the
dry-run predicted:

```
headline events   951        (unchanged -- the veto changes casualty VALUES,
total deaths     1603         never event membership, which is the check that
deaths / year     134         matters most for a fix like this)
DRR ratio        1.03
fatal events      255   mean 6.3
```

Event counts, year curve and merge rate are all identical to the pre-fix
rebuild (951 headline, 2024/2016 = 1.9x, en-np 24.9%), which is the correct
outcome: nothing was dropped, four numbers were corrected.

### What the residual death tail is now — roundups, not ages

With ages gone, the eight largest figures are a different failure mode:

| deaths | title |
|---|---|
| 67 | कर्णालीका ९ जिल्ला पहिरोको **जोखिममा** (9 districts *at risk*) |
| 60 | Floods, landslides kill 60 **across Nepal since Friday night** |
| 55 | 55 killed in **21 landslide incidents** in Gandaki **Province** |
| 35 | **बाढी–पहिरोबाट** ३५ जनाको मृत्यु (flood *and* landslide, combined) |

These are the **roundup over-merge** already listed as an open item — regional
and national running totals that survived `event_typing` and were assigned a
single district. The 67 is worse than a bad casualty count: it is a *risk
warning* that became an event at all.

The top 8 events hold ~24% of all recorded deaths, so this is where the next
real casualty gain is. It is a `event_specificity` / `event_typing` problem, not
an extraction one — the number in each of those titles is correctly extracted,
it just should not be attached to one district.

Deliberately **not** fixed in this session: the operator's stated priority is
corpus coverage (see `prospect_sources.py`), and a ratio of 1.03 against the DRR
Portal is defensible in the meantime. Do this next after sources.

### `prospect_sources.py` crash on first run — and the general lesson

First live run died on candidate #1:

```
http.client.IncompleteRead: IncompleteRead(3259 bytes read, 1 more expected)
```

`fetch()` documented itself as "never raises" and then listed the exceptions it
expected: `URLError, TimeoutError, OSError, ValueError`. `IncompleteRead` is
none of those — it subclasses `HTTPException` — so one server sending a
Content-Length one byte longer than its body ended a 13-site run before any
result was printed.

Two fixes, both worth keeping:

1. **`except Exception`, deliberately.** When a function's contract is "never
   raises, a dead candidate is data", an exception allow-list is the wrong
   shape — it will always be missing the next one. Same reasoning as the
   per-source `try/except` already in `scrape/collect.py`.
2. **`IncompleteRead` is recoverable, not fatal.** The bytes already read are on
   `exc.partial`, and for a sitemap a truncated tail still proves the archive
   depth we are measuring. Discarding it would have thrown away a usable answer.

The per-candidate loop in `main()` is now wrapped too, so a failure names itself
inline and the run continues.

**Landmine, generalised:** this repo now has three separate incidents of one
malformed remote response destroying a long unattended run — the myRepublica
XML `ParseError` in `collect`, the 429 pages stored as article text, and this.
Any function that talks to eight-plus independent Nepali news sites in a loop
should assume the response is malformed and keep going, loudly.

Verified with three unit checks (recovered `IncompleteRead` yields depth
2015-2024; a raw `RuntimeError` returns cleanly; truncated gzip falls back to
raw bytes) before handing it back.

**Note for the operator:** run it as `.venv/bin/python scripts/prospect_sources.py`.
Executing it directly (`scripts/prospect_sources.py`) gives "permission denied"
because Box does not preserve the execute bit — the same reason
`scripts/recollect.sh` self-invokes with `bash "$0"`.

### The first prospector run reported fabricated depth — read this before trusting a depth number

12 of 13 Nepali candidates returned a reachable index. The depth column was
**wrong for every sitemap-index site**, and the cause is worth recording because
it is this project's recurring failure shape.

`probe_sitemaps` followed `sorted(locs)[0]` — the alphabetically first child of
the sitemap index. On WordPress that is essentially never a post sitemap:

| reported | actually followed | what those dates are |
|---|---|---|
| deshsanchar 2001-2026 (10 yrs) | `author-sitemap.xml` | author profile timestamps |
| rajdhani 2000-2026 (18 yrs) | `attachment-sitemap.xml` | image upload dates |
| lokaantar 2018-2026 (7 yrs) | `sitemap-categories.xml` | category page dates |
| nepalpress 2020-2026 (7 yrs) | `wp-sitemap-posts-npauthor-1.xml` | author archives |

An author profile's `lastmod` says nothing about whether the outlet's 2015
articles are reachable, which is the only question the script exists to answer.
A "rajdhani reaches back to 2000, 18 years" would have been a very attractive
number to act on, and it is an artefact of image uploads.

**This is the same failure as `is_landslide_hazard` failing open and as the 429
pages stored as article text: a plausible number produced by a check that was
never actually looking at the right thing.** The tell is identical each time —
the output looked *better* than expected rather than worse.

Fixed:

- `NON_ARTICLE_SITEMAP` excludes author/attachment/category/tag/taxonomy/page/
  user/image/video/web-story/amp children explicitly.
- `ARTICLE_SITEMAP` prefers children naming posts/articles/news/stories or
  carrying a year.
- `choose_children()` samples the **oldest, middle and newest** rather than one,
  sorted by any year embedded in the child's name (WordPress writes monthly post
  sitemaps as `sitemap-posts-post-2015-07.xml`, so this is usually a true
  chronological sort). One unlucky pick can no longer decide a verdict.
- Depth now counts **only article URLs**, never the index's own `<lastmod>` —
  those record when each child was regenerated, which for a live site is always
  "recently".
- The report prints which children it sampled, so a bogus depth is visible in
  the output rather than having to be reverse-engineered.
- A sitemap that exists but proves no depth now *also* falls through to the
  search/tag probe. Previously a useless index masked a usable search endpoint,
  which is why annapurnapost (1,265 children) reported nothing.

Verified against the actual child lists from the failed run: deshsanchar now
selects `post-sitemap1.xml` / `post-sitemap12.xml`, WordPress selects
`wp-sitemap-posts-post-*` over `-npauthor-` and `-page-`, a monthly-named set
sorts chronologically and yields 2015/2020/2026, and an all-taxonomy index
correctly returns nothing rather than guessing.

**Standing rule: a depth figure with no sampled-children list beside it is not
evidence.** Re-run before drawing any conclusion about which outlets to add — no
source should be wired into `config.yaml` on the strength of the first run's
numbers.

### Second prospector run — and the `<lastmod>` mistake that made it look empty

Rerun with honest child selection. Nine of eleven reachable candidates now said
**"no dated URLs"** — the script had stopped answering the only question it
exists to answer.

Cause: over-correcting the previous bug. Having established that a sitemap
*index's* `<lastmod>` is meaningless (it records when each child file was
regenerated, always "recently"), I stripped `<lastmod>` from the child files
too, passing only the `<loc>` URLs to the year counter. But **most Nepali
outlets use opaque article URLs** — `deshsanchar.com/?p=12345`,
`nagariknews/news/98765` — with no date in them anywhere. In a child urlset,
`<lastmod>` is per-article and is the closest thing to a publication date the
sitemap offers. Discarding it threw away the only signal those sites carry.

The distinction is now explicit in `years_in(text, use_lastmod=...)`:

| file | `<lastmod>` means | count it? |
|---|---|---|
| sitemap **index** | when the child file was regenerated | **no** — invents depth |
| child **urlset** | when that article was published/modified | **yes** — the only signal |

Two smaller fixes in the same pass:

- **`PLAUSIBLE_YEARS = 2005-2026`.** kendrabindu reported "2000-2000 (1 yr)" from
  a slug that merely looked like a year. Nepal's news sites went online in the
  mid-2000s; anything outside that band is an id, not a date.
- **Paginated news sitemaps sort numerically.** annapurnapost and lokaantar both
  expose `sitemap-news.xml?p=N` with 1,265 and 1,624 children and no year
  anywhere in the names. Sorted lexically, `?p=999` comes before `?p=1000`, so
  the "newest" sample was an arbitrary middle page. Higher `p` is normally
  older, so a numeric spread is what actually probes the far end of the archive.
  These two are the most promising shapes seen so far — a deep paginated news
  sitemap is exactly the door eKantipur and the Kathmandu Post do not have.

Verified: a child urlset with opaque URLs and 2015/2016/2026 lastmods now reads
2015-2026; an index whose children were all regenerated today reads "no dated
URLs"; the 2000 artefact is gone; paginated children sample p=none/100/1000.

**Read the third run, not the first two.** Run 1 fabricated depth from author
and attachment sitemaps; run 2 reported almost none because it discarded
`<lastmod>`. Neither is evidence about these outlets.

### Third prospector run — the first trustworthy numbers, and two viable sources

With index-vs-child `<lastmod>` handled correctly, the Nepali candidates rank:

| source | depth | shape | children |
|---|---|---|---|
| **rajdhani** | **2007-2026 (13 yrs)** | `post-sitemap{N}.xml` | 135 |
| **deshsanchar** | **2008-2025 (10 yrs)** | `post-sitemap{N}.xml` | 271 |
| nepal-press | 2021-2026 (5 yrs) | `wp-sitemap-posts-post-{N}` | 98 |
| lokaantar | 2017-2026 (4 yrs) | `sitemap-news.xml?p=N` | 1,624 |
| annapurna-post | 2023-2026 (2 yrs) | `sitemap-news.xml?p=N` | 1,265 |
| kendrabindu | 2025-2026 | — | 115 |
| gorkhapatra | 2026 only (search) | `?s=` | — |
| nagarik, baahrakhari, ujyaalo, pahilopost | no depth provable | — | — |
| naya-patrika, himalkhabar | nothing reachable | — | — |

**rajdhani and deshsanchar are the two candidates that actually address the
hole** — both Nepali, both reaching back before 2015, both plain WordPress
`post-sitemap{N}.xml` which the existing sitemap machinery already understands.

Note the prior that failed: **nagarik**, reasoned to be the best bet because it
shares a publisher with myrepublica, has no article-like sitemap children at all.
A shared publisher does not imply a shared CMS.

Also note annapurna-post: 1,265 sitemap children but only 2023-2026 of depth.
Volume of children says nothing about archive depth — a busy site simply shards
more finely.

### The config validator was blocking all of this

Two hard-coded checks refused to start whenever a source was added:

```python
config.py:  if len(sources) != EXPECTED_SOURCE_COUNT:    # exactly 8
            if slugs != EXPECTED_SOURCE_SLUGS:           # exact set equality
sources.py: if len(sources) != EXPECTED_SOURCE_COUNT:
```

Already on the landmine list as "**still open**". The instinct was right — catch
silent config drift — but the rule was too strong, and it was blocking the
project's highest-value remaining work. Now a **subset** check:

- dropping one of the original eight still hard-fails, because every coverage
  baseline in this log is stated against that source set;
- adding a source is allowed, since that is the intended direction of travel;
- a new duplicate-slug check replaces the protection the count check used to
  give incidentally.

Three tests cover the three cases. **This landmine can now be struck through.**

### Do not wire deshsanchar/rajdhani in yet — one question is unanswered

`discover_himalayan_times_sitemaps` filters candidates with
`keyword_match(article.url, ...)`: it looks for the landslide keyword **in the
URL**. That works for himalayan-times, whose slugs are English words. For a site
using opaque ids (`/?p=12345`) it returns **nothing**, and depth alone cannot
tell you which case a site is in. Crawling to find out is not an option — 271
sitemap children is on the order of a quarter of a million URLs.

`--inspect SLUG` answers the two questions that decide how (or whether) a source
can be wired in:

- **Q1** do article URLs carry the keyword? → sitemap + keyword filter works,
  source is nearly free to add.
- **Q2** does the search endpoint paginate backwards in time? → use the
  setopati/ratopati search shape instead, which filters server-side.

A source needs a yes to one of them. Both no means the archive is reachable but
not *searchable*, and it should be skipped rather than crawled blindly.

```
PYTHONPATH=src .venv/bin/python scripts/prospect_sources.py --inspect rajdhani
PYTHONPATH=src .venv/bin/python scripts/prospect_sources.py --inspect deshsanchar
```
# 2026-08-09 — independent development set

Added a deterministic `development_set` stage for post-v2 pipeline tuning. It
uses the same orthogonal labeling columns as the locked evaluation while
keeping predictions separate. Before sampling it excludes all locked-test
URLs, prior development rows, previously annotated manual-evaluation rows, and
BIPAD-assisted discoveries. The default 300-row allocation is balanced across
available English/Nepali strata and emphasizes dropped-specificity rows. The
manifest makes the contamination checks and zero-overlap requirement auditable.

# 2026-08-09 — locked v2 scorer definition correction

The completed v2 labels were frozen unchanged before correcting the evaluator.
The original scorer mixed the orthogonal rubric dimensions in two ways: it
treated every granularity except `roundup` as headline truth (so `multi` was a
positive), and treated only `kept_class1` as a pipeline headline prediction
(so district/date extraction failures were counted as event-detection misses).
Its road-obstruction helper was also disconnected from the canonical
`event_type`/`hazard_type` logic.

The corrected scorer now:

- requires `event_granularity_true=single` for headline truth;
- treats retained Class-1 or Class-2 articles as candidates, then applies the
  same aggregate/road/hazard typing used by the canonical inventory;
- reports district and event-date extraction separately;
- reports deterministic within-stratum weighted bootstrap confidence
  intervals rather than attaching an unweighted Wilson interval to a weighted
  point estimate; and
- records SHA-256 hashes of the frozen labels and typed prediction snapshot in
  the score report.

The pre-correction score remains an audit artifact and must not be reported as
the v2 result. No labels or pipeline classification rules were changed.

### Development-set generation audit

Generated `development_set_v1` after the corrected v2 evaluation was frozen.
The frame contained 4,889 non-assisted articles; 913 prior-evaluation URLs were
present in that frame and excluded, leaving 3,976 eligible articles. The final
sample has 300 unique URLs, zero overlap with prior evaluation, zero
BIPAD-assisted URLs, and zero pre-filled truth cells. Its separate prediction
file contains the same 300 URLs. All 514 tests, Ruff, `git diff --check`, and
the source-shadowing check passed before generation.

### Development labels completed and diagnosed

The completed v1 development labels passed structural validation: all 300 rows
and protected metadata match the blank reference, every controlled value is in
vocabulary, every annotator is present, and dates/deaths/triggers are canonical.
Three rows are legitimately undecidable (two inaccessible 404 articles and one
event with no resolvable country), leaving 297 diagnostic rows. The frozen label
SHA-256 is `10c52ee53e90c53ca71513e603b4ba527b15902ef01798d353e46188fd2fb49b`.

The unweighted development sample has 41 TP / 27 FP / 46 FN / 183 TN. These
counts are for rule diagnosis only, not held-out or population performance.
The errors reveal two target-definition mismatches before any lexical tuning:

- 25 of 46 apparent false negatives were typed `road_obstruction`, even though
  the annotation headline definition counts a real single-event road landslide;
- 13 of 46 false negatives were labelled `follow_up`, while the specificity
  stage treats follow-up language as a hard negative even for one concrete
  event.

The dominant ordinary false-positive issue is granularity: 20 of 27 are
`multi` and five are `roundup`. The remaining two are one missed avalanche and
one preparedness article. Among non-road false negatives, broad `risk_only`
(7), `out_of_country` (4), `followup` (4), `roundup` (3), and `context_only`
(2) rules suppressed concrete events. Do not add isolated keywords yet. First
align whether road-only events and specific follow-ups belong in the target;
then implement explicit granularity logic and re-audit these broad patterns.

### Development-guided classifier correction completed

Implemented the v1 development findings while preserving both the frozen label
file and the original prediction snapshot. The operational changes are:

- headline truth/prediction now uses explicit `event_granularity=single`;
- real single road-obstruction reports remain typed but count as landslide
  observations, while BIPAD eligibility remains restricted to ordinary
  landslide events;
- concrete follow-up articles are retained as event evidence and first reports
  are preferred as cluster representatives;
- class 2 is treated as an extraction-confidence bucket rather than an event
  ontology, so typed single class-2 events can enter dedup;
- multi-event, roundup, forecast/risk, avalanche, flood, and foreign-event
  reports are filtered by explicit orthogonal labels before dedup;
- event detection can succeed even when district/date extraction fails; and
- foreign-place matching no longer mistakes Indian/भारतीय victims or teams for
  an event located outside Nepal.

The final v1 development comparison (297 decidable rows) is:

| snapshot | TP | FP | FN | TN | precision | recall | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| pre-tuning baseline | 41 | 27 | 46 | 183 | 0.603 | 0.471 | 0.529 |
| deterministic tuned | 77 | 22 | 10 | 188 | 0.778 | 0.885 | 0.828 |

These are unweighted development-sample diagnostics and must not be reported
as held-out performance. The rebuilt canonical export contains 1,617 typed
single-event records, including 343 `road_obstruction` subtypes. A local
`qwen2.5:7b` adjudicator benchmark reached precision 0.638, recall 0.770, and
F1 0.698 on its development judgement-call rows; because it did not beat the
deterministic tuned pipeline, it remains optional and was not adopted for the
production inventory. A new untouched locked v3 is required for final metrics.

### Untouched locked v3 drawn

Generated the post-development `locked_test_set_v3` with seed 20260810. The
non-assisted article frame contained 4,889 URLs. The exclusion audit found
1,214 unique prior-evaluation URLs, 1,213 of them in the frame, leaving 3,676
eligible URLs. The final sample has 386 unique URLs and zero overlap with locked
v1/v2, development v1, labelled manual verification, or BIPAD-assisted
discovery. Its 14-row shortfall from the requested 400 is explicit in the
manifest: only 6 `dropped_other` rows remained (9 short) and no
`no_extraction` rows remained (5 short).

All 4,632 truth cells in the working label file are blank; the reference URL
lock and label/prediction SHA-256 hashes verify; label and prediction row IDs
match. Generation, checking, scoring, prediction refresh, and adjudicator paths
now resolve the configured locked-test version instead of a hard-coded v2.
Checking blocks blank controlled judgements, scoring blocks incomplete or
structurally altered labels and changed predictions, and the first valid score
freezes a completed-label copy. The v1/v2 artifacts remain untouched.

### Locked v3 scored and final release sealed

All 386 v3 rows were completed; 382 were decidable and four were excluded as
undecidable. The population-weighted held-out article result is precision 0.680
(95% CI 0.609–0.749), recall 0.851 (0.787–0.915), and F1 0.756
(0.702–0.809). District exact accuracy is 0.819 with coverage 0.922 among 123
true headline rows with district truth. Event-date accuracy is not reportable
because only five rows had truth, below the prespecified minimum of 30. Frozen
label and prediction hashes verify.

Release QA found four apparent post-cutoff dates. A tracked, idempotent reviewed
correction layer now records evidence and before/after state: one Myagdi RSS
event was corrected to 2025-08-22, while one foreign Sikkim report, one
multi-event road report, and one aggregate government-damage article were
excluded from canonical construction. These are explicitly post-validation
release corrections; v3 was not rescored.

The rebuilt canonical release contains 1,614 unique single-event records from
2015-04-07 through 2026-08-07, across 73 districts and nine representative
sources, including 343 road-obstruction subtypes. No canonical row occurs after
the 2026-08-10 release cutoff. The canonical CSV SHA-256 is
`1d2a1fcafafbf1863ede9c2a81020d8752026cf52a7665105e68d1322a06584f`.

The release bundle `nepal_landslide_inventory_v0.1.0_v3_20260810` includes the
canonical CSV, SQLite snapshot, frozen evaluation artifacts, correction source
and applied audit, inventory audits, manuscript metrics, and validation report.
Its bundle lock is
`7c123f47be07434fa8f3fb7c1179d8e730d0fd86bcb16196df07d20fc80ec75c`.

### v0.2 older-source expansion and locked v4 draw

Preserved the sealed v0.1 release and copied the working database to
`data/snapshots/pre_v02_collection_20260810_1010.sqlite` before collection.
Added source-native collectors for Nagarik, Deshsanchar, and Rajdhani, plus an
`LS_SOURCE` selector, per-source crawl bounds, current-year URL hints,
structural search-result parsing, oldest-first WordPress traversal, and
resumable fetching that skips already stored clean articles.

The bounded run added 1,055 raw articles: Nagarik 731 (2015–2026), Deshsanchar
170 (2017–2019), and Rajdhani 154 (2020). All parsed successfully; article
quality flagged one short Deshsanchar body. Rebuilding produced 2,008 canonical
events, up 394 from the sealed 1,614: 1,586 headline landslide-family events
and 422 road-obstruction reports. The new sources contribute to 388, 47, and 42
canonical clusters respectively, with overlap between sources and the existing
inventory.

Refreshed external matching at the 2026-08-08 common cutoff: 2,004 news events,
5,345 BIPAD rows collapsed to 4,092 clusters, 3,508 candidate pairs, 3,787
search seeds, and one 796-feature COOLR inventory. BIPAD continues to be framed
as an independent incomplete system rather than ground truth.

Changed the configured locked version to v4 with seed 20260811 and drew 381
rows from 4,345 eligible articles after excluding 1,600 unique prior-evaluation
URLs. Prior-evaluation overlap is zero; 105 rows come from the three added
sources. The lock hash begins `884e23f1727f`. v3 remains frozen validation for
v0.1 and must not be reported as validation of v0.2.

### Deeper archive completion and locked v5 draw

Locked v4 was completed before further collection. Of 381 rows, 373 were
decidable and eight undecidable. Population-weighted headline classification
was precision 0.696 (95% CI 0.626–0.761), recall 0.838 (0.774–0.907), and F1
0.760 (0.706–0.812). District exact accuracy was 0.846 with 0.943 coverage
among 121 rows with district truth; event-date accuracy remained unreportable.

Preserved the scored-v4 database, then completed the configured oldest-first
archive caps. Deshsanchar increased from 170 to 1,200 rows and Rajdhani from
154 to 800, adding 1,676 raw articles without HTTP or parser failures. Four
Deshsanchar rows fail downstream article-quality rules; Rajdhani has no quality
flags. Normalized coverage is 2017–2022 for Deshsanchar and 2020–2024 for
Rajdhani.

The rebuilt database contains 7,624 raw articles and 2,387 canonical records:
1,912 headline landslide-family events and 475 road-obstruction reports.
External matching was refreshed at the common cutoff. Locked v5, seed
20260812, then sampled 383 rows from 5,640 eligible articles after 1,980 prior
evaluation URLs in the frame were excluded. Prior-evaluation overlap is zero;
the lock hash begins `90e6b24c226e`. The blank-state checker confirms zero
answered rows. No further collection or tuning is allowed before v5 scoring.

### Additional-source prospecting, collection, and locked v6 draw

Prospected sixteen candidate national outlets using robots/sitemaps, native
search endpoints, deep pagination, and direct inspection of actual result URLs.
Most were rejected: Annapurna Post and Naya Patrika did not offer meaningful
older depth; Ujyaalo and Baahrakhari had opaque routes without a safe historical
filter; and direct checks proved that Khabarhub English and Lokantar ignored
their query parameter and served homepage/archive content. English OnlineKhabar
and Nepali Times passed both archive-depth and semantic-route checks.

Implemented two bounded source-native collectors: a WordPress REST search for
English OnlineKhabar and URL-keyword filtering over Nepali Times' complete
article sitemap. Both use source-specific URL handling for single-segment
article slugs. Live parser checks recovered a dated 1,012-character OnlineKhabar
body and a dated 1,395-character 2015 Nepali Times body before collection.

Collected 600 OnlineKhabar-English articles (2019–2026) and 12 Nepali Times
articles (including 2014–2016); all 612 parsed successfully and introduced no
new article-quality warnings. Rebuilding produced 8,235 raw articles and 2,498
canonical records: 2,026 headline landslide-family events and 472
road-obstruction reports. The new sources participate in 212 and three
canonical clusters respectively. External matching was refreshed.

Changed the locked version to v6 with seed 20260814. It draws 388 rows from
5,869 eligible articles after excluding 2,363 prior-evaluation URLs in the
frame, with zero overlap. The v6 lock hash begins `dec172a52d22`; its blank
checker correctly reports zero answered rows. v5 was never labelled and is now
an unused checkpoint. No collection or tuning may occur before v6 is scored.

### Locked v6 scoring and final v0.2.0 release

Completed all 388 locked-v6 labels and froze the labelled file before scoring.
Of those rows, 387 were decidable and one was excluded as undecidable. The
population-weighted headline-classification estimates are precision 0.742
(95% CI 0.675–0.807), recall 0.822 (0.744–0.910), and F1 0.780
(0.723–0.834). District exact accuracy is 0.822 with 0.927 coverage among 123
rows with truth. Event-date extraction remains unreportable because only 18
rows supplied date truth.

The first release attempt correctly rejected an OnlineKhabar English record
dated 2026-10-04, after the 2026-08-10 cutoff. Manual review showed that the
April 2026 article retrospectively described widespread Ilam floods and
landslides on 2025-10-04 and 2025-10-05 across more than 200 locations. Added
a fifth versioned correction to set the retrospective date and exclude the
aggregate article from the single-event inventory. The article was not in v6,
so the held-out score remains unchanged.

Rebuilt deduplication, event typing, final export, and audits. The sealed v0.2.0
release contains 2,497 unique canonical events from 2015-03-07 through
2026-08-09, covers 76 districts and 14 representative sources, and has no row
after the release cutoff. The release ID is
`nepal_landslide_inventory_v0.2.0_v6_20260810`; its bundle lock is
`ebd9b05f34f2fa1979a1afb5cc93b40ae344dc60afaeb1dea5a148ef23949f54`.
