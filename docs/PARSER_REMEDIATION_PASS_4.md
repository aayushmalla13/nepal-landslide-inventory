# Parser remediation pass 4

Generated: 2026-09-24

## Purpose

This pass used the spent v0.9 final audit only as development evidence. It does
not provide a new precision estimate and does not change the v0.9 release
decision.

## Repairs

- Added general exclusions for Nepali preparedness and response plans,
  parliamentary generalities, weather forecasts, political metaphor, long-
  period disaster statistics, protest and maintenance coverage, explanatory
  features, multi-hazard aggregates, and primary tornado coverage.
- Fixed Nepali Kathmandu-dateline handling. A single non-dateline body district
  may replace Kathmandu; multiple body districts leave the event unresolved
  instead of inventing a location.
- Made `event_specificity` and `filter_scope` non-destructive. They now retain
  extracted date, place, casualty, and trigger evidence when downgrading a row.
- Added a canonical eligibility invariant: dedup accepts class 1 or 2 only when
  `specificity_ok = 1`. This preserves approved low-confidence road and follow-
  up reports while preventing rejected class-2 roundups from re-entering the
  inventory.
- Added regression tests for all new semantic families, Kathmandu datelines,
  filter-stage idempotency, evidence preservation, and dedup eligibility.

## Rebuild result

The complete working pipeline was rerun in this order:

`extract -> event_specificity -> location_consistency -> filter_scope -> corrections -> dedup -> event_typing -> export_final -> inventory_audit`

- Raw/article rows: 10,203
- Specificity retained: 4,058
- Specificity rejected: 6,145
- Canonical events: 2,219
- Unique canonical event IDs: 2,219
- Articles admitted to clusters: 3,574
- Approved class-2 articles admitted: 538
- Specificity-rejected articles admitted: 0
- Same-identity cluster collisions reported by dedup: 296

Both `event_specificity` and `filter_scope` were run twice. Their first- and
second-pass corpus digests matched exactly. The complete pytest suite passed
with two intentional skips.

## Development replay

Against the 150-row spent v0.9 final audit:

- Confirmed false-event representatives rejected: 26/26
- Confirmed false-event representatives entering a cluster: 0/26
- Confirmed-event representatives retained and clustered: 109/124
- Confirmed-event representatives rejected: 15/124

The 15 rejected true representatives are not all simple false negatives. Nine
were labelled as multi-event or otherwise non-single records, three of the six
single-event records had a wrong claimed date, and one had a wrong claimed
district. They are a development queue for temporal-role correction and safe
decomposition, not evidence for weakening the canonical gate.

## Reproducibility

- Pre-repair database snapshot:
  `data/snapshots/landslide_inventory_pre_parser_repair_20260924.sqlite`
- Post-repair database snapshot:
  `data/snapshots/landslide_inventory_post_parser_repair_20260924.sqlite`
- Post-repair database SHA-256:
  `bc08c0b0414955585f16e9ae83da1790e7249a1e332af59df446febe5b777997`
- Working canonical CSV SHA-256:
  `6675877dc1def15b15d1c42a4ec546f6060b3c75de55ae068e3997a8a64f9239`

## Decision

Do not promote this working rebuild. The next repair target is dedup and
identity resolution: inspect the 296 same-identity cluster collisions and the
spent audit's duplicate-merge failures, then rerun the pipeline and draw a new
independent probability audit. The automated secondary-event extractor remains
unwired because its locked precision gate failed; see
`docs/SECONDARY_PRECISION_RESULT.md`.
