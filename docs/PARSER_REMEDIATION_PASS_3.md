# Parser remediation pass 3

## Scope

This pass corrects a recurring location-evidence ordering error in road reports.
The extractor previously preferred a Kathmandu desk dateline or route endpoint
over a municipality written beside the physical road failure.

The retained rule requires all of the following:

- an explicit landslide road-obstruction headline
- a municipality beside failure or obstruction language
- no person-home or route-destination attribution
- one unanimous mapped event district
- an existing Kathmandu assignment

The English equivalent is additionally limited to a Kathmandu dateline and a
single normalized municipality mention in direct road-failure context.

## Audited corrections

Fresh article extraction now resolves:

- PCR-002 from Kathmandu to Nawalpur, using Binayee Rural Municipality
- PCR-008 from Kathmandu to Makwanpur, using the unanimous Bhimphedi and
  Indrasarowar evidence

The mixed Lamjung-Manang report is not overridden because its event-context
municipalities map to different districts. The Bhaktapur road-office and
Eastern Rukum route-destination cases remain in the explicit correction plan;
they are not generalized from two development examples.

## Safety audit

A broad event-municipality override was tested first and rejected. It changed
309 corpus rows and followed unrelated municipalities in casualty, relief,
risk, and national-roundup articles. Restricting it only to road headlines
still proposed 94 changes, including clear corridor and multi-report errors.

The retained Nepali rule proposes 17 changes, all from Kathmandu to a unanimous
municipality-derived road-failure district. The English dry replay changes five
rows; the one nationwide report is independently rejected as multi-event by
the specificity stage.

These are development diagnostics, not independent accuracy estimates. No
database row or frozen release was modified.

## Validation

The focused English, Nepali, extraction-stage, and location-consistency tests
pass. The complete suite passes all 1,100 collected tests with two expected
skips. Ruff's import/name checks and `git diff --check` pass.

## Decision

Further broad parser expansion is not justified from the remaining reviewed
cases. Most are cluster decomposition, recurrence, retrospective response, or
row-specific chronology problems already represented in the unapplied identity
and correction plans. The next stage is to complete the 45-row true-value and
25-row structured-attribute gates, then assemble a new candidate.
