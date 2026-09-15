# Proposed place fills: measured precision, and the decision not to apply them

**Date:** 2026-09-04. Reviewer: GS, 72 rows.
Measurement: `scripts/score_place_backfill.py` → `data/outputs/place_backfill_precision.json`.

---

## Decision

**Neither the municipality nor the ward fills enter the canonical inventory.**
They remain a separate, precision-labelled annotation layer
(`data/outputs/place_backfill_candidates.csv`), exactly as
`place_backfill_report.py` intended: *"PROPOSED, NOT APPLIED. Precision must be
measured on the labelled review pack before these values enter a versioned
inventory release."*

That measurement has now been made, and it does not clear the bar.

## What was measured

The review pack is a **stratified** sample, so a raw accept rate over the 72
labelled rows would not estimate population precision: municipality fills are a
small stratum sampled at roughly one in six, ward fills a large one sampled at
about one in twenty-nine. Precision is estimated within each stratum and
combined with weights proportional to stratum size. `unsure` verdicts are
excluded from both numerator and denominator and reported separately — counting
them as accepts would flatter the result, as rejects would punish the proposal
for the reviewer's uncertainty.

| Field | Population | Labelled (decided) | Precision | 95% CI (Wilson) | Stratified |
|---|---:|---:|---:|:---:|---:|
| Municipality | 84 | 15 | **0.600** | 0.358 – 0.802 | 0.640 |
| Ward | 1,696 | 56 (+4 unsure) | **0.857** | 0.743 – 0.926 | 0.877 |

By language: municipality 0.556 (en, n=9) and 0.667 (np, n=6); ward 0.828 (en,
n=29) and 0.889 (np, n=27).

## Why this is a no, for each field separately

**Municipality — 0.600, and the interval reaches down to 0.358.** Two of every
five proposed municipalities are wrong. There is no reading of that number under
which the fills belong in a published inventory. The population is 84 articles,
so applying them would add at most 84 values and roughly 34 errors. The trade is
bad in both directions at once: negligible gain, material corruption.

**Ward — 0.857, and it still does not earn its place.** This is a respectable
number for a cheap heuristic, and it was tempting. Two things decide against it.

1. **It buys nothing for the paper.** The rainfall analysis works at district-day
   resolution and collapses records within a district-day to one case-day. A ward
   changes no case, no control, no exposure, no threshold. The entire benefit is
   optional future sub-district work.
2. **It costs about 240 permanent errors.** 14.3% of 1,696 fills is roughly 240
   wrong wards, written into the canonical inventory as confident values that
   nothing downstream can distinguish from correct ones. A missing ward is
   honest; a wrong one is not.

Spending a known, irreversible 240 errors to buy an analysis nobody is currently
running is a bad trade. The fills lose nothing by waiting: they are already
computed, carried with their evidence snippets, and can be applied the day a
sub-district analysis actually needs them — by which point precision can be
re-measured on a larger sample and, if necessary, the rule tightened.

## What the labelled rows revealed, and what was done about it

Nine of the fourteen rejections share one cause, and the reviewer's notes name it
precisely: the evidence sentence locates a **person**, not the landslide.

> "Evidence identifies the deceased person's residence; it does not locate the landslide."
> "Ward 14 is the victim's destination/home in Rukum West, not the landslide site."
> "Ward 4 is given as the local speaker's address; the evidence does not place the landslide there."

This project already has a module for exactly that failure —
`nlp_attribution.is_person_attribution` — and it already governs district and
municipality extraction in `nlp_en` and `nlp_np`. The backfill was written
without it and inherited the very error it prevents. That guard is now wired into
`find_municipality_mentions`, so a municipality in a home address is not proposed,
and wards anchored to such a mention disappear with it.

**Its measured effect was small, and it is reported honestly as small.**
Corpus-wide it removed 10 municipality and 18 ward proposals. On the labelled
rows it caught 1 of 6 municipality rejections and 0 of 8 ward rejections, moving
municipality precision from 0.600 to 0.643 and leaving ward precision unchanged.
The diagnosis was right; the existing cue lists simply do not cover these
phrasings — "the chairperson of", "a local speaker", "members of a group", a
victim's *destination* rather than residence. Extending them is worthwhile future
work, but it must not be tuned against these 72 rows.

## The 72 labelled rows are now spent

They were used to diagnose a failure and to motivate and evaluate a code change.
Any further precision estimate made on them is optimistic by construction.

`place_backfill_report.py` now takes `--spent` (defaulting to the completed first
round) and excludes those rows from the review sample. Re-running with the
original seed had returned 15 of the 72 spent rows; the regenerated pack is now
**60 rows with zero overlap**, ready for an independent confirmation round
whenever the fills are wanted.

## If these fills are ever to be applied

1. Extend the attribution cues to cover the phrasings above, using articles
   **outside** the spent 72.
2. Label the fresh 60-row pack (`data/outputs/place_backfill_review_pack.csv`).
3. Re-measure. A field enters a release only if its stratified precision and the
   lower bound of its interval are both defensible for a published inventory —
   and the ward decision additionally requires an analysis that actually uses
   wards.
4. Apply as a **new versioned inventory release**, never in place, with the
   measured precision recorded in the release notes so downstream users can
   discount accordingly.
