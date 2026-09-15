# Multi-event district-day extraction

## Why this exists

The granularity diagnosis (`docs/GRANULARITY_DIAGNOSIS.md`) established that
29.3% of the articles the pipeline keeps as class-1 events report **more than
one landslide failure**. The pipeline emits one record per article, so those
articles are under-counted. That finding closed with a decision not to
reclassify them — a `multi` article still yields a correct district-day, and
deleting it would delete a true case-day — but it left the obvious remedy open:
emit **several** district-days from one article instead of one.

This document is the design for that, and the measurement that gates it.

## Part 1: what the yield actually is

The temptation is to read "29.3% of articles report several failures" as "the
inventory under-counts by 29.3%". That inference is wrong, because **the
analysis unit is the district-day, not the failure**. Three houses buried on
three slopes in Ilam Municipality on one night is one district-day, and the
inventory already has it.

So all 47 human-labelled `multi` articles in the class-1 development pack were
read in full and adjudicated for the only thing that matters: how many
**additional, defensible `(district, date)` pairs** each one supports. The
adjudication is recorded per article, with reasons, in
`data/outputs/multievent_yield_audit.csv`, and scored by
`scripts/score_multievent_yield.py`.

| | |
|---|---:|
| `multi` articles audited | 47 |
| articles yielding **no** additional district-day | **31 (66%)** |
| additional district-days, strongly supported | 10 |
| additional district-days, contestable | 7 |
| of those 17 pairs, already in the inventory from another article | 4 |

Reweighted by the class-1 pack's stratum inclusion weights and discounted for
collisions, that projects to **+198 district-days on the 1,508 the v0.6.0
analysis uses: +13.2%, 95% CI [6.9, 20.2]**.

Three of the four collisions are Chitwan on the Narayangadh–Muglin corridor,
which is reported so relentlessly that a second article rarely contributes a
district-day the inventory lacks.

A materiality threshold of 5% was fixed in the module *before* the numbers were
computed, because a gain smaller than that could not repay a new inventory
release plus a fresh human-labelled locked test set. The lower bound clears it.
**The project is worth building.**

### How much confidence that number deserves

Less than the point estimate suggests, and the direction of the error matters.
82% of the estimate comes from a single stratum (`np:signal`, 17 sampled
articles). The **largest** stratum — `np:plain`, standing for 1,788 of the 3,182
class-1 articles — contributed four `multi` articles, all of which yielded
nothing. The bootstrap can only ever resample zeros from those four, so the
interval is *conditional on that stratum truly yielding nothing*, which four
observations cannot establish. The interval is therefore conservative at the
top: the true yield is more likely to be higher than lower.

## Part 2: why a naive extractor would be a disaster

The same read produced the finding that actually constrains the design. Most
district names in these articles are **not failure locations**. Resolving every
place candidate the existing extractor already surfaces would emit 42 extra
district-days across the 47 articles, of which at most 17 are defensible —
a precision of **24% (strong only) to 40% (including contestable ones)**.
Projected to the inventory, a naive extractor would inject false case-days
equal to **43% of the entire current case set**.

That is not a tuning problem. It would be a systematic corruption of the
inventory, and — because the false districts cluster on highway corridors and
capital datelines — it would be *spatially correlated with rainfall*, which is
precisely the kind of error the threshold analysis cannot absorb.

The reasons a district gets mentioned without failing there, each observed and
recorded in the audit's `trap_kind` column:

| Trap | What it looks like | Example |
|---|---|---|
| `victim_home_district` | the dead and injured are identified by where they were *from* | c1-0034: nine die at Timure, **Rasuwa**; Sindhupalchok and Nuwakot appear only as the victims' home districts |
| `dateline` | the reporting city, not the event | c1-0009: "Surkhet, April 7" on a Dailekh/Kalikot event |
| `road_destination` | the far end of a blocked corridor | c1-0011: "Beni–Jomsom road connecting **Mustang**" — the failures are all in Myagdi |
| `stranded_destination` | where the stuck vehicles were going | c1-0047: Kathmandu, Pokhara, Chitwan, Gorkha, Tanahu, on a Lamjung blockage |
| `publisher_address` | the outlet's own footer | c1-0002: Lalitpur |
| `retrospective_bulletin` | a police status roundup of *already-reported* blockages | c1-0079: Bhojpur blocked since Baisakh 12, Salyan already **reopened** |
| `flood_not_landslide` | the hazard is a flood | c1-0059, and the Bhojpur item in c1-0044 and c1-0079 |
| `hospital_referral` | where the casualties were taken | c1-0081: Jajarkot, for a failure in Rukum West |
| `adjacency_mention` | "close to the border with X" | c1-0010: Syangja |

## Part 3: the design

### The rule

A district `D` earns an **additional** record only if some sentence jointly
carries all three of:

1. a **failure term** — पहिरो, लेदो, landslide, debris flow, mudslide, rockfall;
2. a **location** resolving to `D` — the district name, or a municipality/ward
   that maps to it;
3. an **occurrence predicate** — खस्यो, गयो, जाँदा, पुरिएर, बगाएको, occurred,
   buried, swept, hit, blocked — and *not* a risk, prevention, clearing or
   reopening predicate.

and no trap pattern from the table above matches that mention.

Everything about this rule is deliberately asymmetric. A missed recovery costs
one district-day out of a projected 201. A false recovery puts a fabricated
landslide into the canonical inventory, where nothing downstream can tell it
from a real one. So every ambiguous case is dropped.

### Dates are the harder half

The reproducibility rules forbid treating publication or capture dates as event
dates, and the audit shows exactly why that bites here: the district-rich
articles are *status bulletins* that mix today's failures with ones from a week
ago (c1-0044 carries failures from Baisakh 12, 16 and 22 in four sentences).

So a recovered record takes its date **only** from an explicit anchor in its own
sentence:

- an explicit BS date (`वैशाख १२ गते`) via the existing `bs_to_ad`;
- an explicit AD date;
- a weekday name resolved backwards from the publication date via the existing
  `_infer_weekday_date`;
- `गएराति` / `last night` / `आज` / `today`, publication-relative.

**If a sentence carries no anchor, no record is emitted** — the article's
primary date is never reused for a secondary record. Reusing it would
manufacture exactly the error the granularity work was trying to fix (several
days' failures collapsed onto one) and would also manufacture collisions that
hide the problem from the collision check.

This rule is what makes the *temporal* recoveries work honestly: c1-0039 names
Wednesday, Tuesday and Monday explicitly, and c1-0040 names Tuesday and Monday,
so those five district-days are anchored. Articles that gesture at "days
earlier" (c1-0012) emit nothing.

### What changes in dedup

One article may now contribute to several `(district, date)` clusters. Two
constraints follow, both aimed at keeping the recovered records from
masquerading as independent corroboration:

- `cluster_size` and `sources_json` count **distinct articles**, not records,
  so one article spanning three district-days is not counted as three
  independent sources for any one of them;
- a **secondary** record may not be the sole basis for a canonical event unless
  its evidence clears a higher bar than a primary record — secondary records are
  the ones carrying the 21–36% naive precision, and a district-day resting on
  one secondary mention alone is the single most likely way a fabricated event
  enters the release.

Every recovered record carries `extraction_basis = "secondary_failure"` and its
supporting sentence, so the inventory stays auditable and any later analysis can
exclude them wholesale.

**Implemented** in `unify/dedup_stage.py`, with one further change the design
had not anticipated. Union-find was keyed on `url`, which was sound while each
article produced exactly one event and fails silently once it does not: a URL
key collapses an article's several district-days into a single node, and every
recovered district-day disappears into whichever cluster the primary joined.
Records are now keyed by `url#district@date`, and two records sharing a URL are
forbidden from merging with each other — their body text is identical, so the
similarity path would otherwise reunite them on every run, undoing the
separation and inflating the cluster size at the same time.

Three supporting changes: `choose_representative` prefers a directly reported
record over a recovered one regardless of confidence, because the recovered
record's casualties and municipality belong to the article's own subject; a
recovered record carries no impact fields at all (`to_record` nulls deaths,
missing, injured, municipality, ward and trigger explicitly); and
`cluster_summary` gains `record_count` and `secondary_record_count`, with a
migration, so the record-level counts `size` no longer reports are still
available. For a run with no recovered records every one of these is a no-op,
which is what keeps the v0.6.0 baseline comparable.

## Part 4: what the implementation achieves so far

`src/landslide_inventory/unify/multievent.py`, scored by
`scripts/score_secondary_extraction.py` against the 47-article audit:

| | |
|---|---:|
| secondary district-days emitted | 6 |
| precision | 1.00 |
| recall | 0.35 (0.40 on strongly supported pairs) |
| trap violations | **0** |
| records emitted from 53 non-`multi` articles | **0** |

The last row is the negative control, and it is the most informative number
here — see Part 5.

The precision figure must not be read as a result. The audit is what the rules
were written from, so agreement with it is close to guaranteed; the honest
precision number will come from locked test v8. **Recall of 0.35 is the
meaningful development figure**, and it is deliberately where the asymmetry put
it: the rules refuse anything contestable. It fell from 0.53 when the
same-district gate in Part 6 was added, which was a good trade.

Three entries in the audit were revised during implementation, when the
extractor disagreed with the first read and the article text turned out to
support the extractor. Revising ground truth in response to a model's output is
the fastest way to make a development measurement dishonest, so the changes are
recorded in full — in the audit's own `note` column and in a comment block in
the scoring script — and were applied symmetrically, including one downgrade
that cost recall:

- **c1-0017 Dhading, 14 June** — added. Explicitly dated, in `Gangajamuna Rural
  Municipality-5`; the first read stopped at the two occasions near the top of
  the article.
- **c1-0035 Myagdi, 21 June** — added. The first read dismissed it as
  "retrospective", conflating *reported late* with *unusable*. An explicitly
  dated failure in a named district is a valid case district-day whenever it
  was written up.
- **c1-0033 Manang** — downgraded from strong to contestable. Every enumerated
  failure is in Lamjung; Manang enters only through the road name
  "Lamjung–Manang" and through Chyame, the corridor endpoint. That is the
  `road_destination` pattern.

### What it still misses, and why that is acceptable

Eight defensible pairs are not reached. Each is a deliberate consequence of a
precision-first rule rather than a bug:

| Missed | Why |
|---|---|
| c1-0044 Kavrepalanchok | the failure term is in the previous sentence; the sentence itself says only "blocked" |
| c1-0044 Myagdi | its sentence carries three dates, so nothing in it can be attributed |
| c1-0039 Chitwan ×2 | the dated sentences name a road spot, not a district, and the article names another district elsewhere |
| c1-0092 Chitwan | the two corridor sections are never tied to their districts in one sentence |
| c1-0002 Myagdi | a failure on the Baglung/Myagdi boundary — caught by the adjacency rule, correctly |
| c1-0033 Manang | the road-destination rule, correctly |
| c1-0083 Palpa | its only predicate is clearing, which is not an occurrence |

### Gazetteer hazards found during implementation

Three false-positive families came from the shared gazetteer rather than from
the article text, and all three would have fabricated events:

- **fuzzy municipality matching.** `normalize_municipality` falls back to a 90%
  similarity match. "Shubh Kalika Rural Municipality" of Kalikot matches
  "Kalika Rural Municipality" of **Rasuwa**. Right for the primary extractor,
  where the input is already believed to be a municipality; wrong here, where
  the input is an arbitrary capitalised word. This module bypasses the fallback.
- **bare tokens that are also municipality names.** The given name *Ramprasad*
  is a rural municipality in Bhojpur; the *Koshi* Highway shares its name with a
  rural municipality in Sunsari. Fixed by requiring the text to actually say
  "municipality" / "गाउँपालिका".
- **partial municipality names.** "Likhu Tamakoshi Rural Municipality" is in
  Ramechhap, "Tamakoshi Rural Municipality" in Dolakha. Fixed by taking the
  longest span that resolves and abandoning the mention thereafter.

## Part 5: what the corpus run changed

Running the extractor over all 3,738 kept class-1 articles was supposed to be a
confirmation. It was not. It recovered **379 novel district-days, +25.1% of the
case set** — above the projection's upper bound of 20.2%, from an extractor
reaching only half the defensible recoveries. A yield that beats its own ceiling
is not good news; it means something is being recovered that should not be.

The development audit could not have caught it, because **the audit covers only
`multi` articles** while the corpus run applies the extractor to every kept
class-1 article — around 70% of which report a single event. Nothing measured so
far said what the rules do on an ordinary article.

The class-1 pack answers that directly: it carries 43 human-labelled `single`
articles, 5 `roundup`, 4 `not_applicable` and 1 `unclear`. A record emitted from
a `single` article is wrong by definition. Used as a negative control, it found
**3 of 43 `single` articles producing records**, and a `roundup` article
producing two more. Extrapolated to the corpus, roughly a hundred fabricated
district-days.

### The same-district failure

The diagnosis was in the gap distribution. Of 277 same-district recoveries,
**134 sat exactly one day from their article's own primary date**, and 191
within three. A genuine second occasion does not pile up at a one-day gap; that
is the signature of one landslide being redescribed by weekday and read as a
new event. Two of the three `single`-article offenders were exactly this, and
one of them was worse than a duplicate: in c1-0063 the *recovered* date
(14 August, the Lidi landslide) was correct and the pipeline's primary date
was wrong, so emitting it would have produced two district-days for one event
while leaving the original error in place.

The fix is the standard dedup already applies when deciding whether two reports
describe one event: **a same-district recovery must name a municipality, and a
different one from the article's primary**. A sentence naming no local unit
fails, because the article's own event is the default reading of an unlocated
failure.

Two other things the corpus run surfaced:

- **the assessment-team itinerary**, a tenth trap: *"a team went to Taplejung,
  Panchthar and Sankhuwasabha to assess the damage caused by floods and
  landslides"* passes the occurrence test on its own terms and names three real
  districts, but reports a visit.
- **a gazetteer shortcut that defeated the fuzzy guard.** `_lookup_keys` tries
  the trailing 2- to 5-token suffixes of its input. "Shubh Kalika Rural
  Municipality" is a real local unit of **Kalikot**; its 3-token suffix "Kalika
  Rural Municipality" is a real local unit of **Rasuwa**, and matches *exactly*,
  so bypassing the fuzzy fallback did nothing. Resolution now requires the full
  span's own key. Worth recording that the test meant to catch this had been
  passing for the wrong reason — a broken regex was mangling the name before
  the gazetteer saw it, and when the regex was fixed the fabricated Rasuwa
  record reappeared with the test still green. The guarantee is now pinned at
  the resolver rather than through the extractor.

### After the fixes

| | before | after |
|---|---:|---:|
| corpus records | 685 | 419 |
| novel district-days | 379 (+25.1%) | **258 (+17.1%)** |
| of those, firm-dated | 288 (+19.1%) | **166 (+11.0%)** |
| records from 53 non-`multi` articles | 5 | **0** |
| development recall | 0.53 | 0.35 |

+17.1% now sits inside the projected interval [6.9, 20.2] rather than above it,
and the firm-dated subset at +11.0% is close to the +13.2% point estimate. The
negative control is clean: zero records from every human-labelled article that
reports one event or none.

That agreement is reassuring but should not be over-read. The projection and the
corpus run share the same underlying adjudication, so they are not independent,
and the corpus figure is still a *floor* — the extractor reaches about a third
of the defensible recoveries.

## Part 5b: the measurement that actually matters, and why it does not exist yet

After the Part 5 fixes the corpus yield settled at **145 novel district-days,
+9.6%** (91 firm-dated, +6.0%), the development audit still reported precision
1.00, and the negative control was still clean. It would be easy to stop there
and cut a release.

That would be wrong, and the reason is worth stating plainly: **nothing measured
so far can detect the errors that matter.** The development audit covers 47
`multi` articles, which the rules were written from. The negative control covers
53 articles reporting one event or none, and proves only that the extractor stays
quiet — not that what it emits is right. The corpus is dominated by neither
population.

So I read random recovered records by hand. Twice, twelve at a time. Both times
roughly **four in ten looked correct**, and both times the read found error
families no measurement had flagged — corridor labels, travel origins, enumerated
district lists, a Bikram Sambat year written in the text and ignored. Every fix
was justified and each one lowered the yield. But that loop has no stopping rule:
I cannot tell whether the next twelve would be clean or would surface a fifth
family, and "I read some and they looked better" is not a result.

Two defects found this way are worth recording separately, because they are real
regardless of what happens to this project:

- **an explicit BS year was discarded.** `९ असार २०७४` — a 2024 article recalling
  a 2017 failure — had its year replaced by the publication year and landed seven
  years out on the right month and day, which is exactly the shape that survives
  a plausibility check. Fixed, and a `MAX_DAYS_FROM_PRIMARY` bound added.
- **the municipality gazetteer is missing Kaligandaki Rural Municipality in
  Syangja.** It carries only the Gulmi one, so a Syangja event resolved to Gulmi
  and `is_ambiguous_municipality` saw nothing to flag. Recorded rather than
  patched: changing the gazetteer changes the primary extractor's behaviour too,
  and that belongs in its own piece of work against the frozen baseline.

### What replaces the guessing

`scripts/draw_secondary_precision_pack.py` draws every one of the 154 novel
recovered district-days — a census, not a sample, because a proportional draw of
120 covered 79% of them and bought sampling error for nothing. Each row carries
its evidence sentence and the full article, and asks two questions: did a
landslide happen in *that district*, and was it on *that date*. The date basis,
the confidence and the stratum are held in a separate file the annotator is asked
not to open.

Strata are recorded for reporting, on the two axes the error analysis showed
actually separate good records from bad: firm against soft date anchors, and
cross-district against same-district.

| stratum | population |
|---|---:|
| `cross:firm` | 85 |
| `cross:soft` | 62 |
| `same:firm` | 7 |

**This is a real gate, not a formality.** If precision comes back near the
development figure, the recovered district-days go into a new release. If it
comes back near 40%, they do not, and this extractor is either rebuilt or
abandoned — which costs nothing already published, because the v0.6.0 analysis
never depended on it.

## Part 6: how this gets evaluated

The audit of the 47 is a **development** set. It was read while designing the
extractor, so it cannot also measure it — scoring the extractor against the
adjudication that shaped it would report how well the rules encode my own
reading, not how well they generalise.

So:

- the extractor is developed and tuned against the 47-article audit;
- it is then evaluated on **locked test set v8**, drawn fresh and labelled by a
  human, which does not yet exist. v7 is spent.
- v8's labelling task is different from v7's and needs its own guide: the
  annotator is asked not "is this one event or several" but "list every
  `(district, date)` this article supports", which is the quantity the extractor
  actually emits.

No new inventory release ships before v8 is scored. The v0.6.0 release and its
frozen locked-test artifacts stay exactly as they are and remain the baseline
against which any new release is compared.

## Status

- [x] Yield measured and gated — **material**, +13.2% [6.9, 20.2]
- [x] Trap taxonomy derived from a full read of all 47 `multi` articles
- [x] Design fixed, with the asymmetry and the no-anchor-no-record rule
- [x] Extractor implemented (`unify/multievent.py`)
- [x] Extractor measured on the development audit — recall 0.35, zero trap violations
- [x] Dedup rule revised so one article cannot corroborate itself
- [x] Extractor run across the full corpus; over-recovery found and fixed
- [x] Negative control on 53 human-labelled non-`multi` articles — zero records
- [x] Precision-audit pack drawn — all 154 novel source-level claims (144 distinct district-days)
- [x] Precision pack labelled and scored — **gate failed**, 52/154 (33.8%)
- [x] Verified claims isolated — 52 source claims representing 48 district-days;
      manual supplement only, not integrated
- [x] Extractor redesigned as strict v2 - explicit same-sentence AD/BS dates only
- [x] Strict-v2 dry run completed - 23 source claims, 21 district-days, 13 novel;
      all 13 novel claims overlap spent human-confirmed development examples
- [x] Locked test set v8 drawn - 145 previously unjudged articles, zero overlap
      with prior evaluation URLs
- [x] Locked test set v8 model-labelled - 145/145 rows complete, with `ChatGPT`
      recorded as annotator on every row; this is not independent human validation
- [x] Strict v2 diagnostic scored on v8 - 0/59 pipeline-missing exact pairs
      recovered; precision not estimable because its sole prediction was unresolved
- [x] Release decision recorded - **do not integrate automated secondary records**

Nothing in the inventory, the v0.6.0 release, or the manuscript has been changed
by this work. The extractor is not wired into the pipeline; it runs only from
the dry-run and scoring scripts. The failed gate means it must remain unwired.
See `docs/SECONDARY_PRECISION_RESULT.md` for the scored result and decision.

### The obstacle wiring will hit

`article_events` carries `CREATE UNIQUE INDEX idx_article_events_url ON
article_events(url)` — the schema-level statement that one article is one event.
Recovered records cannot be stored there while it stands. That index is load
bearing for every other stage, so lifting it is its own piece of work and should
not be folded into this one. The likely shape is a separate `secondary_events`
table feeding dedup alongside `article_events`, which also keeps the recovered
records physically separable for any analysis that wants to exclude them.
