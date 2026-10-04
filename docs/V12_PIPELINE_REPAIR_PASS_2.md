# v1.2 pipeline repair: pass 2

Date: 2026-09-28

## Status

This pass is diagnostic only. It does not promote or modify v1.1. The v1.1
validation sample is spent and is used here only to diagnose repairs; it is not
an independent estimate of v1.2 performance.

The isolated rebuild completed from `extract` through `export_final`. Its
manifest is `data/outputs/v12_pipeline_diagnostic/diagnostic_manifest.json`.

## Repairs implemented

- Added conservative sentence-level multi-event evidence for counted failures,
  coordinated failure sites, second-event transitions, distributed failures,
  multi-site response summaries, and multi-road obstruction reports.
- Preserved direct single-event headlines when later prose only gives generic
  district context, and preserved fresh/again reports as one new occurrence.
- Distinguished municipal borders and road destinations from multiple event
  sites, preventing false multi-event classifications.
- Preferred an event-linked `today morning/afternoon/night` occurrence over an
  older explicit date in a background sentence.
- Restricted casualties for fresh/again reports to the new event sentence, so
  older incidents in the body cannot donate fatalities to the current event.

## Diagnostic result

- Pass-1 rebuilt canonical events: 2,201.
- Pass-2 rebuilt canonical events: 2,121.
- Event types: 1,345 landslide and 776 road obstruction.
- Hazards: 1,921 landslide, 163 debris flow, and 37 rockfall.
- Article roles: 2,001 first report, 119 follow-up, and 1 retrospective.
- Same-identity collision candidates: 321; these remain disambiguated rather
  than automatically merged.
- Canonical export SHA-256:
  `961f027df3df4496903b85dd0895adae4995ff72b3df4667bcd9ce0a800afa5b`.

## Spent-audit replay

The article-level classifier identifies 32 of 35 known non-single rows while
keeping all 99 confirmed single rows as single (97.8% binary granularity
accuracy on this development-only replay).

The final rebuilt export removes or reconstructs all 35 known non-single
canonical claims:

- 32 representative URLs are absent from the rebuilt canonical export.
- The Panchthar row `V11F-049` is reconstructed as one article with one missing
  person; the unrelated same-day reports are no longer merged into it.
- The renewed Lamjung report in `V11F-052` is dated 2024-06-23 and forms a
  separate two-article event from the 2024-06-18 event.
- The fresh Kalikhola event in `V11F-107` remains dated 2017-06-25 but no longer
  inherits two deaths from the older police-vehicle incident.

Six of 99 confirmed single rows are absent. This is not caused by the new
granularity classifier:

- Five have no defensible event date after publication-date fallback was
  removed from follow-up reports: `V11F-016`, `V11F-035`, `V11F-075`,
  `V11F-078`, and `V11F-140`.
- `V11F-127` remains a reopening/follow-up story with an unresolved Kathmandu
  dateline versus road-site location.

## Decision

Pass 2 resolves the known multi-event blocker without a known single-event
classification regression. Do not release or draw the final validation sample
yet. The next pass should recover dated, located single events without restoring
publication-date or dateline shortcuts.

## Next pass

1. Recover explicit historical dates for the five confirmed single follow-up
   rows with missing dates, using event-linked sentences only.
2. Resolve the event site for `V11F-127` and analogous road follow-ups while
   preserving the zero-regression district constraint.
3. Reconcile the rebuilt pipeline with validated v1.1 manual identity and
   attribute corrections.
4. Freeze a v1.2 candidate and draw a new untouched probability sample that
   excludes every previously reviewed event ID and article URL.
