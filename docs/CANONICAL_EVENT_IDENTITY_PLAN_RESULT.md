# Canonical event identity plan result

## Outcome

The final collision review is complete and valid. All 99 date-resolved
reconstruction candidates received a decision, with no unresolved rows.

- New physical events: 85
- Candidates merged into existing frozen events: 12
- Candidates excluded during collision review: 2
- Candidate excluded during date review: 1
- Superseded old canonical events removed: 55
- Provisional inventory rows after identity changes: 2,915
- Net identity-layer change from frozen v0.6.0: +30

Each merge targets a different existing frozen event. No reconstructed candidate
appears in both the new-event and merge tables.

## Unapplied plan files

- `data/outputs/canonical_event_identity_plan_REMOVE_OLD_EVENTS.csv`
- `data/outputs/canonical_event_identity_plan_NEW_EVENTS.csv`
- `data/outputs/canonical_event_identity_plan_MERGES.csv`
- `data/outputs/canonical_event_identity_plan_EXCLUDED_CANDIDATES.csv`
- `data/outputs/canonical_event_identity_plan_manifest.json`

## Remaining gates

The identity plan must not be applied yet. The independent audit also identified
date/location corrections and structured event-type, hazard, and casualty
corrections in records outside this identity batch. Those correction gates must
be resolved and reconciled with the identity plan before building a new release.

After all correction layers are complete, the project must generate stable
production event IDs, rebuild canonical outputs and the SQLite snapshot, rerun
rainfall linkage, and validate the new release with a fresh locked sample.
