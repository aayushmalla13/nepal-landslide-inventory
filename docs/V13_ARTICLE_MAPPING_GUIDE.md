# v1.3 article-mapping review guide

## Files

Open these side by side:

1. `data/outputs/v13_article_mapping_DECISIONS.csv`
2. `data/outputs/v13_article_membership_MAP.csv`

The decision sheet has 22 rows, one per audited canonical event requiring an
identity or article-membership decision. The membership map contains the full
source text and stable IDs such as `V13R-001-A01`.

Do not edit the membership map. In the decision sheet, fill only:

- `final_resolution`
- `final_event_count`
- `final_event_groups_json`
- `excluded_article_mapping_ids_json`
- `reviewed_by`
- `review_notes`

Do not reorder rows or change any other column.

## Main question

For each decision row, determine which physical landslide events are supported
by its mapped source articles. The audit note and proposed resolution are hints,
not answer keys.

## Resolution choices

- `exclude_cluster`: no valid observed landslide or road-obstruction event remains.
- `keep_cluster`: all retained articles describe one physical event.
- `decompose_source_article`: one article describes two or more physical events.
- `recluster_articles`: different articles currently grouped together describe different events.
- `recluster_and_decompose`: both decomposition and reclustering are required.
- `unclear`: the evidence cannot support a safe decision.

## Exclude a cluster

Use this for non-events, forecasts, risk-only stories, or reports too aggregate
to support an individual dated event. List every mapping ID for that row in the
excluded list.

```text
final_resolution: exclude_cluster
final_event_count: 0
final_event_groups_json: []
excluded_article_mapping_ids_json: ["V13R-001-A01"]
reviewed_by: aayush
review_notes: No observed dated surface landslide is documented.
```

## Keep one event

```text
final_resolution: keep_cluster
final_event_count: 1
final_event_groups_json: [{"group_id":"G1","article_mapping_ids":["V13R-010-A01"],"event_date":"2024-07-01","district":"Kaski","municipality":"","event_type":"landslide","hazard_type":"landslide","deaths":"not_reported","evidence":"The article documents one dated failure."}]
excluded_article_mapping_ids_json: []
reviewed_by: aayush
review_notes: One event with a consistent date and site.
```

## Split into multiple events

Create one JSON object per physical event. A mapping ID may appear in more than
one group only when that article explicitly supports multiple failures.

Every group must contain:

- `group_id`
- `article_mapping_ids`
- `event_date` in `YYYY-MM-DD`
- canonical `district`
- `municipality`, or `""` when unsupported
- `event_type`: `landslide`, `road_obstruction`, or `other`
- `hazard_type`: `landslide`, `debris_flow`, `rockfall`, or `other`
- `deaths`: an integer string, `not_reported`, or `unclear`
- a short source-supported `evidence` statement

Every mapping ID must appear in at least one retained group or in
`excluded_article_mapping_ids_json`, but never both.

## Unclear

Use `unclear` when the sources cannot support safe event definitions. Leave the
event count and both JSON decision fields blank, set `reviewed_by`, and explain
what the evidence cannot establish in `review_notes`.

## Save

Save the completed UTF-8 file as:

`data/outputs/v13_article_mapping_DECISIONS_COMPLETED.csv`

I will run the validator after you finish. Do not edit or rename the membership
map, blank decision template, or manifest.
