# Technical & Methodological Review — Nepal Landslide Inventory

Reviewer role: technical / architecture / data / geospatial / methodology lead
Date of review: 2026-08-06
Code state reviewed: working tree (no git commits exist)
Data state reviewed: `data/raw_sqlite/landslide_inventory.sqlite` (4,453 articles → 1,071 canonical events)

---

## 0. Executive judgement

The engineering scaffold is genuinely good: clean package layout, config validation, deterministic hashing, idempotent-ish SQLite stages, ~296 tests, a real bilingual EN/NP path, and a committed gazetteer. That part is above average for a research repo.

The **scientific content is not currently publishable**, and the gap is not small. Three findings independently block the paper:

1. **The final inventory is roughly half wrong at the event level.** Your own refreshed manual metrics report Class-1 precision = **0.516**. Inspecting the canonical table confirms it: a stock-market metaphor ("सेयर बजारमा ६५ अंकको पहिरो"), a nationwide roundup ("Floods, landslides claim 90 lives so far across Nepal"), and a parliamentary-procedure article are all sitting in `canonical_events` as Class 1.

2. **The district field is systematically biased toward Kathmandu by construction**, and the bias is provable from the scoring code, not just suspected. Kathmandu is the #1 landslide district in your output (89 events). That is geomorphologically impossible.

3. **The evaluation set is not held out.** `manual_refresh` re-scores the same 200 labeled rows against the current model, and the rules were tuned between the two scoring runs (macro F1 0.34 → 0.66 on the *same rows*). Every number in `manual_metrics_refreshed.json` is in-sample. There is currently no unbiased estimate of any pipeline metric.

Additionally: **the manual sample can never measure recall**, because `manual_pack.py` draws only from `in_nepal = 1 AND class IN (1,2)` — the rows the pipeline already kept. Everything the filters throw away is invisible to validation. That matters, because the filters are demonstrably throwing away real events (see §3.1: 172 articles were excluded as "metaphor" for containing the substring `by landslide`, i.e. *"buried by landslide"*).

My recommendation is **not** to patch. The extract → specificity → location → scope chain should be redesigned around a different decomposition. Details in §7.

---

## 1. System understanding & stage map

### 1.1 What the system currently is

A single-pass, article-keyed, rule-cascade ETL over SQLite. Each stage reads `article_events`, makes a decision, and **destructively mutates the same row in place** (nulling `district`, `event_date_ad`, `deaths`, etc. when a row is demoted to class 3). There is no immutable fact table and no decision log separable from the data.

### 1.2 Actual stage map

```
config.yaml ──► AppConfig (config.py; validates fixed 8 sources, fixed study window)
   │
   ├─ smoke .................. init dirs + SQLite schema (db.py)
   │
   ├─ collect ................ scrape/{discovery,fetcher,parser,storage}.py
   │                           googlenews RSS + tag/trend pagination
   │                           ──► discovered_urls (4,470), raw_articles (4,453)
   │
   ├─ normalize_dates ........ preprocess/dates.py  (BS→AD, URL dates, lead-text dates)
   │                           ──► raw_articles.published_date_ad          [MUTATES]
   │
   ├─ lang ................... langdetect/router.py (devanagari ratio + langdetect)
   │                           ──► article_lang (route_lang, mixed_flag)
   │
   ├─ extract ................ unify/extract_stage.py
   │                           ├─ nlp_en/extract.py + nlp_en/places.py   (spaCy + regex)
   │                           ├─ nlp_np/extract.py + nlp_np/places.py   (regex)
   │                           ├─ unify/location.py  finalize_place_extraction()
   │                           └─ class assignment ladder (demote/re-promote)
   │                           ──► article_events (4,453) + article_events.csv
   │
   ├─ event_specificity ...... unify/event_specificity.py
   │                           ~200 hand-written substring/regex patterns,
   │                           additive score, reason precedence
   │                           ──► article_specificity + MUTATES article_events
   │
   ├─ location_consistency ... unify/location_consistency.py   [WHERE class = 1 ONLY]
   │                           re-runs extractor on title; title overrides body
   │                           ──► article_location_check (1,174) + MUTATES article_events
   │
   ├─ filter_scope ........... unify/scope_filter.py
   │                           second, *different* foreign-country detector
   │                           ──► article_scope + MUTATES article_events
   │
   ├─ dedup .................. unify/dedup_stage.py
   │                           WHERE class=1 AND in_nepal=1 AND district AND date
   │                           block by district → rapidfuzz token_set_ratio → union-find
   │                           ──► cluster_summary (1,071) + canonical_events (1,071)
   │
   ├─ inventory_audit ........ validation/inventory_audit.py   (QA tables)
   ├─ audit_canonical ........ validation/audit_canonical.py   (30-row sample)
   ├─ manual_pack ............ validation/manual_pack.py       (biased sample — §5.1)
   ├─ manual_score ........... validation/manual_score.py
   ├─ manual_refresh ......... validation/manual_refresh.py    (re-scores same rows — §5.2)
   ├─ manual_audit ........... validation/manual_audit.py
   │
   └─ bipad .................. bipad/validation.py             (not yet run; design flawed — §6)

   NOT IMPLEMENTED: unify, validate, analysis, geocode/, dedup/ (empty pkg), analysis/ (empty pkg)
```

### 1.3 Where the stage boundaries are wrong

- **`filter_scope` runs after `event_specificity`.** Scope is the cheapest, most decisive filter and must run first. Running it fourth means specificity decisions are made on out-of-country articles, and specificity has already NULLed fields that scope then reads.
- **`location_consistency` runs only on `class = 1`.** The location check is the thing that would *create* correct class-1 rows from class-2 candidates. Gating it on the current class is circular.
- **Foreign-country detection is implemented twice**, differently, in `event_specificity.FOREIGN_TERMS` (has Devanagari terms) and `scope_filter.FOREIGN_TERMS` (Latin-only, word-boundary regex). Two answers, two vocabularies, both mutate `class`.
- **`event_specificity` conflates six unrelated judgements** into one score: is-it-in-Nepal, is-it-an-event, is-it-one-event, is-it-a-followup, is-it-a-metaphor, is-it-a-forecast. These have different error costs and different correct evidence, and collapsing them into a single additive score makes each one untunable.

---

## 2. Top 5 implementation / code risks

### 2.1 `by landslide` in `METAPHOR_PATTERNS` destroys real events — 172 articles
`event_specificity.py:66` lists `'by landslide'` as a political-metaphor marker. It matches **"buried by landslide"**, **"swept away by landslide"**. Measured on the live DB:

| substring | articles containing | dropped as `metaphor` |
|---|---|---|
| ` by landslide` | 177 | **172** |
| `विजय` (a common Nepali given name) | 44 | 28 |

Of 235 total `metaphor` exclusions, ~200 are almost certainly false negatives. `'constituency'`, `'बहुमत'`, `'विजय'` have the same failure mode.

**Related dead-config**: `config.yaml → keywords.exclude` (`political landslide`, `stock slide`, `राजनीतिक पहिरो`) is **never read by any code**. The one place metaphor exclusion is configurable is unused, while a hardcoded list does the work — badly. The stock-market article in your canonical output proves it.

### 2.2 Filter stages are destructive and non-idempotent
`event_specificity.py:164-223` and `scope_filter.py:118-170` `UPDATE article_events SET district = NULL, event_date_ad = NULL, deaths = NULL ...` when a row is demoted. Consequences:
- Re-running `event_specificity` a second time sees `district = NULL`, so `has_location_anchor` flips, the score changes, and the reason can change. **The stage is not idempotent** despite the README's claim that all stages are.
- Provenance is destroyed. You cannot answer "what did the extractor originally think?" for any excluded row — which is exactly what a reviewer will ask, and exactly what you need to audit §2.1.
- The full recovery path is a re-run of `extract`, which is expensive (spaCy over 4,453 docs).

### 2.3 The date pipeline silently produces wrong dates and records no provenance
`preprocess/dates.py:174-220` resolves a date from five competing sources — `published_date_raw`, URL path, `year_hint`, lead-text scan, source-specific override — through an if/elif ladder with no recorded winner. Observed failure in the live DB:

```
published_date_raw = 'April 22, 2026'  →  published_date_ad = '2026-04-01'
```

There is **no `date_method` / `date_source` column**. You therefore cannot report what fraction of event dates are explicit vs. publication-date fallback — a mandatory disclosure for any news-derived inventory. (`class1_fallback_dates.csv` exists with 73 rows, but that is a downstream heuristic, not provenance.)

Also: BS→AD conversion is applied only when `source_lang == 'np'`. An English-language article quoting a BS date is not converted.

### 2.4 The dedup death-count guard is vacuous
`dedup_stage.py:300-305`:
```python
municipality_guard = True
if config.prefer_same_municipality and left.municipality and right.municipality:
    municipality_guard = left.municipality == right.municipality
...
return municipality_guard or deaths_guard or body_guard
```
`municipality_guard` defaults to `True` and is only falsifiable when **both** rows have a municipality. 647/1,071 canonical events (60%) have no municipality. So in the majority of pairs the function returns `True` unconditionally and `dedup.guard_deaths_delta` never applies. The config knob does nothing.

### 2.5 `conf_*` fields are constants, not confidences
`article_events.conf_district` is **1.0 for 1,143 of 1,174 Class-1 rows**. The confidence columns carry no information, yet `dedup.choose_representative` ranks by their sum, and `location_consistency` clamps them as if they were meaningful. Either make them calibrated or delete them; right now they create a false impression of uncertainty quantification.

**Also worth fixing (lower severity):** `db.py` `ALTER TABLE`-based migrations have accreted a 40-column denormalized `article_events` with both `class` and `event_class`, both `url` and `article_url`, both `extracted_event_id` (PK) and a UNIQUE index on `url`. The unique index on `url` hard-codes **one event per article**, which is wrong for multi-event roundups you intend to eventually split.

---

## 3. Top 5 architecture / design risks

### 3.1 Rule cascades cannot be validated, and these were tuned on the test set
`event_specificity.py` is ~200 literal substrings and 15 regexes with an additive score, hand-precedenced. Individually plausible, collectively unauditable. Examples that will fire on true events:
- `'warning'` (RISK_PATTERNS) → matched 22 articles, 13 dropped as `risk_only`
- `'has killed'`, `'overall'`, `'cumulative'` (ROUNDUP_PATTERNS)
- `'बजेट'` (budget), `'अपडेट'` (update), `'खुल्यो'` (opened) → CONTEXT_ONLY / FOLLOWUP
- `'loss'`, `'क्षति'` → DAMAGE_ONLY

The architectural problem is not that rules are used — rules are fine and often preferable to an LLM for reproducibility. The problem is that **there is no mechanism that could have caught these**, because the only labeled data is drawn from the surviving rows (§5.1).

### 3.2 `class` conflates event type with extraction completeness
`extract_stage.py:220-231` demotes Class 1 → 2 when `district is None`, and again when `event_date_ad is None`. So `class` answers "is this a landslide event?" *and* "did we successfully extract two fields?" simultaneously. Consequences:
- Class-1 precision/recall is a mixture of two different quantities and is not interpretable.
- A perfectly-reported fatal landslide with a district our gazetteer missed becomes "not an event".
- The demote-then-re-promote ladder (`_qualifies_for_specific_class_one`, 8 sequential veto conditions) is a symptom, not a design.

**These must be separate fields**: `is_landslide_event` (bool), `event_granularity` (single / multi / roundup), `article_role` (first-report / follow-up / retrospective), and independently `district_resolved`, `date_resolved`.

### 3.3 The class definition is contradicted across three places
| Source | Class 1 means |
|---|---|
| `LABELING_GUIDE.md` | real Nepal event, district identifiable, date usable — **casualties not required** |
| `docs/manual_label_policy.md` | specific Nepal event **with confirmed deaths / injuries / missing** |
| the code | 793 of 1,174 Class-1 rows have zero casualties → follows the LABELING_GUIDE definition |

Annotators labeled against one rubric; the code implements another; the policy doc states a third. A meaningful share of the 0.516 Class-1 precision is definitional disagreement, not model error — and you currently cannot tell how much.

### 3.4 The final deliverable is not reproducible
`data/outputs/canonical_events_final.csv` — the file named like the paper's dataset, with a richer schema (`cluster_size`, `trigger`, `deaths`, `scope_reason`, …) than anything the code emits — is **produced by no code in this repository**. Same for `data/raw_sqlite/landslide_inventory_final_snapshot_20260423.sqlite`.

And: **the git repository has zero commits.** No code version can be tied to any dataset version. For a paper claiming a reproducible pipeline, this is disqualifying on its own and is the cheapest thing on this list to fix.

### 3.5 Config rigidity blocks the fix that the data demands
`config.py:13,50-59` hard-fails unless there are **exactly 8 sources with exactly these slugs**, and `EXPECTED_STUDY_PERIOD` is hardcoded to 2015-01-01..2026-12-31 (while README and `paper_metadata` say 2015–2024). Your data says collection failed for two of the eight sources; the config makes it a validation error to drop or replace them.

---

## 4. Top 5 geospatial / domain / methodological risks

### 4.1 The district assignment is a "first prominent place mention" heuristic, and it is biased to Kathmandu by construction

`unify/location.py:94-101` takes `ordered[0]` — one single best candidate — and calls its district the event district. Ranking is `(-score, start_position)`. The score in `nlp_en/places.py:156-179`:

```python
score += 2.0                              # any trigger word within ±120 chars
score += max(0.0, 2.0 - (start / 800.0))  # explicit prior favouring EARLY mentions
```

A myRepublica dateline — `KATHMANDU, July 12: A landslide killed three in Sindhupalchok…` — puts *Kathmandu* at `start=0` with "landslide"/"killed" inside the ±120-char window. It scores ~12.5. *Sindhupalchok*, mentioned at char ~300, scores ~12.1. **The dateline wins deterministically.**

There is no notion of the *semantic role* of a place mention: event site vs. dateline vs. destination vs. victim's home vs. rescue-coordination office vs. highway endpoint.

Evidence straight out of `canonical_events`:

| Representative title | Assigned | Correct |
|---|---|---|
| "Avalanches disrupt efforts to rescue bodies from landslide-hit **Langtang**" | Kathmandu | **Rasuwa** |
| "Landslide buries moving bus in **Kakani**" | Kathmandu | **Nuwakot** |
| "One person goes missing, four vehicles buried in landslide in **Makawanpur**" | Kathmandu | **Makwanpur** |
| "पृथ्वी राजमार्गको पहिरो… हेलिकप्टरमा **ल्याइयो काठमाडौं**" (*airlifted **to** Kathmandu*) | Kathmandu | Dhading/Tanahu |
| "हिउँपहिरो… शव परीक्षणको लागि **काठमाडौं ल्याइँदै**" (*bodies brought **to** Kathmandu*) | Kathmandu | event district |

Result: **Kathmandu is your #1 landslide district (89 events)**, ahead of Sindhupalchok (43). No reviewer familiar with Nepal will read past that table.

Note the fourth and fifth rows also reveal a **hazard-type error**: `हिउँपहिरो` is an *avalanche*, not a landslide, and it is not excluded anywhere.

### 4.2 Chitwan #2 (83 events) is one highway, one outlet, and no event definition
Inspection shows nearly all Chitwan rows are Narayangadh–Muglin road-obstruction articles from myRepublica ("Landslide disrupts Narayangadh-Muglin section", "Vehicles stranded for hours due to delay in clearing landslide debris", "When landslide smacks trucks ..."). Across the whole inventory, **224 of 1,071 canonical events (21%) have road/highway in the representative title.**

Two problems:
- **No event definition separates a slope failure from a traffic disruption report.** A single corridor generating recurrent minor blockages is being counted as dozens of distinct landslide events.
- The corridor spans the **Chitwan–Tanahu** boundary, so even the district attribution is unstable.

You must decide and state, in the methods section, whether a road-blocking debris slide with no casualties is an inventory event. My recommendation: keep them, but as a **separately flagged `event_type = road_obstruction`** subset, excluded from headline counts and from BIPAD comparison.

### 4.3 Duplicate events survive across languages — dedup is barely functioning
Cluster size distribution: **1,002 of 1,071 clusters are singletons; only 19 clusters span more than one source.** For a bilingual 8-source corpus, a fatal landslide is covered by many outlets on the same day. Cause: `compute_similarity` uses only `rapidfuzz.token_set_ratio` on raw title/body. **Devanagari and Latin text share no tokens**, so an *ekantipur* and a *Kathmandu Post* report of the same event score ~0 and can never merge. The only cross-language path (district + date + deaths) is gated behind the string-similarity check and is unreachable.

This is not a cosmetic problem. Bilingual coverage correlates with event severity, so **large events are systematically double-counted relative to small ones**, biasing both the event count and its spatial distribution.

Secondarily, `token_set_ratio` on 2,000 chars of news body is a poor similarity for *within*-language too: it ignores order and duplicates, so two unrelated monsoon reports easily clear the 0.88 threshold. Over-merge and under-merge simultaneously, in different regimes.

### 4.4 The temporal distribution is a coverage artifact, not a landslide signal

| Year | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 |
|---|---|---|---|---|---|---|---|---|---|---|
| Canonical events | 49 | 38 | 41 | 60 | 52 | 128 | 128 | 100 | 114 | **257** |

2024 is 5× 2016. That is Google News RSS recency bias and site archive depth, not landslide activity — and 2015 (the Gorkha earthquake year, with the Jure/Langtang-era co-seismic landslide record) is one of your *lowest* years, which is diagnostic of the problem.

Source coverage is equally lopsided — the "eight bilingual sources" claim is not supported by the data:

| Source | Articles | Class 1 |
|---|---|---|
| setopati | 1,512 | 546 |
| myrepublica | 1,013 | 364 |
| himalayan-times | 992 | 125 |
| online-khabar | 338 | 119 |
| ratopati | 242 | 11 |
| ekantipur | 242 | **2** |
| rising-nepal | 39 | 7 |
| **kathmandu-post** | **75** | **0** |

eKantipur and the Kathmandu Post — two of Nepal's largest outlets — contribute 2 and 0 events. Worse, the KP rows are **not articles**: `kathmandupost.com/national/province-no-2` titled "Madhesh Province - The Kathmandu Post" is a section landing page. The crawler is ingesting navigation pages. This also explains the 485 phantom "2026" articles (they carry the scrape date).

**Implication for the paper:** any inter-annual trend, and any statement about national landslide frequency, is currently uninterpretable. Either model reporting effort explicitly (articles-per-source-year as exposure) or restrict claims to within-year spatial patterns and explicitly disclaim trend inference.

### 4.5 Terai districts in a landslide inventory
`inventory_audit_summary.json` reports districts present only in the Nepali-language subset: **Banke, Bara, Dhanusha, Rupandehi, Saptari** — all Terai plains, essentially without landslide terrain. Their presence is a direct false-positive indicator (flood articles, or victim's-home-district attribution). A physiographic sanity gate (Terai districts require an explicit hill/slope place mention) is a cheap, defensible, and citable filter.

---

## 5. Validation design — the part I would redesign first

### 5.1 The manual sample cannot measure recall (structural)
`manual_pack.py:118-124`:
```sql
WHERE COALESCE(e.in_nepal, 1) = 1
  AND COALESCE(e.class, 3) IN (1, 2)
```
The evaluation sample is drawn **only from rows the pipeline kept**. Therefore:
- No excluded article is ever reviewed. The false-negative rate of `scope_filter` and `event_specificity` is **structurally unmeasurable**.
- The "macro recall = 0.677" in `manual_metrics_refreshed.json` is recall *within the retained set*, not recall of the inventory. It is not the quantity the paper needs and should not be reported as recall.
- The 172 `by landslide` false negatives (§2.1) could never have been detected by this design.

### 5.2 The labeled set is not held out
`manual_refresh` re-scores the **same 200 rows** against the current model. Between `manual_metrics.json` (2026-04-13, macro F1 **0.342**) and `manual_metrics_refreshed.json` (2026-04-20, macro F1 **0.656**), the rules were revised. The presence of `manual_verification_sample_200.csv`, `manual_verification_batch2.csv`, `manual_verification_sample_pre_batch2_backup.csv`, and `manual_verification_sample_refreshed.csv` shows the label set was also grown and edited during that window.

Whatever the intent, the effect is standard test-set contamination: **0.656 is a training-set number.** Publishing it as a validation result is not defensible.

### 5.3 Annotation is not blind
`manual_pack` writes `class_pred`, `district_pred`, `date_pred`, `deaths_pred` into the same row the annotator fills. `LABELING_GUIDE.md` instructs "label from the article itself, not the predicted fields" — which is exactly the instruction that does not work against anchoring. The strong per-field agreement improvements are partly an anchoring artifact.

### 5.4 Ground-truth labels are unvalidated
`trigger_true` contains a literal `unkown` typo class with **17 rows**, scored as a distinct truth category. `manual_score.py` never validates the label vocabulary. Fix the scorer to hard-fail on out-of-vocabulary truth values.

### Redesign (do this before any further tuning)

1. **Freeze a locked test set now.** Sample **from `raw_articles`, not from `article_events`** — i.e., from every article that passed keyword collection, regardless of pipeline outcome. Stratify by source × language × year × pipeline-decision (kept / dropped-scope / dropped-specificity / dropped-other). n ≈ 400. Hash-lock it; check the hash into git; never re-label it.
2. **Keep a separate dev set** (the current 200 rows are fine for this — they are burned as test data anyway) for all rule iteration.
3. **Blind the pack.** Two files: `*_labels.csv` (url, source, title, snippet + empty truth columns) and `*_predictions.csv` joined only at scoring time.
4. **Double-annotate ≥100 rows and report Cohen's κ.** A rule-based inventory with subjective class boundaries needs an inter-annotator reliability number; without it the 0.516 precision has no error bar.
5. **Reconcile the class rubric to one document** before re-labeling anything.
6. **Report the confusion matrix and per-class CIs**, not just macro F1.

---

## 6. BIPAD validation — the current design is wrong; here is a better one

### 6.1 What is wrong with `bipad/validation.py`

**(a) It treats BIPAD as ground truth, which is scientifically indefensible.**
`build_metrics` computes `precision = matches / canonical_count` and `recall = matches / bipad_count`. This asserts that a news-derived event absent from BIPAD is a *false positive*. BIPAD is an independent, incomplete, differently-defined administrative reporting system with its own coverage discontinuities and its own under-reporting — not a reference standard. Reviewers will reject this framing immediately, and it also undersells your work: a news event BIPAD missed is a *contribution*, not an error.

**(b) `_is_landslide_row` fails open.**
```python
if not disaster_value:
    return True
```
If the hazard column name in the export is not in `DISASTER_COLUMNS`, **every row — floods, fires, epidemics — is treated as a landslide**. Silent, catastrophic, and it will look like a plausible recall number.

**(c) BS-date corruption risk.** `DATE_COLUMNS` includes `'date_bs'`, and `parse_date` has no Bikram Sambat handling. A BS date `2081-03-25` parses cleanly as an AD date — a silent ~57-year offset. It must hard-fail on any 4-digit year in the 2070–2090 range.

**(d) `_first_date` falls back to scanning every column value** for anything date-shaped. It will happily return `created_at` or `updated_on` instead of the incident date, in dict order.

**(e) Ambiguous format order.** `'%d-%m-%Y'` is tried before `'%m-%d-%Y'`; `05-07-2024` resolves silently and possibly wrongly.

**(f) No study-window filter on BIPAD rows**, so the recall denominator includes out-of-period records.

**(g) District + date only, greedy 1:1.** No municipality, no casualty constraint. In a monsoon week a single district has many BIPAD landslide rows; with a ±7-day window a large share of "matches" are chance. And the 1:1 constraint contradicts reality: BIPAD often records per-household/per-ward incidents while news aggregates them — the true relationship is **many-to-many**, and the *unit of analysis differs between the two inventories*.

### 6.2 The design I want instead

Reframe the entire exercise from *"validate against ground truth"* to **cross-inventory agreement between two independent, incomplete observation systems**. This is both correct and a stronger paper.

**Layer 1 — Harmonize units before comparing anything.**
Collapse BIPAD to *incident clusters* (district × date-window × hazard) before matching, so both sides are at the same granularity. Report how much collapsing was needed — it is itself a finding.

**Layer 2 — Matching with a stated, tiered rule.**
- Tier A: same district **and** same municipality **and** |Δdate| ≤ 1
- Tier B: same district and |Δdate| ≤ 3 and |Δdeaths| ≤ 1
- Tier C: same district and |Δdate| ≤ 7
Report each tier separately. Allow many-to-many and report the multiplicity distribution.

**Layer 3 — Chance-corrected agreement (this is the part that makes it publishable).**
Compute a **null distribution** by permuting event dates within district (or shifting all news dates by ±30/60/90 days) and re-running the matcher. Report observed overlap **minus** expected-by-chance overlap. Without this, a ±7-day district-level match rate is nearly meaningless; with it, you have a defensible statistic that almost no news-inventory paper reports.

**Layer 4 — Capture–recapture for total event count.**
Treat news and BIPAD as two independent samplers of the same underlying event population and apply a Lincoln–Petersen / log-linear capture–recapture estimator, with district-level heterogeneity. This converts "BIPAD found 60% of ours" into **an estimate of how many landslide events both systems missed** — a genuinely novel contribution and the strongest possible use of BIPAD.
State the independence assumption explicitly and test it (BIPAD reporting is partly media-triggered, which violates independence; stratify by casualty severity to bound the bias).

**Layer 5 — Agreement at aggregate scale.**
Compare district-year and district-month counts via Spearman ρ and a Bland–Altman plot. Two inventories can disagree wildly on individual events yet agree on spatial-temporal structure — and that agreement is what actually licenses the downstream CHIRPS/rainfall analysis.

**Layer 6 — Directional error analysis.**
Manually review a stratified sample of both `bipad_unmatched_canonical` (are these real events BIPAD missed, or our false positives?) and `bipad_unmatched_reference` (coverage gaps in news, or BIPAD granularity?). This is the table that goes in the paper's discussion.

**Never report "precision" and "recall" against BIPAD.** Use *overlap*, *chance-corrected agreement*, *capture–recapture completeness*, and *rank correlation*.

---

## 7. Keep / Refactor / Redesign

### Keep (this is real, hard-won work)
- Package layout, `config.py` validation pattern, `utils/` (deterministic `stable_hash`, `utc_now_iso`), `Makefile`, shadow-module guard.
- The **gazetteer layer** (`gazetteer.py`, `gazetteer_municipality.py`, `resources/*.csv`) — alias normalization, EN/NP, municipality→district. Solid and reusable.
- The **bilingual routing** (`langdetect/router.py`) and the separate `nlp_en` / `nlp_np` extractors. Correct architecture.
- The **place-candidate model** — `PlaceCandidate(name, admin_level, score, start, …)` with a ranked candidate list. Good bones. The problem is only that `finalize_place_extraction` throws away all but `ordered[0]`.
- `scrape/` idempotent storage, `coverage_report.csv`, `discovered_urls` provenance.
- The test suite as a **regression harness** — keep it, just stop treating it as validation.

### Refactor
- `preprocess/dates.py` → explicit candidate list with `date_method` provenance and a documented precedence table, instead of an if/elif ladder.
- `dedup_stage.py` → keep union-find and determinism; replace the similarity function (§8) and make `cluster_id` content-stable (see below).
- `db.py` → replace `ALTER TABLE` accretion with a versioned migration list; drop the duplicate columns; drop the `UNIQUE(url)` constraint that forbids multi-event articles.
- `manual_pack.py` / `manual_score.py` → blind packs, locked test set, vocabulary validation, κ.
- `config.py` → drop the exactly-8-slugs constraint; make the study window a config value, not a constant; reconcile 2024 vs 2026.
- `bipad/validation.py` → fail-closed hazard filter, BS-date guard, study-window filter (§6).

### Redesign
1. **The classification model** — split `class` into orthogonal fields (§3.2). This is the root fix; most of the rule cascade's complexity exists to paper over the conflation.
2. **District resolution** — replace "highest-scoring mention" with **event-site role classification** (§8).
3. **The filter chain** — reorder to scope → hazard-type → event-vs-nonevent → granularity → location → date, each writing an immutable decision row and **never mutating** `article_events`.
4. **Cross-language dedup** — §8.
5. **The validation protocol** — §5.
6. **BIPAD comparison** — §6.

---

## 8. Two concrete redesigns

### 8.1 District resolution: from "best mention" to "event-site role"

Replace `finalize_place_extraction`'s `ordered[0]` with a **role classifier over all candidates**, keeping the full candidate list in the DB.

Assign each place mention a role from evidence in a ±N-token window:
| Role | Evidence (EN / NP) | Use for district? |
|---|---|---|
| `event_site` | governed by the landslide predicate — "landslide **in** X", "X **मा पहिरो**", "पहिरो खस्यो" | **yes** |
| `dateline` | position 0–40, ALL-CAPS or followed by `, <Month> <D>:` | **never** |
| `destination` | "brought/airlifted **to** X", "**ल्याइयो** X", "उपचारका लागि X" | never |
| `victim_home` | "X **निवासी**", "resident of X", "hailing from X" | never |
| `admin_office` | "District Administration Office X", "जिल्ला प्रशासन कार्यालय" | tie-break only |
| `corridor` | X–Y road/highway names | flag `multi_district` |

Then: `district = argmax(role == event_site)`; if none, leave **NULL** rather than falling back. A null district is honest and measurable; a wrong district is invisible and fatal.

This one change should move Kathmandu and Chitwan off the top of the table and is the single highest-value fix in this document. Because myRepublica datelines are already detected by `MYREPUBLICA_DATELINE_PATTERN` (in `extract_stage.py`), a large part of the plumbing exists — it is used to trim text, but its output is never used to *veto a place candidate*. That is a small, high-leverage change.

**Validate it directly** with a district-level confusion matrix on the locked test set, plus a physiographic sanity check (share of events in Terai districts should be near zero).

### 8.2 Cross-language, language-agnostic dedup

Replace pure string similarity with a **structured-signature blocking + scoring** scheme that does not depend on script:

```
Blocking key : (district, event_date ± candidate_window)
Score        : w1·municipality_match          (gazetteer-normalized → language-neutral)
             + w2·ward_match
             + w3·casualty_vector_agreement   (deaths/missing/injured, language-neutral)
             + w4·trigger_agreement
             + w5·place_name_transliteration_similarity   (NP→Latin via a fixed
                                                           transliteration table,
                                                           then rapidfuzz)
             + w6·within-language body similarity (TF-IDF cosine, NOT token_set_ratio)
Merge if score ≥ τ, with an explicit hard veto on conflicting municipalities.
```

Key points:
- Weights fit on the **dev** set, reported on the **test** set.
- Replace `token_set_ratio` on bodies with **TF-IDF cosine** so that shared monsoon boilerplate is down-weighted by IDF. `token_set_ratio` on 2,000-char news bodies is not a defensible similarity measure in a methods section.
- Make `cluster_id` stable: hash `(district, canonical_date, municipality)` rather than the member URL set, so IDs survive adding a source. Currently every `event_id` changes whenever coverage changes — which breaks any longitudinal audit or published DOI'd dataset version.
- Report the **merge rate by language pair** (en–en, np–np, en–np). If en–np merges stay near zero after the fix, the fix did not work.

---

## 9. Sequenced plan

### Immediate — this week, in this order

1. **`git init` is done; commit.** Commit the tree now, tag it `pre-review-baseline`. Nothing else in this document is verifiable without it. Then commit the DB snapshot pointer + a `DATA_VERSION` file.
2. **Freeze the locked test set** (§5.1), sampled from `raw_articles` including dropped rows. Do this *before* touching any rule, or you burn another evaluation set.
3. **Fix `by landslide`** and audit every entry in `METAPHOR_PATTERNS`, `ROUNDUP_PATTERNS`, `RISK_PATTERNS`, `CONTEXT_ONLY_PATTERNS` for substring-collision. Move them into `config.yaml` (`keywords.exclude` already exists and is unused). Expect ~200 events to return.
4. **Stop the destructive updates.** Add `article_decisions(url, stage, decision, reason, score, decided_at)`; make filters write there and leave `article_events` immutable. This is ~half a day and unblocks all error analysis.
5. **Purge the crawler garbage** — Kathmandu Post section pages, the 2026 phantom rows. Add a parser gate requiring an article-like URL and a dated byline.
6. **Delete or regenerate `canonical_events_final.csv`** from code.

### Short term — 2–4 weeks

7. **Implement event-site role classification** (§8.1). Re-run. Confirm Kathmandu and Chitwan drop out of the top ranks; confirm Terai share → ~0.
8. **Split `class`** into `is_landslide_event` / `event_granularity` / `article_role` / `*_resolved` flags (§3.2). Reconcile the labeling rubric to one document first.
9. **Reorder stages**: scope → hazard-type → event → granularity → location → date → dedup.
10. **Add `date_method` provenance**; report the explicit-date vs. publication-fallback split.
11. **Fix collection for eKantipur and Kathmandu Post**, or formally drop them and revise the "eight sources" claim. Google News RSS `site:` queries do not backfill archives — you need per-site archive pagination for pre-2020 coverage. Then re-derive the year distribution and see how much of the 5× 2024 spike survives.

### Medium term — 1–2 months

12. **Cross-language dedup** (§8.2), with merge-rate-by-language-pair reported.
13. **Blind, double-annotated evaluation** on the locked test set; report κ and per-class CIs. This is the number that goes in the paper.
14. **BIPAD comparison per §6**, including the permutation null and capture–recapture.
15. **Reporting-effort model** — articles-per-source-year as an exposure offset — before any temporal claim.
16. **Write the methods section from the code**, then re-read the code against it. Every disagreement is a bug in one of the two.

### The single best next step
**Freeze a locked, decision-stratified test set drawn from `raw_articles` (including dropped articles), before changing a single rule.** Everything else in this plan is unmeasurable without it, and every further tuning pass without it destroys more of your ability to state a defensible number in the paper.

---

## 10. What is genuinely strong

Stated plainly, because the above is heavy and the foundation deserves credit:

- **The bilingual design is the right call and is properly implemented** — separate EN/NP extractors with a language router and a mixed-language merge path is the correct architecture, not a shortcut.
- **The gazetteer work is excellent** — alias normalization, municipality→district mapping, EN/NP variants, all committed and versioned. This is usually the hardest and most tedious part of a Nepal inventory, and it is done.
- **Determinism was designed in from the start** — stable hashing, sorted iteration, seeded sampling, deterministic union-find. Most research pipelines cannot re-produce their own outputs; yours can.
- **The audit tooling already exists** — `inventory_audit`, `audit_canonical`, `dedup_cluster_audit.csv`, `class1_low_confidence.csv`. You built the instruments needed to find these problems; several of the numbers I used above came from your own outputs.
- **You measured honestly.** `manual_metrics.json` reporting macro F1 = 0.342 was not hidden or discarded. That is the habit that makes the rest of this fixable.

The problems in this review are the problems of a project that got far enough to have real data to be wrong about. The scaffold is sound; the science layer needs the rebuild described above.
