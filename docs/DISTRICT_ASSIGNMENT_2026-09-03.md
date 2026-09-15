# District assignment: three corrected rules, measured on labelled data

**Date:** 2026-09-03 · **Status:** implemented, tested, released as rainfall
v0.3.0. A new inventory release is **blocked** pending locked-test v7 labelling.

District is the analysis unit for the entire rainfall study. Every case-day and
every matched control is a (district, date) pair, so an article assigned to the
wrong district does not merely lose detail — it moves a case into a different
rainfall series. This note records why the district rules were changed, what the
change is worth, and what it cost.

---

## 1. How the problem surfaced

The municipality gazetteer was rebuilt from 142 to 753 local units
(`MISSING_DATA_RECOVERY.md`). Before that expansion could enter a release, the
open question was whether more matching municipality names would change which
district an article is assigned to. `scripts/measure_district_drift.py` was
written to answer it, and on the first 400 class-1 articles it found five
changes — all five wrong:

> "Pilgrim dies in Rasuwa landslide" was reassigned **Rasuwa → Rautahat**.

Reading the article explains it: *"The deceased has been identified as Namrata
Karki of **Chandrpur Municipality-1, Rautahat**."* Chandrapur is where the victim
lived. The landslide was at Mini-Gosainkunda in Rasuwa. With the 142-unit
gazetteer, Chandrapur simply did not resolve, so the error could not happen; at
753 units it did.

This class of error is unusually dangerous because the resulting record is
**internally consistent** — the municipality really is in that district — so no
consistency check in the pipeline can detect it.

## 2. A wrong baseline, caught

The drift script originally compared against the `district` and `class` columns
of `corpus_for_extraction.csv.gz`. Those columns are a pre-extraction snapshot,
not pipeline output: they disagree with the released `article_events.csv` on
about 2,990 class assignments all by themselves. The script now compares against
`data/outputs/article_events.csv`, the released extract-stage output, and the
docstring records the trap. Every number below uses the corrected baseline.

## 3. The three rules that changed

### 3.1 A body "<X> district" phrase outranks the filing dateline

`nlp_en.extract._find_explicit_district` returned the dateline first and only
consulted an explicit "<X> District" phrase if no dateline existed. A dateline
names the bureau that filed the story:

> **SURKHET**, Aug 30: A landslide swept away five houses and killed one person
> **in Kalikot district** on Sunday morning.

> **DHANKUTA**, July 12: ... in Silongchong Rural Municipality **in
> Sankhuwasabha district** ...

> **KAILALI**, July 28: A couple died ... **in Darchula district** ...

All three were stored under the bureau's district. The body phrase is the
stronger evidence — the writer attached the word "district" to a name while
describing the event — so it now wins. The qualifier is also matched
case-insensitively: house style is "in Kalikot district" with a lower-case *d*,
and the old pattern required a capital, which is why the phrase almost never
fired in practice.

The function already distrusted the dateline enough to veto a Kathmandu one
outright; this extends the same reasoning to the general case.

### 3.2 A place inside a home-address attribution is not a place candidate

New module `src/landslide_inventory/nlp_attribution.py`. It recognises a small,
fixed set of attested attribution phrases — English *identified as*, *a resident
of*, *hails from*; Nepali *घर भएका*, *निवासी*, *बासिन्दा*, *स्थायी ठेगाना* — and
reports whether a character span sits inside one, without crossing a sentence
boundary (`.` or `।`).

Both language place extractors and both explicit-municipality finders now skip
attributed spans. The Nepali case that motivated it:

> **गोरखाको** सिरानचोक गाउँपालिका–१ केराबारीमा ... पहिरो ... **सिन्धुपाल्चोक
> जिल्लाको** मेलम्ची **घर भएका** चालक रमेश तामाङ ...

The landslide is in Gorkha; Sindhupalchok is where the excavator driver lived.
The released pipeline stored Gorkha correctly only by accident, and the
gazetteer expansion broke that accident.

The design is deliberately conservative. A missed cue leaves behaviour exactly
as before; a false cue can only cause a place to be *ignored*, never invented.
Terms such as bare "resident" are excluded because "residents were evacuated"
describes people at the event site.

### 3.3 An established district is no longer overridden by a contradicting municipality

`unify.extract_stage._reconcile_district` let a municipality's district win
unconditionally. It is replaced by `_reconcile_place`, which returns district,
municipality and ward together and applies two rules:

* **No usable district** → the municipality supplies one. Pure gain; this is
  what the enlarged gazetteer is for. A name shared across districts (fifteen
  exist) cannot pick one for itself and supplies nothing.
* **A canonical district is already extracted** → keep it, and drop the
  contradicting municipality and ward. The language extractors have already
  adjudicated this conflict against the text, including the genuine
  dateline-is-not-the-event case, which
  `nlp_en.extract._district_is_near_municipality` accepts when the district is
  written next to the municipality ("Uttargaya rural municipality – 4, **Rasuwa**"
  under a NUWAKOT dateline). Reaching the stage means that adjudication
  declined.

Dropping the municipality rather than moving the event is the conservative
direction: it never relocates a case, and it never asserts a finer location the
evidence does not support.

## 4. What it is worth

### 4.1 Measured on labelled data, not on drift

`scripts/score_district_development.py` scores district assignment against the
123 rows of `development_set_v1_labels_final.csv` that carry a human
`district_true`. Per `docs/DEVELOPMENT_SET.md` this set exists precisely so
rules may be designed against it. **These are development diagnostics, not
held-out performance, and must not be reported as such.** The locked test sets
were not touched.

| Configuration | Correct | Wrong district | No district | Accuracy |
|---|---:|---:|---:|---:|
| Released v0.4.0 pipeline (142-unit gazetteer) | 100 | 11 | 12 | 0.813 |
| 753-unit gazetteer + all three rules | **106** | **10** | **7** | **0.862** |

**No labelled row got worse.** The gain is five articles that previously had no
district at all and one that had the wrong one.

The script also runs the full 2×2 ablation of §3.1 against §3.3, so the
contribution of each is reproducible without editing code
(`BODY_DISTRICT_OUTRANKS_DATELINE`, `MUNICIPALITY_OVERRIDES_DISTRICT`). On this
sample the two rules are individually neutral — the gazetteer and the
attribution guard carry the measured gain — but each removes a hand-verified
error class that the 123-row sample happens not to contain, and adopting both
is neutral-to-best in every cell of the ablation.

### 4.2 Drift on the full corpus

Against the released `article_events.csv`, over all 10,203 articles:

| | count | share |
|---|---:|---:|
| District unchanged | 9,958 | 97.6% |
| District newly assigned (gained) | 67 | 0.7% |
| District changed | 161 | 1.6% |
| District lost | 17 | 0.2% |
| Municipality newly assigned | 1,612 | 15.8% |

Restricted to the 6,344 class-1 articles — the ones that become canonical events
and therefore rainfall cases — 6,241 are unchanged, 92 changed and 11 lost:
1.6% affected. Class transitions are 38 (2→1) and 15 (1→2).

## 5. What it cost: the inventory and the rainfall result both moved

Canonical events fell from **3,114 to 2,950**. The reduction is deduplication
working better, not events disappearing: 1,612 more articles now carry a
municipality, and the dedup key is (district, date, municipality), so clusters
that were previously split now merge. Distinct district-days went 2,360 → 2,320
(114 lost, 74 gained).

That propagates to the threshold analysis. Released as
`nepal_landslide_rainfall_v0.3.0_20260903`, bundle lock
`2658b66a0ff3…`; v0.2.0 is preserved unchanged on disk.

| Quantity | v0.2.0 (frozen) | v0.3.0 |
|---|---|---|
| Canonical events read | 3,114 | 2,950 |
| Primary case-days / controls | 1,514 / 6,196 | 1,471 / 6,049 |
| Development-selected window | 5 days | 5 days |
| **Primary threshold** | **45.4 mm** | **51.6 mm** |
| Threshold 95% CI (development) | 26.8–72.1 mm | 27.1–71.7 mm |
| Temporal-test AUC | 0.693 (0.657–0.722) | 0.676 (0.638–0.706) |
| Sensitivity | 0.509 | 0.447 |
| Specificity | 0.764 | 0.785 |
| Matched-sample precision | 0.359 | 0.350 |
| Conditional OR per 10 mm (R5, all years) | 1.227 (1.193–1.261) | 1.215 (1.185–1.246) |
| Within-stratum concordance | 0.671 | 0.662 |
| Dev→test AUC gap | +0.051 | +0.035 |
| Co-primary R3 antecedent | 19.1 mm, AUC 0.664 | 20.0 mm, AUC 0.652 |
| Unmatched cases | 192 (12.7%) | 185 (12.6%) |
| Duplicate control rows | 20.1% | 18.7% |

### How to read this honestly

**The association is unchanged.** The conditional odds ratio — the estimator the
matched design implies — moves from 1.227 to 1.215 per 10 mm, well inside either
confidence interval. Within-stratum concordance moves 0.671 → 0.662. Nothing
about the rainfall–landslide relationship is different.

**The cutpoint is less stable than v0.2.0 made it look.** 45.4 mm and 51.6 mm
each sit comfortably inside the other's bootstrap interval (26.8–72.1 and
27.1–71.7), so the two are not statistically distinguishable. But v0.2.0
reported that leave-one-year-out selected a threshold between 45.38 and 45.42 mm
in *all twelve* folds — striking apparent stability. Under v0.3.0 the same
procedure spans 37.5–51.6 mm. The earlier tightness was partly a property of
that particular inventory, not of the rainfall–landslide relationship.

This strengthens rather than weakens the manuscript's existing position that no
single number should be read as an operational threshold. It is now
demonstrable: a defensible revision of the event inventory, which improved
district accuracy on labelled data and regressed nothing, moved the point
estimate by 14%. That belongs in the limitations section as evidence, not as an
apology.

**The dev→test gap narrowed** (+0.051 → +0.035), consistent with the earlier
finding (`RAINFALL_ANALYSIS.md`) that the gap reflects case-mix rather than
publisher turnover.

## 6. What is blocked, and on what

`docs/FINAL_RELEASE.md` states the rule: *"Any classifier change after this
release requires a new locked test version."* These are classifier changes.
Therefore:

* **Inventory v0.4.0 remains the current inventory release.** The rebuilt
  inventory (2,950 events) is on disk as working output but is **not** released,
  because releasing it would publish extraction-accuracy claims that only locked
  v6 supports, and v6 measured the previous classifier.
* **Locked test set v7 has been drawn** — 395 rows, seed 20260903, zero overlap
  with any prior evaluation set (`locked_test_set_v7_LABEL_HERE.csv`). It is
  unlabelled. Labelling it is the single action that unblocks a new inventory
  release and restores a reportable extraction accuracy.
* Rainfall v0.3.0 *is* released, because it is a downstream analysis whose
  manifest hashes its canonical input; its own validity does not rest on the
  locked test set. The manuscript must not, however, quote v6 extraction metrics
  alongside v0.3.0 results without saying that they describe different
  extractors.

## 7. Reproduce

```bash
PYTHONPATH=src python3 scripts/score_district_development.py   # ablation on labelled data
PYTHONPATH=src python3 scripts/measure_district_drift.py       # drift vs released baseline
python3 -m pytest tests/test_nlp_attribution.py tests/test_nlp_en_extract.py \
                  tests/test_nlp_np_extract.py tests/test_extract_stage.py
```

Full pipeline rebuild, after snapshotting the database:

```bash
for s in extract event_specificity location_consistency filter_scope \
         corrections dedup event_typing export_final; do
  PYTHONPATH=src python3 -m landslide_inventory.run --stage $s --config config.yaml
done
PYTHONPATH=src python3 -m landslide_inventory.run --stage analysis        --config config.yaml
PYTHONPATH=src python3 -m landslide_inventory.run --stage rainfall_figures --config config.yaml
PYTHONPATH=src python3 -m landslide_inventory.run --stage rainfall_release --config config.yaml
PYTHONPATH=src python3 scripts/verify_releases.py
```
