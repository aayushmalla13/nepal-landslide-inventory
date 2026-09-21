# Post-correction article-mapping guide

## Purpose

This review resolves the 67 identity and article-membership findings before any
date, location, event-type, hazard, or casualty correction is applied. The pack
is tied to the frozen v0.7 candidate and contains 85 source-article memberships.

No candidate or production record has been changed.

## Open these files together

1. `data/outputs/post_correction_article_mapping_DECISIONS.csv`
2. `data/outputs/post_correction_article_membership_MAP.csv`

The decision sheet has one row per affected canonical event. The membership map
has one row per source article, extraction metadata, audit notes, and full text.
Use `queue_id` and `mapping_id` to connect the files.

## Fill only these decision columns

- `final_resolution`
- `final_event_count`
- `final_event_groups_json`
- `excluded_article_mapping_ids_json`
- `reviewed_by`
- `review_notes`

Do not edit any other column or change row order.

Allowed `final_resolution` values are `exclude_cluster`, `keep_cluster`,
`decompose_source_article`, `recluster_articles`,
`recluster_and_decompose`, and `unclear`.

## Event-group JSON

Each retained physical event needs one object:

```json
{
  "group_id": "A",
  "article_mapping_ids": ["PCR-001-A01"],
  "event_date": "2025-08-31",
  "district": "Chitwan",
  "municipality": "",
  "event_type": "road_obstruction",
  "hazard_type": "landslide",
  "deaths": "not_reported",
  "evidence": "Kerabari slide blocked the road on August 31."
}
```

Use `unclear` for an unknown value rather than inventing one. An article can
support multiple event groups when it explicitly reports several separable
physical failures.

## Decision rules

1. Use `exclude_cluster` when no specific physical Nepal landslide event is
   supported or an aggregate cannot be decomposed safely. Set event count to
   `0`, groups to `[]`, and list every mapping ID as excluded.
2. Use `keep_cluster` when the current articles support one physical event.
3. Use `decompose_source_article` when one article supports multiple distinct
   events with separable locations or dates.
4. Use `recluster_articles` when different articles support distinct events.
5. Use `recluster_and_decompose` when both conditions apply.
6. Use `unclear` only when the evidence cannot support a defensible identity
   decision. Leave event count and event groups blank and explain why.
7. Every mapping ID must appear in at least one retained group or in the
   excluded-ID list. It cannot appear in both.
8. Do not treat several place names as separate events when they describe one
   continuous failure area.

For retained decisions, `final_event_count` must equal the number of group
objects. Use `[]` when no article is excluded.

## Save and validate

Save the completed decision sheet as:

`data/outputs/post_correction_article_mapping_DECISIONS_COMPLETED.csv`

Then run:

```bash
PYTHONPATH=src .venv/bin/python scripts/validate_post_correction_article_mapping.py
```

The validator rejects modified frozen fields, invalid JSON, unknown or missing
mapping IDs, inconsistent event counts, and missing reviewer provenance.
