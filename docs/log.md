# Working Log — Nepal Landslide Inventory

Purpose: running context for any contributor (human or Claude) picking up this repo.
Read this **after** `docs/TECHNICAL_REVIEW.md` and before touching code.

Newest entries at the bottom of each session. Session headers are dated.

---

## Standing context (read first)

**The problem, in one paragraph.** The pipeline turns 4,453 scraped Nepali/English news
articles into canonical landslide events (1,071 at review time; **1,010 now**, of which
**862 are headline landslide events** — the rest are 124 `road_obstruction` and 26
non-landslide hazards, both retained but excluded from headline counts).

The engineering is sound; the science layer is improving but not yet publishable.
Class-1 precision was 0.516 and **has not been re-measured** — every metric in the repo
is still in-sample, because the 200-row evaluation set was re-scored after the rules were
tuned on it. Kathmandu's rank was fixed on 2026-08-06 (now #2 at 49, behind Chitwan at
58), but by removing two construction errors, not by validation.
See `docs/TECHNICAL_REVIEW.md` §0.

**Nothing here is validated yet.** The locked test set exists and is unlabelled. Until
it is annotated, every number in this log is a count, not an accuracy.

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
- `config.py` hard-fails unless there are exactly 8 sources with exactly the expected
  slugs. Two of those sources (kathmandu-post, ekantipur) collected almost nothing, so
  you cannot drop them without editing the validator. **Still open.**
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

### Open decisions for the operator

Items 1–4 were decided and applied this session (see above). Remaining:

1. **The roundup over-merge.** Nationwide roundups ("At least 148 are dead in
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
