# Missing-data recovery: gazetteer rebuild and place backfill

**Date:** 2026-08-14 · **Status:** built and measured; inventory rebuild **not**
applied, gated on human review of the precision pack.

## 1. What was actually missing, and why

An audit of the 3,380 event-bearing (class 1) articles separated *absent from the
text* from *present but unextracted*:

| Field | Recorded | Text contains it | Gap | Verdict |
|---|---:|---:|---:|---|
| Municipality | 1,384 (40.9%) | 2,567 (75.9%) | 1,189 | recoverable |
| Ward | 3 (0.1%) | ≥411 (12.2%) explicit, far more suffixed | ~1,700 | recoverable |
| Deaths | 567 (16.8%) | 1,466 mention death language | 921 | partly recoverable, needs negation handling |
| Missing | 335 (9.9%) | 764 | 444 | partly recoverable |
| Injured | 208 (6.2%) | 815 | 616 | partly recoverable |
| Trigger | 1,597 (47.2%) | 1,541 mention rain | 259 | mostly already extracted |
| Event date | 3,380 (100%) | — | 0 | complete |
| District | 3,380 (100%) | — | 0 | complete |

The dominant cause was not the extraction patterns. **The municipality gazetteer
contained 142 English and 100 Nepali local units. Nepal has 753.** Roughly four
out of five local units simply had no entry to match against.

The ward gap had two causes: the Nepali pattern accepted only `वडा नं.`, missing
`वडा नम्बर`, `वडा नं` without the full stop, `वडानम्बर-६` and the very common
`<municipality>-<ward>` suffix form; and even when a ward candidate was produced,
a district candidate outranked it and the ward was discarded.

## 2. Gazetteer rebuild

`scripts/build_municipality_gazetteer.py` builds the gazetteer from two
checksum-pinned sources vendored under `data/reference/sources`:

| Source | Provides | Licence |
|---|---|---|
| bibekoli/local-levels-of-nepal-dataset | 753 local levels with English **and** Devanagari names, 77 bilingual districts, 4 unit types | none declared — see §6 |
| mesaugat/geoJSON-Nepal | 747 local-unit polygons with name and district | MIT |

The second source corroborates the first: 620 of 747 names match exactly after
normalisation (83.0%), and a further ~11% are spelling variants, so the factual
content is independently attested by an MIT-licensed dataset.

Result: **142 → 753 units**, 1,515 English aliases and 2,236 Nepali aliases.

### Corrections made, with evidence

Nothing was resolved silently. Each correction is declared in the build script
and re-emitted when it runs.

1. **Gulmi duplicate.** The bilingual source lists Chatrakot Rural Municipality
   twice in Gulmi and omits Dhurkot Rural Municipality. The geometry source lists
   Gulmi's twelve units including both Chatrakot and Dhurkot, so the duplicate row
   stands in for Dhurkot.
2. **Jagannath Rural Municipality was in the wrong district.** The previous
   project gazetteer placed it in Bajhang. Both reference sources place it in
   **Bajura**, and Bajhang's twelve units do not include it. Any article naming
   this municipality would previously have been assigned to the wrong district.
   No event in the current inventory names it, so no released record is affected.
3. **Six district spellings** in the source were mapped to the project's
   vocabulary (`Pachthar`→Panchthar, `Nawalparari East`→Nawalpur,
   `Nawalparasi West`→Parasi, `Kapilbastu`→Kapilvastu, `Rukum West`→Western
   Rukum, `Rukum East`→Eastern Rukum).
4. **Three legacy renames** resolved by hand where fuzzy matching could not:
   Lakhan Thapa→Sahid Lakhan, Taplejung Municipality→Phungling Municipality,
   Binayi Triveni→Binayee. Twenty-eight further legacy names were spelling
   variants and were folded in automatically at ≥95 similarity **within the same
   district**.

### Two safety properties added

**Shared names no longer infer a district.** Fifteen canonical names exist in more
than one district — Godawari Municipality in both Lalitpur and Kailali, Malika
Rural Municipality in Gulmi and Myagdi, Sunkoshi Rural Municipality in three
districts. `municipality_to_district()` previously returned whichever row loaded
first. It now returns `None` for these, and `municipality_districts()` returns all
candidates. The list is in `resources/municipality_ambiguous.csv`.

**District names cannot be read as municipalities.** Eighteen units share a name
with a district (Ramechhap Municipality in Ramechhap, Gorkha Municipality in
Gorkha, Kathmandu Metropolitan City in Kathmandu, …). Adding bare-stem aliases for
those would have made a plain district name in a dateline resolve to a
municipality — this was caught by an existing test that started returning
"Ramechhap Municipality" where "Doramba Rural Municipality" was correct. Bare
stems are now withheld for those eighteen; the full form still resolves.

The build is idempotent: the legacy gazetteer is read from a pinned snapshot under
`data/reference/sources`, never from `resources/`, so re-running cannot fold
generated aliases back into itself.

## 3. Place backfill

`src/landslide_inventory/unify/place_backfill.py` recovers municipality and ward
from text already collected. Rules, all enforced by tests:

- **Additive only** — an existing value is never overwritten.
- **District agreement required** — a municipality is accepted only when the
  gazetteer places it in the article's already-resolved district. This is what
  keeps the expansion from importing places from elsewhere in the article.
- **Wards must be anchored** — accepted only when adjacent to an accepted
  municipality mention (within 80 characters) or written as
  `<municipality>-<ward>` directly against the municipality span. A bare ward
  number elsewhere often belongs to a quoted ward chairperson from another ward.
- **Evidence carried** — every proposal records the matched text snippet.
- **Nothing imputed** — no match means no value.

### Measured yield — restated 2026-09-03

The first measurement of this backfill was taken against the v0.4.0 inventory,
where the extractor itself resolved a municipality for only 40.9% of class-1
articles. The district-assignment work (`DISTRICT_ASSIGNMENT_2026-09-03.md`) then
put the enlarged gazetteer to work *inside the extractor*, so most of what the
backfill used to propose is now simply extracted. Both measurements are shown
because the change is the interesting part:

| | v0.4.0 extractor | v0.4.0 + backfill (proposed) | current extractor | current + backfill (proposed) |
|---|---:|---:|---:|---:|
| Municipality recorded | 1,384 (40.9%) | 2,134 (63.1%) | **2,141 (63.0%)** | 2,235 (65.8%) |
| Ward recorded | 3 (0.1%) | 1,685 (49.9%) | 4 (0.1%) | **1,718 (50.6%)** |

The municipality recovery has therefore *already landed in the pipeline*, where
it is subject to the extractor's own district-agreement and attribution rules
rather than to a separate proposal layer. That is the better place for it.

What the backfill still contributes is **wards**: 1,714 of them, against 4 that
the extractor records. Ward is not used by the rainfall analysis, but it is the
finest location the corpus supports and it is what a municipality-scale exposure
analysis would eventually be joined on.

Ward fills are dominated by the `<municipality>-<ward>` suffix form. Of the 94
remaining municipality fills, 80 involve a name shared across districts and were
resolved only because the district agreed — which is precisely the case the
extractor declines to resolve on its own, so the two layers are complementary
rather than redundant.

Outputs (none of which modify the inventory):

- `data/outputs/place_backfill_candidates.csv` — all 1,726 proposals with evidence
- `data/outputs/place_backfill_review_pack.csv` — 72-row stratified sample to label
- `data/outputs/place_backfill_summary.json` — counts and the rules applied

## 4. Why this has not been applied to the inventory

Applying it would change `canonical_events_final.csv`, which is frozen in
inventory release v0.4.0. Under the project's own rules that requires a new
versioned release, and a new release should not be cut on unverified extraction.
Two things must happen first, in this order:

1. **Label the review pack.** 120 rows, stratified by language and by whether a
   ward was attached. Fill `municipality_verdict` and `ward_verdict` with
   `correct` / `wrong` / `unclear`. This yields the precision estimate that the
   manuscript would have to report.
2. ~~**Re-run the pipeline and measure district drift.**~~ **Done, 2026-09-03.**
   It did change, and measuring it found real errors in both directions. Full
   account: `docs/DISTRICT_ASSIGNMENT_2026-09-03.md`. In summary: 1.6% of
   class-1 articles changed district; three district-evidence rules were
   corrected as a result; district accuracy on the 123 labelled development rows
   rose from 0.813 to 0.862 with no labelled row regressing; the rainfall
   analysis was re-run and released as
   `nepal_landslide_rainfall_v0.3.0_20260903` (primary threshold 45.4 → 51.6 mm,
   association unchanged).

Note that item 1 and item 2 are independent gates. The pipeline changes above
concern the **gazetteer and the extractors**, which are part of the pipeline.
The **place backfill** in §3 is a separate artifact that still writes nothing to
the inventory and still waits on the review-pack labelling.

Because district assignment did change, a new inventory release is also
required — and is blocked on a newly drawn locked test set, since these are
classifier changes. Locked v7 (395 rows, seed 20260903) has been drawn and
awaits labelling.

## 5. What was deliberately not attempted

**Casualty backfill.** ~~Scoped but not built.~~ **Built 2026-09-03**, in the
order this section demanded: sample, label, then write patterns. The dominant
cause turned out not to be negation at all but that the Nepali patterns matched
digits only, while Nepali reports small tolls as words. Worse, the digit-only
fallback was recording *wrong* counts — missing counts, injured counts and even
an evacuation figure of six hundred thousand read as death tolls. Death counts
went 1,410 → 2,246 articles, missing 874 → 1,243, injured 544 → 839, with none
lost, and 58 articles now carry a guarded explicit zero. Full account:
`docs/CASUALTY_EXTRACTION_2026-09-03.md`.

**Trigger backfill.** Only 259 articles mention rain without a trigger recorded —
a small return for the same negation-handling risk.

## 6. Open item: licence of the bilingual source

Administrative unit names and their district assignment are government facts, and
the MIT-licensed geometry source independently attests ~94% of them. The bilingual
source repository carries no LICENSE file. Before public redistribution of the
derived gazetteer, either confirm that source's terms or regenerate the Nepali
names from an official government or OCHA release. Flagged rather than ignored.

## 7. Reproduce

```bash
python3 scripts/build_municipality_gazetteer.py --check   # verify, write nothing
python3 scripts/build_municipality_gazetteer.py           # rebuild resources/
PYTHONPATH=src python3 scripts/place_backfill_report.py   # propose fills
python3 -m pytest tests/test_place_backfill.py tests/test_gazetteer_municipality.py
```
