# v1.1 article-mapping review guide

## Files

Open these side by side:

1. `data/outputs/v11_article_mapping_DECISIONS.csv`
2. `data/outputs/v11_article_membership_MAP.csv`

The decision sheet has 36 rows, one per audited canonical event. The membership
map has 43 article rows with full text and stable IDs such as `V11R-001-A01`.

Do not edit the membership map. In the decision sheet, fill only:

- `final_resolution`
- `final_event_count`
- `final_event_groups_json`
- `excluded_article_mapping_ids_json`
- `reviewed_by`
- `review_notes`

Do not reorder rows or change any other column.

## Main question

For each decision row, determine what physical landslide events are actually
supported by its mapped source articles. The audit note and proposed resolution
are hints, not answer keys.

## Resolution choices

- `exclude_cluster`: no valid observed landslide or road-obstruction event
  remains.
- `keep_cluster`: all retained articles describe one physical event.
- `decompose_source_article`: an article describes two or more physical events.
- `recluster_articles`: different articles currently grouped together describe
  different events.
- `recluster_and_decompose`: both decomposition and reclustering are required.
- `unclear`: the evidence cannot support a safe decision.

## How to fill

### Exclude the whole cluster

Use this for forecasts, risk-only stories, preparedness, non-events, or reports
too aggregate to support any individual event.

```text
final_resolution: exclude_cluster
final_event_count: 0
final_event_groups_json: []
excluded_article_mapping_ids_json: ["V11R-005-A01"]
reviewed_by: aayush
review_notes: Risk assessment only; no observed dated failure.
```

List every mapping ID for that row in the excluded list.

### Keep one event

```text
final_resolution: keep_cluster
final_event_count: 1
final_event_groups_json: [{"group_id":"G1","article_mapping_ids":["V11R-010-A01","V11R-010-A02"],"event_date":"2024-07-01","district":"Kaski","municipality":"","event_type":"landslide","hazard_type":"landslide","deaths":"not_reported","evidence":"Both articles describe the same named failure."}]
excluded_article_mapping_ids_json: []
reviewed_by: aayush
review_notes: Same date, location and incident narrative.
```

### Split into multiple events

Create one JSON object per physical event and set `final_event_count` to the
number of objects. A single mapping ID may appear in multiple groups when one
article explicitly supports multiple physical failures.

```json
[
  {
    "group_id": "G1",
    "article_mapping_ids": ["V11R-001-A01", "V11R-001-A02"],
    "event_date": "2023-07-01",
    "district": "Parbat",
    "municipality": "Phalebas Municipality",
    "event_type": "landslide",
    "hazard_type": "landslide",
    "deaths": "not_reported",
    "evidence": "Initial school-damaging failure on Asar 16."
  },
  {
    "group_id": "G2",
    "article_mapping_ids": ["V11R-001-A01", "V11R-001-A03"],
    "event_date": "2023-08-07",
    "district": "Parbat",
    "municipality": "Phalebas Municipality",
    "event_type": "landslide",
    "hazard_type": "landslide",
    "deaths": "not_reported",
    "evidence": "Later renewed slide episode after Shrawan 22."
  }
]
```

The example shows formatting only; verify dates and facts from the article map.

For every group:

- use `YYYY-MM-DD` for `event_date`;
- use a canonical Nepal district name;
- leave `municipality` as `""` if unsupported;
- use `landslide`, `road_obstruction`, or `other` for `event_type`;
- use `landslide`, `debris_flow`, `rockfall`, or `other` for `hazard_type`;
- use an integer as a string, `not_reported`, or `unclear` for `deaths`; and
- write a short source-supported `evidence` explanation.

Every article mapping ID must appear in at least one retained event group or in
`excluded_article_mapping_ids_json`. It cannot be both retained and excluded.

### Unclear

```text
final_resolution: unclear
final_event_count: [blank]
final_event_groups_json: [blank]
excluded_article_mapping_ids_json: [blank]
reviewed_by: aayush
review_notes: Explain exactly what the sources do not establish.
```

## Save and validate

Save the completed UTF-8 file as:

`data/outputs/v11_article_mapping_DECISIONS_COMPLETED.csv`

Validation command:

```bash
PYTHONPATH=src .venv/bin/python scripts/validate_v11_article_mapping.py
```
