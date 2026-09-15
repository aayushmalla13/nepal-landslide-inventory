# The Nepali anthropogenic trigger was excluding real landslides

## What went wrong

The analysis drops `anthropogenic` and `earthquake` events from the case arm.
That is correct: a spoil heap collapsing at an excavation site carries no
physical relationship to antecedent rainfall. So whatever the trigger classifier
calls anthropogenic **leaves the study**.

The English and Nepali routes classified it differently, and the asymmetry was
never intentional:

| | test applied |
|---|---|
| English | a configured term **and** a phrase placing the earthworks at the failure (`_has_anthropogenic_trigger`) |
| Nepali | a configured term, alone |

And the Nepali vocabulary was three terms: `सडक विस्तार`, `डोजर`, `निर्माण`.

Two of those three are **aftermath** words. A `डोजर` is the machine that clears
a landslide. `निर्माण` appears in every "निर्माणाधीन सडक" — a road under
construction is *where* landslides happen, not a reason the slope moved.

## How much it cost

**452 canonical events were tagged `anthropogenic` and dropped from the
analysis. 416 of them came through the Nepali route.** The matched term was
`निर्माण` in 203 cases and `डोजर` in 128.

Reading them, the great majority are ordinary rainfall-triggered landslides:

> *कालीखोलामा पहिरो, मुग्लिन सडक अवरुद्ध* — landslide at Kalikhola, Mugling road blocked
> *एकैदिन तीस ठाउँमा पहिरो* — landslides at thirty places in one day
> *कर्णाली राजमार्गमा चट्टाने पहिरो, २ दिनदेखि यातायात ठप्प* — rock landslide on the Karnali Highway

The loss was also **non-random**. A dozer turns up when a road is blocked, so the
rule preferentially removed *road-corridor* landslides — including the
`सुक्खा पहिरो` (dry landslide) cases, which are exactly the low-rainfall events
that would pull a threshold down.

The same three terms missed the burials that genuinely *are* anthropogenic,
because those reports use a word that was not in the list — `माटोको ढिस्कोले
पुरिएर`, buried by a mound of soil. Those arrived as `unknown` and stayed in the
analysis. The classifier was wrong in both directions at once.

## The fix

Two halves, both needed:

1. **`nlp_np/extract.py`** — `_has_anthropogenic_trigger_np` mirrors the English
   two-part test. A configured term must appear *and* a phrase from
   `NP_ANTHROPOGENIC_CONTEXT` placing the earthworks at the failure: burial by
   placed earth (`माटोको ढिस्कोले पुरि`), or an extraction site
   (`प्लटिङ`, `क्रसर`, `उत्खनन`, `खन्ने क्रम`, `पर्खाल लगाउँदा`).

2. **`config.yaml`** — the Nepali `road_construction` list gains `ढिस्को`,
   `ढिस्का`, `प्लटिङ`, `क्रसर`, `उत्खनन`, `खन्ने`, `खन्दै`, so the placed-earth
   burials have a term to match at all.

`मजदुर` and `कामदार` are deliberately **absent** from the context list.
Labourers are killed by real landslides too, and their presence says nothing
about what moved the slope.

## Measured effect on the Nepali route (2,082 canonical events)

| transition | events |
|---|---:|
| anthropogenic → unknown | 191 |
| anthropogenic → rainfall | **178** |
| unknown → anthropogenic | 33 |
| rainfall → anthropogenic | 7 |
| anthropogenic → earthquake | 3 |

**372 events released; 40 newly excluded.** The 178 that land on `rainfall`
matter most: those articles explicitly say it was raining, which is direct
confirmation they were rainfall-triggered landslides thrown away by a dozer.

Projected onto the case set: **+287 new district-days (+19.0%)**, and 33
existing case-days correctly leave as anthropogenic.

## The caveat that stops this shipping on its own

A 15-row read of the released events found roughly **10 genuine landslides and 5
that are not events at all** — a minister's statement about Melamchi, a feature
on landslide victims living under tarpaulin, a girl swept away by a *stream*.

Those articles were being excluded **by accident**, via a trigger tag that had
nothing to do with why they should be excluded. Fixing the trigger removes that
accidental filter and exposes a pre-existing gap in the scope and specificity
filters.

So the honest statement is: **the trigger classification is now correct, and
that correctness reveals a second defect.** Shipping the trigger fix alone would
add ~287 case-days of which perhaps a third are aftermath and statement
articles. That trades a known bias for an unknown one.

The 10/15 figure is a read of fifteen rows, not a measurement. Before a release,
the released events need a labelled sample of their own — the same treatment the
secondary-extraction records are getting.

### The cheap fix does not work

The obvious move is to release only the events the pipeline already calls
`specificity_reason = event_specific`, reusing a judgement the pipeline has
already made rather than inventing a new one. **It does not separate them.**

Tested against the ten rows read by hand:

| | aftermath (5) | genuine (5) |
|---|---|---|
| `event_specific` | 3 | 3 |
| `damage_only` | 2 | 0 |
| `roundup` | 0 | 1 |
| `event_specific_followup` | 0 | 1 |

A minister's commitment on Melamchi and a feature on victims living under
tarpaulin both come through as `event_specific`; the Narayangadh–Muglin
blockage — a real landslide closing a highway — comes through as `roundup`.
Filtering on that field would drop genuine events and keep the aftermath ones.

The distribution over all 415 released events (259 `event_specific`, 52
`damage_only`, 42 `roundup`, 26 `event_specific_followup`, 23 `followup`) offers
no usable cut either, because the field is close to uncorrelated with the
distinction that matters here.

So the gap cannot be closed by reusing existing machinery. It needs either a
labelled sample of the released events or a classifier built for the question —
"is this article reporting a failure, or reporting *about* one that already
happened?" — and neither is a quick win. That is the honest reason this fix is
staged rather than shipped.

## Status

- [x] Defect identified, mechanism confirmed, both directions measured
- [x] Fix implemented in `nlp_np/extract.py` and both config files
- [x] 16 tests covering both directions and the structural parity of the routes
- [ ] Label a sample of the 372 released events to size the aftermath problem
- [ ] Close the scope-filter gap the fix exposes
- [ ] Re-run the pipeline, cut a new inventory release, compare against v0.6.0

**Nothing has been re-run and no release has been cut.** The v0.6.0 numbers
stand. The code change is staged and tested; the inventory it would produce has
not been generated, and no new threshold has been computed — computing one now,
before the aftermath question is settled, would produce a number that looks
authoritative and is not.
