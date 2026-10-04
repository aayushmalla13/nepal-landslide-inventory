# v0.9 article-mapping review guide

## Purpose

This is the first correction gate for the failed v0.8 validation. It resolves
false events, aggregate source articles, and incorrect multi-article clusters
before any date, location, or structured-attribute correction is applied.

## Files

Keep these side by side:

- `data/outputs/v09_article_mapping_DECISIONS.csv`
- `data/outputs/v09_article_membership_MAP.csv`

The decision sheet has one row per canonical event. The membership map contains
one row per source article with full text and a stable `mapping_id`.

Do not change frozen columns or row order. Fill only:

- `final_resolution`
- `final_event_count`
- `final_event_groups_json`
- `excluded_article_mapping_ids_json`
- `reviewed_by`
- `review_notes`

## Resolution choices

- `exclude_cluster`: no valid landslide or road-obstruction event remains.
- `keep_cluster`: all retained articles describe one physical event.
- `decompose_source_article`: one article describes multiple physical events.
- `recluster_articles`: existing articles belong to different events.
- `recluster_and_decompose`: both conditions apply.
- `unclear`: evidence cannot support a safe decision.

For `exclude_cluster`, use event count `0`, groups `[]`, and list every mapping
ID in `excluded_article_mapping_ids_json`.

For retained events, `final_event_groups_json` must contain one object per
physical event with these fields:

```json
[
  {
    "group_id": "G1",
    "article_mapping_ids": ["V9R-001-A01"],
    "event_date": "2024-07-01",
    "district": "Kaski",
    "municipality": "",
    "event_type": "landslide",
    "hazard_type": "landslide",
    "deaths": "not_reported",
    "evidence": "Short source-supported explanation"
  }
]
```

Every mapping ID must appear in at least one retained group or in the excluded
list. A single source article may support multiple groups when it reports
multiple physical events.

Save the completed sheet as
`data/outputs/v09_article_mapping_DECISIONS_COMPLETED.csv`. The validator is:

```bash
PYTHONPATH=src .venv/bin/python scripts/validate_v09_article_mapping.py
```
