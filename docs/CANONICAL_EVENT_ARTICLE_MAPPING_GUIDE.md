# Canonical event article-mapping guide

## Why this review is required

The adjudicated audit establishes that these 55 canonical records have an event
identity or membership problem. It does not fully specify the corrected
physical events. In particular, an aggregate article may contain enough detail
to create several events, or it may be too vague and need exclusion.

No production record has been changed by the mapping pack.

## Files

Open these side by side:

1. `data/outputs/canonical_event_article_mapping_DECISIONS.csv`
2. `data/outputs/canonical_event_article_membership_MAP.csv`

The decision sheet has one row per affected canonical event. The membership map
has one row per frozen source-article membership and includes full article text.
The frozen v0.6 URL list is authoritative; working-database cluster membership
is deliberately not used.

## Decision fields

Fill these columns in the decision sheet:

- `final_resolution`: one of `exclude_cluster`, `keep_cluster`,
  `decompose_source_article`, `recluster_articles`,
  `recluster_and_decompose`, or `unclear`.
- `final_event_count`: `0` for exclusion; otherwise the number of distinct
  physical events supported by the evidence. Leave blank only for `unclear`.
- `final_event_groups_json`: a JSON list describing each retained physical
  event. Use `[]` for exclusion.
- `excluded_article_mapping_ids_json`: a JSON list of source mapping IDs that
  support no retained event. Use all source IDs for whole-cluster exclusion and
  `[]` when every article supports at least one retained group.
- `reviewed_by`: stable reviewer name or initials.
- `review_notes`: short rationale, especially when evidence is incomplete.

Each event-group object should use this shape:

```json
{
  "group_id": "A",
  "article_mapping_ids": ["CEC-003-A01"],
  "event_date": "2025-08-31",
  "district": "Chitwan",
  "municipality": "",
  "event_type": "road_obstruction",
  "hazard_type": "landslide",
  "deaths": "not_reported",
  "evidence": "Kerabari slide blocked the road on Aug 31."
}
```

An article may appear in multiple groups when one article reports several
well-specified physical events. Use `unclear` for an unknown field rather than
inventing a value.

## Decision rules

1. Use `exclude_cluster` when no specific physical Nepal landslide event is
   supported, or when an aggregate/historical article cannot be decomposed into
   event-specific records.
2. Use `decompose_source_article` when one article clearly supports two or more
   distinct events with separable dates or locations.
3. Use `recluster_articles` when the articles describe distinct events but no
   article itself needs decomposition.
4. Use `recluster_and_decompose` when both problems occur.
5. Do not retain a group without an evidence sentence and at least a district
   plus date or an explicit `unclear` marker.
6. Do not infer that multiple place names are automatically multiple events;
   they may describe one continuous failure area.
7. Every source mapping ID must appear in at least one event group or in the
   explicit excluded-ID list. An excluded ID cannot also support a retained
   group.

Save the reviewed decision sheet as:

`data/outputs/canonical_event_article_mapping_DECISIONS_COMPLETED.csv`

The next validator will reject altered frozen columns, invalid JSON, unknown
mapping IDs, duplicate group IDs, inconsistent event counts, or blank reviewer
provenance.
