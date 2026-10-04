# v1.5 Article-Mapping Review

Open these files side by side:

- `data/outputs/v15_article_mapping_DECISIONS.csv`
- `data/outputs/v15_article_membership_MAP.csv`

The decision sheet contains 46 findings from the spent v1.4 probability audit.
Use each `queue_id` to locate all corresponding articles in the membership map.
Read the audit note and full article evidence, then decide how many distinct
physical landslide events are actually represented.

Fill only:

- `final_resolution`
- `final_event_count`
- `final_event_groups_json`
- `excluded_article_mapping_ids_json`
- `reviewed_by`
- `review_notes`

Allowed resolutions are `exclude_cluster`, `keep_cluster`,
`decompose_source_article`, `recluster_articles`,
`recluster_and_decompose`, and `unclear`.

For exclusions, use event count `0`, groups `[]`, and list every excluded
mapping ID. For retained or decomposed events, provide one JSON group per
physical event using the exact mapping IDs and evidence-supported date,
district, municipality, event type, hazard type, and deaths. If an exact date
or single canonical district cannot be established, use `unclear` rather than
inventing a value. A mapping ID must appear in exactly one retained group or in
the exclusion list.

Set `reviewed_by` to `aayush`. Do not change row order, IDs, claims, evidence,
or the membership map. Save as:

`data/outputs/v15_article_mapping_DECISIONS_COMPLETED.csv`
