# Canonical event pipeline fixes result

**Status:** complete as of 2026-09-16.

Recurring event-type, hazard-type, and death-count failures found by the
canonical-event audit have been converted into parser rules and regression
tests. These changes improve future pipeline runs; they do not replace the
validated manual correction plans for the frozen release.

## Death-count replay

The current extractors reproduce 12 of the 17 reviewed death corrections from
the structured-attribute and true-value plans when run against each event's
representative article. This includes English toll and kinship constructions,
Nepali kinship compounds and singular roles, explicit safe/rescued statements,
and an uncertainty veto that preserves `not_reported` rather than writing a
false zero.

Five rows remain intentionally plan-driven:

- `CEC-008`: the representative article reports missing people; a later cluster
  member confirms four deaths.
- `CEC-034`: the representative article carries an unconfirmed toll of 12; a
  later cluster member confirms 11.
- `CEC-005`: zero deaths is a human inference from property and livestock loss,
  not an explicit no-human-loss statement.
- `CEC-112`: the only occupant is reported injured and treated, but the article
  does not explicitly state zero deaths.
- `CEC-076`: the no-human-loss statement is season-wide, so the roundup guard
  correctly prevents automatic assignment to one focal event.

The release assembler must therefore apply the validated correction plans after
pipeline-derived values. It must not infer zero from silence, use the maximum
casualty count across cluster members, or weaken roundup-scope safeguards.

## Verification

- Focused casualty and extraction tests: 122 passed.
- Fatal-error Ruff checks: passed.
- Full suite: 1,031 passed and 2 existing tests skipped (1,033 collected).
