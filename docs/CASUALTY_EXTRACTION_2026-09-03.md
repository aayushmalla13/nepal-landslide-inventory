# Casualty extraction: word-form counts, body recovery, and guarded zeros

**Date:** 2026-09-03 · **Status:** implemented, tested, released as rainfall
v0.4.0. Inventory release still blocked on locked-test v7 labelling.

`MISSING_DATA_RECOVERY.md` §5 scoped casualty backfill in August and then
deliberately declined to build it:

> The gap is large (921 deaths, 444 missing, 616 injured) but the failure mode
> is dangerous … The project's rule against imputing zero makes this a task that
> needs a labelled development set before any pattern is written.

That was the right call, and this is that task done in that order: sample first,
label second, write patterns third, measure fourth.

---

## 1. What the audit actually found

Against the current inventory, of 3,397 class-1 articles only 563 carried a
death count. 933 contained death vocabulary with no count extracted, **703 of
them Nepali**. So the gap was not evenly spread; it was overwhelmingly a Nepali
extraction problem.

Reading those articles showed three distinct causes.

### 1.1 The Nepali patterns matched digits only

Both Nepali casualty patterns required `\d+`. Nepali disaster reporting writes
small tolls as words:

    तीन जनाको मृत्यु भएको छ        three people died
    एक बालकको मृत्यु भएको छ        a boy died
    दुई महिलाको शव भेटिएको छ       the bodies of two women were found

Small tolls are the common case, so a digit-only pattern misses most single-event
reporting and catches mainly the large aggregate figures — precisely the wrong
selection.

### 1.2 A death can be confirmed without any death word

"शव फेला परेको छ" — *a body has been found* — is the standard construction in
recovery reporting. None of its words is a death term, so any toll written this
way was invisible. It accounts for a large share of the Nepali gap.

### 1.3 English counts separated from their verb by an apposition

    Four persons of a single family were buried to death
    Three members of the same family have died
    Two Nepal Police personnel were killed

The patterns required the death term close behind the count, so the intervening
phrase hid all of these.

---

## 2. The finding that was not in the brief

The digit-only patterns were not only missing counts. **They were producing
wrong ones.** With no correct match available, a deliberately loose fallback —
`(?:death-term)[^0-9]{0,8}(\d+)` — took whichever digit sat within eight
characters of a death word. In Nepali headline style that is routinely a
different quantity entirely:

| Headline | Recorded deaths | Correct |
|---|---:|---:|
| नौ जनाको मृत्यु, **४५** बेपत्ता | 45 | 9 |
| चार जनाको मृत्यु, **१०** घाइते | 10 | 4 |
| एक जनाको मृत्यु, **९** सवारी साधन पुरिए | 9 | 1 |
| पाँचजनाको मृत्यु, **६ लाख** भन्दा धेरै घरमा विद्युत बन्द | 6 | 5 |
| दुई जनाको मृत्यु, **६ लाख** सत्तरी हजार सुरक्षित स्थानतर्फ | 6 | 2 |

Missing counts, injured counts, damaged-vehicle counts and an evacuation figure
of six hundred thousand were all being stored as death tolls. Once the word-form
pattern matches the correct, earlier construction, the loose fallback never runs.

All 45 articles whose death count changed were inspected individually. Every one
is a correction. This is worth stating plainly because a change of this shape —
counts moving both up and down — could otherwise look like churn.

---

## 3. Explicit zeros, and the rule that governs them

An article that states in so many words that nobody was harmed now records
**0**, not unknown. "A landslide happened and hurt nobody" is real information
and is different from "we do not know", and conflating them understates the
denominator of any impact analysis.

The project's standing rule — an unknown casualty value is never replaced by
zero — is what makes this dangerous, because the same phrase is routinely scoped
to one district inside a wider tally:

> गण्डकीमा मानवीय क्षति भएको छैन। *(in an article reporting 48 deaths)*

`nlp_counts.explicit_zero_is_safe` therefore requires **all four** of:

1. an explicit no-casualty phrase is present — necessary, never sufficient;
2. no casualty count was extracted anywhere in the article;
3. no death vocabulary appears anywhere in the article;
4. the article is not a roundup, and the claim is not contradicted later in it.

Guard 4 exists because of one specific labelled failure that passed the other
three:

> मन्त्री घिसिङले … बाढीको कारणले मानवीय क्षति भएको छैन। **तर पहिरो गएर इलाममा
> भने क्षति भएको** उनले बताए।
> *(no human loss from the flood — but there WAS loss from the landslide in Ilam)*

`क्षति` means loss or damage generally and is not death vocabulary, so nothing
else caught it. 58 articles now carry an explicit zero.

Livestock deaths are deliberately *not* treated as death vocabulary: "पहिरोमा
कुनै मानवीय क्षति नभएको तर … तीन भैँसी … मरेका" is a genuine human zero.

### Two encoding traps found along the way

**`कुल` sits inside `स्कुल`.** Devanagari has no word boundary that `\b`
understands, so the roundup-marker alternation matched the word for "total"
inside the word for "school", vetoing a legitimate zero in an article about
closed schools. It also matched inside the personal name कुलमान. Every
Devanagari marker is now fenced with explicit look-arounds.

**`नभएकाे` and `नभएको` render identically but are different bytes.** Legacy
Nepali fonts and some CMS exports write one vowel sign as two marks (आ-sign +
े-sign instead of the single ो-sign). Unicode does *not* canonically compose
these — NFC leaves both unchanged — so an ordinary pattern silently fails on the
second form. `fold_devanagari_vowel_signs` rewrites the two-mark spellings.

---

## 4. How it was measured

`scripts/draw_casualty_development_set.py` draws 140 articles seed-
deterministically (seed 20260903) across four strata, balanced by language, after
excluding **all 1,090 URLs** appearing in any locked test set or prior
development set. The strata are the recall gap, the explicit-no-casualty
articles, the not-yet-known articles (present specifically as traps for an
over-eager zero rule), and a control stratum that already had a count.

78 rows were labelled by reading the article text. Blank means unknown; 0 means
the article states nobody was harmed.

`scripts/score_casualty_development.py` reports:

| Metric | Before | After |
|---|---:|---:|
| Exact agreement with the human label | 0.538 | **0.808** |
| Recall on counts a human could read | 0.500 | **0.767** |
| **False zeros** | 0 | **0** |
| Explicit zeros missed | 25 | 2 |

False zeros is the number with a hard target of zero: a wrong zero is invisible
downstream because it looks like a measurement rather than an absence.

**Three of my own labels were wrong, and the implementation caught them.** Two
articles I had marked as zero turn out to report deaths elsewhere in the same
piece, and a third has a headline stating a landslide claimed a life. Each is now
corrected in the label file with a note recording the mistake and why. This is
the argument for labelling before implementing rather than after: the
disagreements are informative in both directions.

These are development diagnostics for rule design, per
`docs/DEVELOPMENT_SET.md`. They are **not** held-out performance and must not be
reported as such.

### What is still missed, honestly

Of 15 remaining disagreements: counts that require summing across categories
("६ महिला, तीन पुरुष र एक/एक बालक तथा बालिकाको मृत्यु" = 11); a toll expressed
as a rising total ("ज्यान गुमाउनेको संख्या ५ पुगेको"); coordinated subjects
("A mother and her two-year-old daughter died"); and two conservative refusals
where "so far" made the extractor decline a zero it could have taken. The last
group errs in the safe direction and was left alone.

---

## 5. Effect

| | before | after |
|---|---:|---:|
| Articles with a death count | 1,410 | **2,246** |
| Articles with a missing count | 874 | **1,243** |
| Articles with an injured count | 544 | **839** |
| Death counts changed | — | 45, all corrections |
| Counts lost | — | **0** |
| Class 2 → 1 on recovered human impact | — | 28 |

Canonical events 2,950 → 2,885. The rainfall analysis is essentially unmoved
(threshold 51.6 mm both sides, temporal-test AUC 0.676 → 0.675), which is the
correct outcome: that analysis reads district, date, trigger and event type, and
never a casualty count. The value here is in the inventory.

## 6. Reproduce

```bash
PYTHONPATH=src python3 scripts/draw_casualty_development_set.py
PYTHONPATH=src python3 scripts/score_casualty_development.py
python3 -m pytest tests/test_nlp_counts.py tests/test_nlp_np_extract.py tests/test_nlp_en_extract.py
```
