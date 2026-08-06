# Working Log — Nepal Landslide Inventory

Purpose: running context for any contributor (human or Claude) picking up this repo.
Read this **after** `docs/TECHNICAL_REVIEW.md` and before touching code.

Newest entries at the bottom of each session. Session headers are dated.

---

## Standing context (read first)

**The problem, in one paragraph.** The pipeline turns 4,453 scraped Nepali/English news
articles into 1,071 canonical landslide events. The engineering is sound; the science
layer is not. Class-1 precision is 0.516, the district field is biased toward Kathmandu
by construction (Kathmandu is the #1 landslide district, which is geomorphologically
impossible), and every reported metric is in-sample because the 200-row evaluation set
was re-scored after the rules were tuned on it. See `docs/TECHNICAL_REVIEW.md` §0.

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

**Landmines.**

- Filter stages (`event_specificity.py`, `scope_filter.py`) historically ran
  `UPDATE article_events SET district = NULL, ...` on demotion. This destroys
  provenance and makes the stages non-idempotent. Anything that re-runs a stage twice
  and gets a different answer is hitting this.
- `config.yaml → keywords.exclude` exists and is read by no code. The hardcoded
  `METAPHOR_PATTERNS` in `event_specificity.py` does the work instead.
- `config.py` hard-fails unless there are exactly 8 sources with exactly the expected
  slugs. Two of those sources (kathmandu-post, ekantipur) collected almost nothing, so
  you cannot drop them without editing the validator.
- `data/outputs/canonical_events_final.csv` is produced by no code in this repo.

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
--stage export_final      regenerate canonical_events_final.csv from the DB
```

### Open decisions for the operator

1. **Re-run `extract`?** Required for a clean post-fix measurement. Nothing else
   recovers the destroyed district/date provenance.
2. **Road-obstruction events (§4.2).** 224 of 1,071 canonical events (21%) have
   road/highway in the representative title, and the FOLLOWUP patterns exclude
   others inconsistently. This is a scientific judgement about what the inventory
   *is*, and the review says it must be decided and stated in the methods
   section. Recommendation stands: keep them, flagged as
   `event_type = road_obstruction`, excluded from headline counts and BIPAD.
3. **`body_too_short` policy.** 50 class-1 events come from himalayan-times rows
   under 200 characters. Exclude them, or keep them flagged as title-only
   extractions with lower confidence?
4. **Study window.** `config.yaml` says 2015–2026, README and `paper_metadata`
   say 2015–2024. 485 rows fall in 2026. One of the three has to move.
5. **`landslide_inventory_final_snapshot_20260423.sqlite`** differs from the
   working DB and has no generating code. Needs a `DATA_VERSION` pointer or
   deletion.

### For whoever picks this up next

The locked test set at `data/outputs/locked_test_set_v1_labels.csv` is **drawn
but not labelled**. It is the gate on everything else: §5 says do not tune a
single rule before it exists, and it now exists. Label it (blind — the
predictions are in a separate file, keep them there), double-annotate ≥100 rows
for Cohen's κ, and only then start measuring.

The two highest-value pieces of work remaining are unchanged from the review:
**§8.1 event-site role classification** (which should move Kathmandu and Chitwan
off the top of the district table) and **§8.2 cross-language dedup** (1,002 of
1,071 clusters are singletons because `token_set_ratio` cannot match across
scripts). Neither was attempted in this session.

### Environment note

The repo targets Python 3.12; the sandbox used here had only 3.10, so
`datetime.UTC` was shimmed for test runs. Nothing about that shim is in the
repo. The `.venv/` in the project root is a macOS venv and will not run on
Linux.
