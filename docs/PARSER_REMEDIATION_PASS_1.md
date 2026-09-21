# Parser remediation pass 1

## Scope

This pass converts recurring post-correction audit findings into general parser
rules. It targets false events and aggregate or multi-event articles before
deduplication. It does not apply any row-level correction plan or modify a
release.

The changes add conservative detection for:

- preparedness plans and planned construction or road closures
- unrelated primary incidents with later landslide context
- foreign hazards incorrectly located at a Nepal victim home district
- Nepali multi-month disaster totals
- institutional visits and response reports
- explicit recurring, counted, or multi-location landslides in article titles

Protective tests retain genuine single road failures, landslide-caused vehicle
crashes, and Nepal landslides involving foreign nationals.

## Development diagnostic

The 66 unique representative URLs in the frozen remediation queue marked
`exclude_false_event` or `split_or_exclude_aggregate` were replayed through
`decide_specificity`. Before this pass, 19 were rejected and 47 remained
eligible. After this pass, 31 are rejected and 35 remain eligible.

This 12-row improvement is a targeted development-set diagnostic, not an
inventory precision estimate. The URLs were selected because reviewers had
already found errors. They must not be reported as an independent validation
sample or pooled with the locked audit.

## Remaining work

The 35 retained audit failures are dominated by location-role errors, road
corridor reports with several named failure sites, recurring failures with
ambiguous dates, and clusters requiring article-level decomposition. Those
cases should be addressed through location and multi-event parsing rather than
broader context keywords.

A new release still requires both remaining manual attribute gates, assembly
from the unapplied plans, and a fresh locked probability sample excluding all
previously reviewed events and evidence.
