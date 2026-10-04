# Dedup collision adjudication pass 1

Date: 2026-09-27

## Scope

This pass applies the first 50-row current-state collision review without
modifying the original human submission. The original file remains:

`data/outputs/dedup_collision_review_BATCH_01_COMPLETED.csv`

The resolved copy is:

`data/outputs/dedup_collision_review_BATCH_01_ADJUDICATED.csv`

It contains 45 `merge` decisions, five `keep_distinct` decisions, no `unclear`
rows, and no survivor conflicts. The 45 reviewed edges form 40 transitive
components containing 84 old canonical events and imply 44 cluster
reductions.

## Pipeline changes

- Reviewed article corrections now support district, province, and
  municipality fields in addition to dates and exclusions.
- `corrections/dedup_merge_overrides.csv` stores reviewed merge components
  using representative article URLs, district, and date as stable anchors.
- Dedup fails closed if an anchor is missing or ambiguous.
- A reviewed survivor cluster ID is retained even when merged place evidence
  changes the automatically computed identity base.
- The component-level validator accepts one survivor from anywhere in the
  transitive component and rejects a survivor outside it.

## Structural adjudications

- The Kushma-11 road failure was corrected from Baglung to Parbat; the two
  remaining Ringlang/Bungadobhan fatality reports were merged.
- The bodyless 2015 Sindhupalchok Republica pair remains distinct from the
  Hagam/Yanglakot cluster because physical identity cannot be established.
- Three June 2022 Chitwan articles combining Namsi Bridge and Nagdi Khola were
  excluded pending multi-location decomposition.
- Three June 2024 Chitwan risk-survey articles were excluded because they do
  not report an observed dated failure.
- The seven-household Lower Tenchong report was merged into the later
  28-household Silichong update because the latter explicitly contains the
  same households.
- Four September 2022 Chitwan reports combining Kerabari and 18 Kilo were
  excluded pending multi-location decomposition.
- Three Hupsekot records were corrected from Parasi to Nawalpur, and two
  follow-up reports were corrected to the established 2021-08-27 event date.

## Result

- Canonical events: 2,656 before, 2,605 after (net -51).
- Reviewed article corrections applied: 21 total.
- Reviewed merge components applied: 40/40.
- Reviewed override components resolving to one final cluster: 40/40.
- Reviewed excluded articles still clustered: 0.
- Duplicate event IDs: 0.
- Orphan canonical rows: 0.
- Orphan clustered articles: 0.
- Cluster spans over one day: 0.
- Full pytest suite: passed, with two intentional skips.

The remaining 405 identity-collision extras are candidates, not asserted
errors. This pass resolves the prioritized first batch only; another ranked
batch can be reviewed if further dedup recall is required.

## Reproducibility

- Pre-pass snapshot:
  `data/snapshots/landslide_inventory_pre_collision_adjudication_20260927.sqlite`
  (`184b362b87d56eb4a3e1f875a8f2452a40aed1b08ea524e5bc1a1c7737bb22f3`)
- Post-pass snapshot:
  `data/snapshots/landslide_inventory_post_collision_adjudication_20260927.sqlite`
  (`aed9e133ee511382f19ea7304168c3a3d7d2e59efb54cdcbc5047ec2117a198d`)
- Final CSV:
  `data/outputs/canonical_events_final.csv`
  (`68f2efd27a2c929c0df879974afcde14560ecbd6edf2ce389cc03a18f0857c8a`)
- Article corrections:
  `corrections/article_corrections.csv`
  (`80be07a28b37260608dee6e883a5d81b27186ddc151302b8c66c14fcf891a4d9`)
- Merge overrides:
  `corrections/dedup_merge_overrides.csv`
  (`cad6276067e7cff3bc749be68af1a8f36d9a1c579b6917fb1ec1cefe4ddf61b8`)
- Application verification:
  `data/outputs/dedup_collision_review_BATCH_01_application.json`

## Scientific status

This is the corrected mutable working inventory, not a promoted paper release.
Any precision or accuracy claim for an earlier frozen release remains tied to
that release. A new locked validation sample is required before reporting
performance for this 2,605-event state.
