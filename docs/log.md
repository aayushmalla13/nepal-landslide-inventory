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

### Progress

_(entries appended below as work proceeds)_
