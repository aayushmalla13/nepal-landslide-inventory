# Case-set integrity audit

## Why this exists

The project has a lot of quality machinery — scope filters, specificity filters,
an LLM adjudicator, locked test sets, a place-backfill gate. All of it measures
the same thing: **whether an article is a real Nepali landslide report**.

None of it asks whether the *record* that article produced is internally
coherent. Some of those questions have answers that are impossible rather than
merely unlikely, and cost three lines of code to check. This audit runs them
over the 1,508 district-days the rainfall analysis actually uses.

It was prompted by a side-finding: while measuring something else, an article
about an army chief's appointment turned out to be a landslide case-day.

## What it found

| Check | Severity | Findings |
|---|---|---:|
| `event_after_publication` | violation | 15 |
| `no_hazard_term_in_article` | contamination | 39 |
| `anthropogenic_trigger_missed` | contamination | 31 |
| `forecast_not_occurrence` | contamination | 5 |
| `many_events_one_case_day` | informational | 32 |

**68 case-days (4.5%) are excludable** — 15 impossible, 53 contaminated.

### The impossible ones

15 case-days are dated *after* the article reporting them was published. This is
the cheapest true invariant the project has and it had never been run. It also
works as a tracer: a date pulled from unrelated text has no reason to fall
before publication, so the rows it catches are disproportionately not landslide
reports at all. Among them: an army-chief appointment, a gold-smuggling story at
the airport, a border-opening notice, and a three-months-without-electricity
piece.

### Articles that never mention a landslide

39 case-days come from articles containing no landslide-family term anywhere in
the title or first 1,200 characters. Not a judgement about severity or scope —
the word is simply absent. The set includes a party convention in Chitwan, an
aid distribution to fire victims, and an essay on the relevance of the Bikram
Sambat calendar.

### Rainfall forecasts as case-days

5 case-days are forecasts or advisories with no occurrence anywhere:

> *"आजको मौसम : मेघगर्जन र चट्याङ्गसहित वर्षा हुनसक्ने, बाढी/पहिरोबाट जोगिन आग्रह"*
> — today's weather: thunderstorms possible, take care against floods and landslides

**This is the most damaging single failure available to this analysis.** The
study asks whether antecedent rainfall separates landslide days from
non-landslide days. A day taken from a forecast of heavy rain is a day selected
*on rainfall*, with no landslide attached, entering the case arm guaranteed to
carry high antecedent rainfall. It is contamination pointing in exactly the
direction of the study's own finding. Five is a small number; the mechanism is
not a small problem.

### Burials by placed earth

31 case-days describe a burial by a **spoil heap, sand pile or plotting site**
rather than a slope failure — *"माटोको ढिस्कोले पुरिएर"*, buried by a mound of
soil. The geography corroborates it: Dang ×4, Banke, Kailali, Bhaktapur,
Chitwan, Doti, Sindhuli, Surkhet — flat Terai and valley districts with no
landslide terrain. Several are explicit (a land-plotting site, a stone quarry,
workers digging a road drain).

These are not meant to be here. The pipeline classifies an `anthropogenic`
trigger and the analysis already drops those events; **the machinery works and
the vocabulary does not**. `config.yaml`'s `road_construction` trigger list
carries three Nepali terms — `सडक विस्तार`, `डोजर`, `निर्माण` — and none of them
is the word these reports use. So the events reach the case set as `unknown`.

Worth noting alongside: **1,025 of 1,999 case-set events (51%) have
`trigger = unknown`.** That is honest — the reproducibility rules forbid
defaulting unknowns — but it means the anthropogenic exclusion can only remove
what it positively identifies, and half the case set is untriaged.

### What is *not* a defect

1,999 canonical events over 1,508 case-days looks alarming until you remember
the analysis unit is the district-day: two separate landslides in one district
on one night *should* collapse. A first version of this audit called that
`duplicate_case_day` at contamination severity and put a quarter of the case set
on the excludable list for no reason. It is now informational, and only reports
district-days carrying four or more events.

## Does it change the result? No.

`scripts/run_integrity_sensitivity.py` drops the flagged case-days **and the
controls matched to them** — dropping one without the other would change the
case-control ratio and move the cutpoint for unrelated reasons — then recomputes
against the same quantities on the full set.

| | cases | R5 cutpoint | AUC |
|---|---:|---:|---:|
| full case set | 1,508 | 45.382 mm | 0.6576 |
| violations removed | 1,493 | **45.382 mm** | 0.6576 (+0.002) |
| violations + contamination removed | 1,440 | **45.382 mm** | 0.6591 (+0.003) |

**The cutpoint does not move at all**, at any window, under either scenario. AUC
improves by 0.002–0.005 — the direction you would expect from removing noise,
and far too small to matter. Every variant sits inside the baseline's bootstrap
interval.

That is the result worth having. The contamination is real, the mechanism behind
the forecast cases is serious, and **the headline threshold is robust to
removing every flagged day**. This is exactly the robustness check a referee
asks for, and it now has an answer rather than an assurance.

## What was deliberately not done

The obvious fix — adding `ढिस्को`, `प्लटिङ`, `क्रसर`, `उत्खनन` to the
`road_construction` trigger vocabulary — is a config change that alters the
inventory, and therefore needs its own versioned release and its own comparison
against the frozen v0.6.0 baseline. It is not folded into an audit. Nothing here
modified the inventory, any release, or the manuscript.

## A note on how these checks were built

Both judgement-dependent checks were wrong on their first attempt, in the same
way, and it is worth recording because the failure mode is generic to
keyword rules:

- the **forecast** check, on keywords alone, flagged 34 case-days — mostly real
  landslides that ended "20 more houses at risk". Fixed by requiring forecast
  language *and* the absence of any occurrence predicate.
- the **anthropogenic** check, listing every earthworks word, flagged 109 —
  because an excavator is what *clears* a landslide, a wall is what a landslide
  *destroys*, and gravel and sand are what the debris is made of. Those words
  are evidence of a landslide being dealt with. Narrowed to burial by *placed*
  earth plus unambiguous site types, it flags 31, which matches a hand count.

Both false-positive families are pinned by name in `tests/test_case_integrity.py`.
A noisy check gets ignored, and an ignored check protects nothing.

## Running it

```
PYTHONPATH=src python3 scripts/run_case_integrity_audit.py
PYTHONPATH=src python3 scripts/run_integrity_sensitivity.py
```

Outputs: `case_integrity_findings.csv` (one row per failed invariant with its
evidence), `case_integrity_findings_excludable_case_days.csv`,
`case_integrity_summary.json`, `case_integrity_sensitivity.json`.

The audit reports; it never deletes. A check that quietly dropped rows would
make the inventory depend on the auditor's judgement with no record of it.

## Status

- [x] Invariants implemented and tested (23 tests)
- [x] Run over the v0.6.0 case set — 68 excludable case-days (4.5%)
- [x] Threshold sensitivity measured — **cutpoint unchanged, AUC +0.003**
- [ ] Fix the Nepali `road_construction` vocabulary at source → new release
- [ ] Wire the violation checks into the release gate so a future cut cannot
      ship an event dated after its own publication
