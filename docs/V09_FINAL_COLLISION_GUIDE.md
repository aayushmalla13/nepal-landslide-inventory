# v0.9 final candidate-collision guide

## Purpose

This is the last identity gate. It checks the 26 surviving proposed new events
against one another after existing-event merges, exclusions, and blocked
old-event bundles have been accounted for.

## Files

Use these together:

- `data/outputs/v09_reconstruction_FINAL_COLLISION_DECISIONS.csv`
- `data/outputs/v09_reconstruction_FINAL_COLLISION_PAIRS.csv`

The screen contains no high-tier matches. Sixteen candidates have medium-tier
matches, usually because separate physical locations were decomposed from one
source article on the same district-date. Four have only low-tier matches and
six have no candidate pair.

Fill only:

- `final_candidate_action`
- `merge_candidate_event_id`
- `reviewed_by_final`
- `final_collision_notes`

## Actions

- `new_event`: retain this candidate as a distinct physical event.
- `merge_candidate`: merge it into one listed candidate; provide that ID.
- `exclude_duplicate`: exclude it as a duplicate of one listed candidate;
  provide the retained candidate ID.
- `unclear`: identity cannot be resolved safely.

Merge or exclusion targets must be listed in `candidate_matches_json`, must be
retained as `new_event`, and require explanatory notes. Same-source URL overlap
is expected after decomposing a multi-event article and is not by itself a
reason to merge physically distinct named locations.

Save the completed file as
`data/outputs/v09_reconstruction_FINAL_COLLISION_DECISIONS_COMPLETED.csv`, then
run:

```bash
PYTHONPATH=src .venv/bin/python scripts/validate_v09_final_collisions.py
```
