# v1.2 pipeline repair: pass 3

Date: 2026-09-29

## Status

This pass is diagnostic only. It does not promote or modify v1.1. The v1.1
validation sample is spent and is used only to diagnose repairs; it is not an
independent estimate of v1.2 performance.

The isolated rebuild completed from `extract` through `export_final`. Its
manifest is `data/outputs/v12_pipeline_diagnostic/diagnostic_manifest.json`.

## Repairs implemented

- Recovered historical dates from event-linked sentences in follow-up reports
  instead of accepting publisher datelines as event dates.
- Recognized Nepali reverse-grammar occurrence clauses such as `गएको पहिरो`
  and `खसेको पहिरो`, including `गत <weekday>` when publication falls on the
  same weekday.
- Recovered English historical dates beyond scraped navigation boilerplate
  when the date occurs in the same sentence as an explicit landslide action.
- Added an exact event-site mapping for Charchare in Tinau-5, Palpa, without
  treating road endpoints or Kathmandu filing datelines as event locations.
- Rejected inferred event dates after publication. A future anchor is reduced
  to the existing low-confidence publication fallback, which follow-up and
  retrospective reports cannot use.

## Targeted audit recovery

All six confirmed-single rows missing after pass 2 now survive the complete
pipeline as canonical events:

| Audit row | Event date | District | Municipality |
| --- | --- | --- | --- |
| V11F-016 | 2024-08-24 | Ramechhap | Doramba Rural Municipality |
| V11F-035 | 2024-06-29 | Gulmi | |
| V11F-075 | 2023-06-16 | Taplejung | Sidingba Rural Municipality |
| V11F-078 | 2024-09-28 | Dhading | Dhunibesi Municipality |
| V11F-127 | 2023-05-05 | Palpa | |
| V11F-140 | 2020-08-14 | Sindhupalchok | Jugal Rural Municipality |

## Diagnostic result

- Pass-2 rebuilt canonical events: 2,121.
- Pass-3 reconciled canonical events: 2,160.
- Event types: 1,358 landslide and 802 road obstruction.
- Hazards: 1,957 landslide, 166 debris flow, and 37 rockfall.
- Article roles: 1,997 first report, 162 follow-up, and 1 retrospective.
- Same-identity collision candidates: 338; these remain disambiguated rather
  than automatically merged.
- Extracted article events later than publication: 0.
- Canonical export SHA-256:
  `0c077fab7290b3fbc3f9a74dacb3adfa827e19466433221b4424b4cd75162643`.

The increase of 39 canonical events is broader analogous recovery from the
same evidence-bound rules. It is not a held-out performance estimate and must
be covered by the fresh v1.2 validation draw.

## Verification

- Focused English and Nepali extraction tests passed.
- The complete test suite passed with two intentional skips. The only warnings
  were the known inability to write `.pytest_cache` in the Box-synced folder.
- The spent v1.1 audit replay is unchanged: all 99 confirmed-single articles
  classify as single, and 32 of 35 known non-single articles classify as
  non-single. The remaining three are the pass-2 reconstruction cases
  V11F-049, V11F-052, and V11F-107 rather than new regressions.

## Decision

Pass 3 completes the targeted date and location repair. Do not release v1.2 or
claim validated performance yet. The next stage is to reconcile the rebuilt
pipeline with the reviewed v1.1 identity and attribute corrections, freeze a
candidate, and draw a new untouched probability sample excluding every
previously reviewed event ID and article URL.
