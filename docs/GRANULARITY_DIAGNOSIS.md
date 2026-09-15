# Event granularity: diagnosis, two ruled-out fixes, and what is actually needed

**Date:** 2026-09-04. No classifier change was made. This document records what
was measured, what was tried and rejected on evidence, and why the next step is
120 human labels rather than a patch.

---

## Why this matters

Locked test v7 put article-level precision at 0.626. **78% of its false
positives are articles the human annotator marked `multi` or `roundup`** —
genuine Nepali landslide reports covering more than one failure — against only
8% that describe no landslide at all. The classifier is not confused about
whether a landslide happened. It is confused about how many. Granularity
agreement on v7 was 0.486.

Granularity is therefore the single biggest lever on precision. It is also, on
inspection, the least tractable with the data currently in the project.

## Baseline on the development set

`scripts/score_granularity_development.py`, 298 scorable rows:

**Accuracy 0.550.**

| truth ↓ / predicted → | multi | not_applicable | roundup | single |
|---|---:|---:|---:|---:|
| multi | 19 | 0 | 12 | **32** |
| not_applicable | 3 | **0** | 11 | **61** |
| roundup | 1 | 0 | 34 | 7 |
| single | 5 | 0 | 2 | 111 |

| class | support | predicted | precision | recall |
|---|---:|---:|---:|---:|
| single | 118 | 211 | 0.526 | 0.941 |
| multi | 63 | 28 | 0.679 | **0.302** |
| roundup | 42 | 59 | 0.576 | 0.810 |
| not_applicable | 75 | **0** | — | **0.0** |

Two defects are visible immediately.

## Defect 1: three rubric categories are structurally unreachable

`classify_event_granularity` can return only `single`, `multi` or `roundup`.
There is no `GRANULARITY_NOT_APPLICABLE` constant, so 75 of 298 development rows
(25%) are guaranteed wrong before any text is read. The same gap exists in the
sibling classifiers: the pipeline defines 4 of the rubric's 6 article roles (no
`metaphor_or_nonevent`) and 6 of its 8 hazard types (no `not_a_hazard`).

The pipeline has no way to say *"this article reports no event"*. Everything
defaults to an event having happened.

**Why it was not patched now.** The obvious rule — `article_role ==
forecast_or_risk` implies `not_applicable` — was measured before implementing.
It fixes 13 of the 75 rows and wrongly flips 4 real-event rows: net +9 of 298,
about +3 points. It also cannot improve precision at all, because
`EventTyping.is_headline` already excludes `forecast_or_risk` articles by a
separate condition. The remaining 62 rows are non-events that
`classify_article_role` calls `first_report`, so the real gap is a missing
non-event detector, not a missing mapping.

A change that adds 4 known errors, moves no published number, and addresses a
sixth of the defect is not worth shipping unvalidated. It is recorded here as a
defect with a known shape.

## Defect 2: `multi` recall is 0.302 — and the obvious cause is not the cause

`classify_event_granularity` reads only the title and the first 250 characters
of the body. The natural hypothesis is that the horizon is too narrow. It was
tested rather than assumed.

Of the 32 `multi`-truth articles the classifier calls `single`:

| where the multi-event pattern matches | count |
|---|---:|
| already in title + 250-char lead | 3 |
| only deeper in the body | 9 |
| **nowhere in the article** | **20** |

And the cost of widening the window: **15 of 118 `single`-truth articles have a
multi pattern somewhere in their full body** and would be flipped to `multi`.

So a whole-body window would gain at most 9 and lose 15. **Widening the horizon
makes the classifier worse.** The 250-character lead is a correct design choice,
and the code comment already says why: later paragraphs routinely list other
affected places as context without turning the reported incident into several.

That leaves 20 articles whose plurality the patterns do not express at all — the
real residual, and the only part worth working on.

## Why the development set cannot be used to fix it

This is the finding that decides the next step.

`development_set_v1`'s granularity labels were produced by a language model
(`annotator = gpt-5.6-sol`; see `docs/LOCKED_TEST_V7.md`). For this field
specifically they are not a usable target:

- On the **51 articles matching the pipeline's documented road-obstruction
  rule** — a deliberate decision with its reasoning written in the code, that a
  road blockage is one event even when the body lists other unstable spots — the
  model annotator split **28 `single` / 22 `multi`**. That is close to a coin
  flip on a rule the project decided on purpose.
- **31 of its 63 `multi` articles have a singular landslide subject in the
  title**: "Landslide obstructs Karnali Highway", "Landslide blocks Madan
  Bhandari Highway", "पहिरोले कालीगण्डकी सडक अवरुद्ध".
- Several of the 20 residual articles are foreign events (Indonesia, Darjeeling,
  Kerala, Pakistan) that are negatives anyway because `in_nepal = no`, so they
  cannot affect headline precision whatever their granularity.

Tuning patterns against these labels would not improve the classifier. It would
encode one annotator's noise and would probably reverse a documented design
decision — and the reversal would then be measured as an improvement.

## What is actually needed, and what has been prepared

**120 human granularity labels**, drawn and ready:

- `data/outputs/granularity_development_LABEL_HERE.csv` — 120 rows, 5 fields
- `data/outputs/granularity_development_reading_pack.csv` — full article text
- `data/outputs/granularity_development_manifest.json`

Design choices worth stating:

- **Stratified by language × predicted granularity**, 20 each across six cells,
  so the cases where the classifier is confident and wrong get equal support
  rather than appearing in proportion to their rarity.
- **Drawn from classes 1, 2 and 3.** Class 1 alone would have been useless: the
  class-1 gate requires headline eligibility, which requires `single`, so all
  3,397 class-1 articles are predicted `single` by construction. The `multi` and
  `roundup` articles live in classes 2 and 3. The first draw of this pack made
  exactly that mistake and produced two strata instead of six.
- **695 previously labelled URLs excluded** (locked v6, locked v7, development
  v1), verified by assertion, not assumed.
- **The pipeline's prediction is not shown to the annotator.** It is written to
  `granularity_development_predictions.csv` for scoring afterwards. Showing it
  would invite ratification on precisely the rows the set exists to adjudicate.

## The sequence from here

1. Label the 120 rows (`event_granularity_true`, plus
   `is_landslide_event_true` and `in_nepal_true`, which are what make a
   granularity judgement well defined).
2. Re-score with `scripts/score_granularity_development.py --labels ...` to get
   an honest baseline against human judgement — including whether the
   road-obstruction rule survives human review.
3. Design the fix against those labels: better `multi` expression coverage, and
   a genuine non-event detector for `not_applicable`.
4. Draw **locked test v8** and have it labelled, then score once. v7 is spent
   and may not be reused.

Only after step 4 can a new precision figure be reported.


---

# Part 2: the human labels, 2026-09-05

GS labelled all 120 rows. Structure clean: row IDs and order intact, no frozen
column touched, all three judgement fields filled on every row, **zero
out-of-vocabulary values, zero internal contradictions** (no row has
`is_landslide_event = no` with a granularity other than `not_applicable`, and
none the reverse). All four convention questions were answered explicitly in
`notes`.

## The headline result: the model-labelled set was actively misleading

| | model-labelled (dev v1) | **human-labelled** |
|---|---:|---:|
| accuracy | 0.550 | **0.619** |
| `multi` recall | 0.302 | **0.784** |
| `multi` precision | 0.679 | 0.725 |
| `roundup` recall | 0.810 | 0.833 |
| `roundup` precision | 0.576 | 0.500 |
| `single` precision | 0.526 | 0.632 |
| `not_applicable` recall | 0.0 | 0.0 |

Confusion against human truth (118 scorable rows; 2 `unclear` excluded):

| truth ↓ / predicted → | multi | not_applicable | roundup | single |
|---|---:|---:|---:|---:|
| multi (37) | **29** | 0 | 7 | 1 |
| not_applicable (26) | 6 | **0** | 10 | 10 |
| roundup (24) | 1 | 0 | **20** | 3 |
| single (31) | 4 | 0 | 3 | **24** |

**`multi` recall is 0.784 against a human, not 0.302.** The model annotator made
the classifier's biggest apparent weakness look 2.6x worse than it is. Every
pattern change that Part 1's numbers would have motivated would have been fitted
to that noise. Declining to tune on `development_set_v1` was the right call, and
this is the evidence.

## All three candidate fixes are now dead, each on measurement

**1. Widening the 250-character lead — rejected in Part 1.** Gains 9 `multi`,
wrongly flips 15 `single`. Net negative.

**2. Making `not_applicable` reachable — real defect, but cosmetic.** All 26
`not_applicable` articles in the human pack are pipeline **class 2 or 3**;
**none is class 1**. The pipeline already excludes every one of them through the
scope and specificity filters, by a different mechanism. Implementing
`not_applicable` would raise this granularity metric by up to 22 points and
change **no published number, no inventory row, and no precision figure**. It is
a vocabulary-completeness defect, not an accuracy one, and it is recorded as
such.

**3. The documented road-obstruction rule is not too coarse — it is correct.**
GS's Convention A counts physical slope failures rather than blockages, which
looked like a direct contradiction of the rule that a road-obstruction title is
`single`. It is not, because the rule is a *fallback*: the multi-event patterns
in the heading are tested first. On the 22 road-title articles in the pack:

| | predicted multi | predicted roundup | predicted single |
|---|---:|---:|---:|
| truth multi (13) | **12** | 1 | 0 |
| truth single (9) | 0 | 1 | **8** |

Twenty of 22 correct, and **not one case** of a `multi` road article being
called `single`. The rule fires only where the article really is one blockage.

## What the pack could not answer, and why

This is a limitation of my own sampling, and it matters.

v7's precision loss lives in a specific cell: **class-1 articles the pipeline
kept, that are truly `multi`**. Stratifying by *predicted* granularity cannot
reach that cell well, because class 1 is 100% predicted `single` by
construction. The pack contains only **17 class-1 rows** (16 truly `single`, 1
truly `multi`) — far too few to characterise the failure that costs precision.

| truth | class 1 | class 2 | class 3 |
|---|---:|---:|---:|
| single | 16 | 12 | 3 |
| multi | 1 | 34 | 2 |
| roundup | 0 | 9 | 15 |
| not_applicable | 0 | 6 | 20 |

So the pack answered "is the granularity classifier broken?" — much less than
feared — but not "why do multi articles survive into the kept inventory?".

## Recommendation

A **class-1-only** granularity pack, roughly 100 rows, sampled from the 3,397
kept articles and labelled for granularity alone. That is the population where
the false positives live, and it is the only sample that can drive a fix worth
making.

Whether it is worth GS's time is a judgement call worth stating plainly: **the
rainfall analysis does not depend on granularity at all.** It works at
district-day resolution and collapses multiple records within a district-day to
one case-day, so an article read as one event rather than three still yields the
correct district-day. This is inventory-quality work, not paper-blocking work.
The v7 precision of 0.626 is already reported honestly, with its cause
identified.

---

# Part 3: the class-1 pack, 2026-09-05 — the measurement that changes the picture

GS labelled all 100 rows. Clean: row ids and order intact, no frozen column
touched, all three judgement fields filled, zero out-of-vocabulary values, zero
internal contradictions. The composition confirms the design was right —
`not_applicable` appears 4 times and foreign events 0, because every article
here already passed the scope filters.

## The headline number

Weighted to the 3,110 class-1 articles the sample represents:

| true granularity | estimated share of the **kept inventory** |
|---|---:|
| single | **58.5%** |
| multi | **29.3%** |
| roundup | 7.6% |
| not_applicable | 4.6% |

**41.5% of the kept inventory is not a single event**, while the class-1 gate
labels every one of them `single` by construction. This is the direct
explanation of locked v7's 0.626 precision, arrived at independently: 1 − 0.415
= 0.585 against the 0.626 measured on v7.

## The enrichment worked, and it reversed an earlier negative result

Per-stratum, unweighted:

| stratum | n | current accuracy | true `multi` rate |
|---|---:|---:|---:|
| en:plain | 25 | 0.680 | 0.280 |
| en:signal | 25 | 0.200 | **0.760** |
| np:plain | 24 | 0.667 | 0.167 |
| np:signal | 25 | 0.200 | **0.680** |

An article whose body carries a multi-event phrase is roughly **three times**
more likely to be truly `multi`. That signal is exactly the one Part 1 rejected.

**Part 1's rejection was an artefact of the model-labelled set.** Measured there,
the signal gained 9 and wrongly flipped 15 — a net loss. Measured on human
labels, over the population that actually matters:

| | |
|---|---:|
| current weighted accuracy | 0.585 |
| candidate (`body signal → multi`) | **0.675** |
| change | **+0.090** |
| stratified bootstrap 95% CI | **[+0.037, +0.137]** |
| iterations improving | 99.9% |
| articles correctly reclassified | 394 |
| articles wrongly reclassified | 174 (2.27 : 1) |
| of those, genuinely `single` (a real loss) | 114 |

Both measurements are kept in the test suite:
`test_the_body_signal_looks_harmful_on_the_MODEL_labelled_set` now records the
artefact explicitly, and `test_the_body_signal_helps_on_the_HUMAN_labelled_set`
pins the reversal. Neither can be silently lost.

## Why this is NOT being implemented yet

The fix is well evidenced and it is also a **major inventory revision**, so it
needs a deliberate decision rather than a commit:

1. **It shrinks the inventory by roughly 29%.** A `multi` article fails the
   headline test and leaves the kept set. Every downstream number moves: the
   canonical event count, the 1,508 case-days, the matched controls, and
   therefore the cutpoint, the AUC and every figure in the manuscript.
2. **It is a development measurement.** The class-1 pack exists to design
   against. Confirming the gain requires a newly drawn, human-labelled **locked
   set v8**, scored once. v7 is spent.
3. **It raises a design question the rubric does not settle.** A `multi` article
   reports several *real* landslides. Excluding it improves precision by
   definition, but discards genuine events rather than extracting them. Whether
   the right answer is to drop such articles or to extract multiple events from
   them is a scientific choice, not a bug fix — and 29% of the inventory is too
   much to decide by implementation.

## Recommended sequence

1. Decide the design question in (3): drop `multi` articles, or extract from them.
2. Implement the chosen rule against this class-1 pack (it is a development set;
   inspecting it while designing is legitimate).
3. Draw **locked set v8**, label it, score once, and cut a new inventory release
   with the changed counts recorded against the frozen baseline.
4. Re-run the rainfall analysis on the revised inventory and report the movement
   alongside v0.6.0, as the inventory-sensitivity limitation already anticipates.

---

# Part 4: the decision, 2026-09-05

**Decided: the inventory keeps its multi-event articles. No reclassification.**

## The measurement that decided it

The candidate fix is well evidenced as a *granularity* improvement (+0.090,
95% CI [+0.037, +0.137]). It was rejected anyway, because granularity is not the
quantity this paper depends on.

The analysis unit is the **district-day**, not the article. So the question is
not "does this article describe exactly one failure?" but "did a landslide occur
in this district on this day?". Measured directly on the class-1 pack:

| | |
|---|---:|
| retained articles reporting a real landslide in Nepal | **95.5%** |
| stratified bootstrap 95% CI | **[90.0%, 99.4%]** |
| of the 47 `multi` articles, real Nepali landslides | **47 of 47** |
| article-level headline precision, locked v7 | 0.626 |

Every multi-event article in the sample is a genuine Nepali landslide. An
article reporting three failures in a district on one day yields **the same,
correct district-day** as one reporting a single failure. Reclassifying it to
`multi` would remove a **true** case-day from the analysis, not a false one.

The 0.626 and the 0.955 are both correct. They differ almost entirely because
the headline definition adds a requirement — exactly one failure — that the
rainfall design does not need. Acting on the first would have destroyed data the
second shows is sound.

## What was done instead

1. **Nothing was reclassified.** The inventory, the 1,508 case-days, the
   cutpoint and every published figure are unchanged. No new release is needed.
2. **The manuscript now reports both measures** — the strict article-level
   figure for comparability with classification studies, and event validity as
   the quantity relevant to this design — with the reason for the gap stated.
3. **The real defect is recorded as what it is: under-counting.** An estimated
   29% of retained articles report several distinct failures and contribute one
   district-day each, even when the failures span more than one district. That
   is a completeness limitation, and it acts in the same conservative direction
   as control contamination: missing case-days sit among the controls and depress
   measured discrimination. It is now a limitation in the manuscript.
4. **A test pins the reasoning** (`test_retained_articles_are_overwhelmingly_real_events`)
   so it cannot be quietly reversed by someone optimising the article-level
   metric.

## What would change this decision

Extracting **several district-days from one article** — the option that adds
data rather than discarding it. That would convert the 29% under-count into
recovered case-days and strictly improve the inventory. It is a real project:
per-failure location and date extraction, a revised dedup rule, a new inventory
release, and a locked v8 to evaluate it. Worth doing, and out of scope for the
current paper, which is now internally consistent and honestly caveated.

**Locked v8 is not required for this decision**, because nothing changed. It
becomes necessary the moment the extraction rules do.
