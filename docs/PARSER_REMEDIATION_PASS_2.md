# Parser remediation pass 2

## Scope

This pass addresses multi-failure road and corridor articles that still looked
like one event after parser remediation pass 1. It does not modify the frozen
release or apply any row-level correction plan.

The classifier now treats the following as strong multi-event evidence:

- counted or demonstrably plural roads in a headline
- explicitly separate landslide incidents
- two named landslide sites in one road-obstruction headline
- plural landslides that block, obstruct, halt, or disrupt transport
- a road article lead that places landslides at several or counted sites

The lead rule is limited to the first 400 characters and requires a landslide
term near the multiple-site phrase. Generic municipality lists, destinations,
and later contextual mentions do not trigger it. Whole-body multiplicity
scanning remains disabled.

## Validation

The focused event-typing and specificity tests pass, as does the complete test
suite (1,096 tests, with two expected skips). Ruff's undefined-name/import
checks and `git diff --check` also pass.

On the human-labelled class-1 development pack, the new signals increase
weighted granularity accuracy from 0.637 to 0.652. Every sampled article newly
classified as multi is labelled multi; no sampled single-event article flips.
This is development evidence, not an independent performance estimate.

## Development diagnostic

The same 66 representative URLs used in pass 1 were replayed from the database
through `decide_specificity`. Rejections increase from 31 to 41, leaving 25
known false or aggregate audit articles retained. Ten additional articles are
correctly rejected as multi-event.

The 66 URLs were selected because reviewers had already found errors. These
counts must not be reported as inventory precision and must not be pooled with
the locked validation audit.

## Remaining work

The remaining 25 retained development failures are dominated by location-role,
event-date, recurrence, and article-cluster decomposition errors. The next pass
should correct only genuine single-event location/date extraction and leave
multi-event cluster reconstruction to the unapplied identity plan.
