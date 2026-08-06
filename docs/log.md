# Working Log — Nepal Landslide Inventory

Purpose: running context for any contributor (human or Claude) picking up this repo.
Read this **after** `docs/TECHNICAL_REVIEW.md` and before touching code.

Newest entries at the bottom of each session. Session headers are dated.

---

## Standing context (read first)

**The problem, in one paragraph.** The pipeline turns 4,453 scraped Nepali/English news
articles into canonical landslide events (1,071 at review time; **1,127 now**, of which
**1,003 are headline landslide events** and 124 are typed `road_obstruction`). The
engineering is sound; the science layer is not. Class-1 precision was 0.516, the district
field is biased toward Kathmandu by construction (Kathmandu is still the #1 landslide
district, which is geomorphologically impossible), and every reported metric is in-sample
because the 200-row evaluation set was re-scored after the rules were tuned on it.
See `docs/TECHNICAL_REVIEW.md` §0.

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
  you cannot drop them without editing the validator. ~~Still open.~~
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
--stage event_typing      label road_obstruction / title_only on canonical_events
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

### Open decisions for the operator

Items 1–4 were decided and applied this session (see above). Remaining:

1. **Re-fetch the 615 himalayan-times HTTP 429 URLs**, with backoff. They are
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

The highest-value piece of work remaining is **§8.1 event-site role
classification**. Road typing already moved Chitwan down (89 → 58), but
**Kathmandu is still #1 at 73 headline events**, which is geomorphologically
impossible and is the finding a reviewer will stop at. The cause is `location.py`
taking `ordered[0]` from a candidate list scored to favour early mentions, so a
myRepublica dateline (`KATHMANDU, July 12: A landslide killed three in
Sindhupalchok...`) wins deterministically. Much of the plumbing exists —
`MYREPUBLICA_DATELINE_PATTERN` is already detected in `extract_stage.py`, it is
just used to trim text rather than to veto a place candidate.

Second: **§8.2 cross-language dedup**. Multi-source clusters went 69 → 81 after
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
