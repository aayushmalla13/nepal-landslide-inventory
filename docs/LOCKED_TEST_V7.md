# Locked test v7 — result, and what it changes

**Scored once, 2026-09-04.** Labels frozen at
`data/outputs/locked_test_set_v7_labels_final.csv`; report at
`data/outputs/locked_test_set_v7_score.json`. v7 is now spent and must not be
used for tuning.

---

## Headline result

395 rows, all decidable, annotator **GS**. Population-weighted, strata-bootstrap
95% CIs.

| | v6 (2026-08-10) | **v7 (2026-09-04)** |
|---|---:|---:|
| Precision | 0.742 (0.675–0.807) | **0.626 (0.552–0.701)** |
| Recall | 0.822 (0.744–0.910) | **0.759 (0.682–0.843)** |
| F1 | 0.780 (0.723–0.834) | **0.686 (0.624–0.750)** |
| District exact / coverage | 0.822 / 0.927 (n=123) | **0.828 / 0.922 (n=127)** |
| Event-date exact / coverage | — | **0.824 / 0.976 (n=83)** |

District extraction held up — 0.828 against 0.822, and consistent with the 0.862
measured on the development set. **Article-level precision fell by 0.116.**

Both sets were scored under the same definition. That was checked rather than
assumed: the committed `score_locked.py` in git HEAD carries an older, looser
`_truth_headline` that counts `multi` as positive, and re-scoring v6 with it
gives 0.928/0.666 — not the published figures. Re-scoring v6 with the current
strict definition reproduces 0.742/0.822 exactly. So the published v6 numbers
came from the strict definition and the comparison above is like-for-like.

## Why precision fell: one cause, and it is not detection

Of 64 weighted-sample false positives, **50 are articles the annotator marked
`multi`** — a real Nepali landslide article reporting several distinct failures
— and 6 more are `roundup`. Only 5 are "not a landslide event at all" and 3 are
foreign. The `headline` definition in `docs/ANNOTATION_RUBRIC.md` admits only
`event_granularity = single`, so every multi-event article is a negative.

The pipeline is not confused about whether these articles describe landslides.
It is confused about *how many*:

| | predicted `single` | other |
|---|---:|---:|
| truth `single` (166) | 155 | 11 |
| truth `multi` (83) | 67 | 16 |
| truth `roundup` (45) | 15 | 30 |
| truth `not_applicable` (101) | 79 | 22 |

Overall granularity agreement is **0.486**. The pipeline predicts `single` for
316 of 395 articles (80%) where the truth is 166 (42%). `headline_pred` is
internally consistent with the pipeline's own `event_granularity_pred` in all
395 rows — there is no wiring bug. The granularity classifier itself
over-predicts `single`, and that single weakness accounts for roughly 70% of the
precision loss.

This is the highest-value target in the extraction pipeline, and it is a
tractable one: a `multi`/`roundup` article usually announces itself (plural
subjects, several districts named, a casualty total attached to a region rather
than a site).

## The finding that matters more: who labelled the earlier sets

`annotator` across every labelled set in the project:

| Set | n | Annotator |
|---|---:|---|
| development_set_v1 | 300 | `gpt-5.6-sol` |
| locked_test_set_v6 | 388 | `gpt-5.6-sol` |
| **locked_test_set_v7** | **395** | **GS** |

**v7 is the project's first human-annotated evaluation set.** Every accuracy
figure the project has published before today — including the 0.742/0.822 in
`docs/FINAL_RELEASE.md` and the manuscript — rests on labels produced by a
language model, not by a person.

Two consequences follow, and neither is optional.

1. **The manuscript contains a false statement of provenance.** It reads
   "District accuracy on 123 human-labelled articles rose from 0.813 to 0.862".
   Those 123 labels are rows of `development_set_v1_labels_final.csv`, whose
   `annotator` is `gpt-5.6-sol`. The sentence must be corrected, not softened.

2. **The v6 → v7 comparison is confounded by the annotator.** The two sets differ
   in classifier version, in sample, *and* in who produced the truth. The
   annotators also plainly differ in convention: among landslide-family events
   in Nepal, the model labelled 11% `roundup` against the human's 2%, and 25%
   `multi` against 30%. So the 0.116 precision drop cannot be attributed to the
   classifier changes of 2026-09-03. It is a change of measuring instrument as
   much as a change of measurement.

The right reading is not that the pipeline got worse. It is that **0.626 is the
project's first trustworthy precision estimate**, and it is lower than the
model-labelled estimate that preceded it. That direction is unsurprising: an LLM
annotator and an LLM-adjacent extraction pipeline share failure modes, and
agreement between them overstates accuracy against human judgement.

## What must change

- Report v7 as the paper's evaluation, with the annotator named.
- State the annotation provenance of every set explicitly, including that the
  development set used for tuning was model-labelled.
- Retire the 0.742/0.822 figures from `docs/FINAL_RELEASE.md`,
  `docs/DO_THIS_NEXT.md` and `docs/MANUSCRIPT_DRAFT_V04.md`, or mark them as
  superseded and model-labelled.
- Treat the granularity classifier as the next extraction target. Any change to
  it needs a **v8** locked set: v7 is spent.

## Data quality of the v7 labels

Checked before scoring, and clean:

- 395/395 rows, row IDs and order intact, no duplicates, no edits to any frozen
  column (`url`, `source`, `year`, `route_lang`, `title`, `snippet`).
- All five controlled fields filled on every row; no out-of-vocabulary values.
- Dates all well-formed; deaths all non-negative integers.
- Apparent contradictions all resolved as correct on inspection: the 12 rows
  with `is_landslide_event=no` but a landslide hazard type are all
  `forecast_or_risk` + `not_applicable` (an article about landslide *risk*), and
  the 46 `other_hazard` positives are combined flood-and-landslide monsoon
  events.
- Three district spellings were outside the canonical vocabulary and were fixed
  in the normaliser rather than in the labels: `Nawalparasi (Bardaghat-Susta
  East)` → Nawalpur and `Tanahun` → Tanahu, both added to `DISTRICT_ALIASES`
  with tests.
- One row (`v7-0179`) gives the district as `Rukum`, which has been two districts
  since 2017. The 2015 article names no municipality, so it is genuinely
  unresolvable; the label is left exactly as written.
