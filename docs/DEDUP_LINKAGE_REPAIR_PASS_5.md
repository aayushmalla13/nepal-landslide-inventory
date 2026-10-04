# Dedup linkage repair pass 5

Date: 2026-09-25

## Scope

This development pass repaired the canonical-event linkage failure found after
parser remediation pass 4. It used spent validation labels only for diagnosis
and regression development; none of the results below is a new precision
estimate.

## Defects repaired

1. Pairwise seven-day links were joined with unrestricted single linkage. A
   chain of locally eligible pairs could therefore create one cluster spanning
   as many as 18 days.
2. Similar prose could bridge different dates without an independent factual
   match, especially for recurring road failures.
3. Matching municipality made the old same-language guard effectively pass
   even when casualty vectors conflicted.
4. Cross-language structured scores could be accepted with too little factual
   support after missing fields were renormalized.
5. Same-day, same-language reports with strong factual agreement could remain
   split when their prose differed.
6. English "separate landslide incidents" and Nepali/English second-incident
   connectors with a second ward/municipality casualty were not consistently
   classified as aggregate stories.

## Implementation

- Added `dedup.max_cluster_span_days: 1` and enforce it during union, so
  transitive linkage cannot exceed the configured cluster diameter.
- Require language-neutral corroboration for cross-date links.
- Veto candidate pairs with contradictory comparable casualty fields.
- Require two factual signals for cross-language structured merges.
- Added a conservative same-day recovery path requiring a named municipality
  plus casualty/ward agreement or strong place and TF-IDF agreement.
- Added bilingual aggregate-story patterns for distinct second incidents.
- Corrected collision logging: the count is the number of extra clusters that
  share an identity, not the number of confirmed missed merges.

## Rebuild result

- Articles: 10,203
- Specificity retained/rejected: 4,017 / 6,186
- Canonical events: 2,656, with unique event and cluster IDs
- Multi-article clusters: 415
- Maximum cluster span: 1 day (previously 18 days)
- Same-identity collision groups: 328
- Extra clusters in those groups: 451
- Specificity-rejected articles in canonical clusters: 0

The collision count increased because unsafe broad clusters were split. The
451 extra clusters across 328 groups are unresolved review candidates: some are under-merges and
some are genuinely distinct failures in the same administrative unit and day.
They must not be bulk-merged by identity.

The spent audit's recurring-road multi-day merges are now split. The Chitwan
2021 and Baglung 2020 multi-failure aggregates are rejected. The remaining
Kavrepalanchok and Palpa multi-article groups contain only reports of their
respective same incidents after the incorrectly linked dates were removed.

## Verification

- Focused dedup/similarity/parser tests pass.
- Full pytest suite passes with two intentional skips.
- Event-specificity rerun is idempotent: `10203|4017|1344` before and after
  for total rows, retained rows, and roundup rows.
- SQLite snapshot and working database SHA-256:
  `184b362b87d56eb4a3e1f875a8f2452a40aed1b08ea524e5bc1a1c7737bb22f3`
- Final CSV SHA-256:
  `3fbf147d1f2708723e36b1de1033fcc04d6100996b10da69ecb95716a4eada55`

Snapshots:

- `data/snapshots/landslide_inventory_pre_dedup_linkage_repair_20260925.sqlite`
- `data/snapshots/landslide_inventory_post_dedup_linkage_repair_20260925.sqlite`

## Next gate

Build a prioritized review pack from the 328 current collision groups. Review
named-municipality groups with strong pair evidence first, keep blank-location
and casualty-conflict groups separate by default, and materialize only explicit
reviewed merges. Then rebuild a versioned candidate and draw a fresh independent
probability audit under the unchanged promotion rule.
