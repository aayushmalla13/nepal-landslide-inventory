# v1.2 pipeline repair: pass 1

Date: 2026-09-28

## Status

This pass is diagnostic only. It does not promote or modify v1.1.

The isolated rebuild completed from `extract` through `export_final` against a
copy of the 10,203-article database. Its manifest is:

`data/outputs/v12_pipeline_diagnostic/diagnostic_manifest.json`

## Repairs implemented

- Recomputed event typing globally with a classifier fingerprint and preserved
  explicit human event/hazard corrections.
- Expanded conservative multi-event detection using plural-failure headlines,
  explicit dozen/many-place language, and a longer lead window.
- Prevented follow-up and retrospective stories from inheriting publication
  dates unless an event-linked date anchor is present.
- Allowed event-anchored municipalities to override conflicting datelines,
  victim residences, and route labels when the mapped district is unambiguous.
- Made reviewed dedup overrides lifecycle-aware when upstream filtering removes
  some or all reviewed article anchors; ambiguous anchors still fail closed.

## Diagnostic result

- Current mutable pipeline: 2,605 canonical events.
- Repaired isolated rebuild: 2,201 canonical events.
- Repaired event types: 1,385 landslide and 816 road obstruction.
- Article roles: 2,079 first report, 121 follow-up, 1 retrospective.
- Same-identity collision candidates: 329; these remain disambiguated and are
  not automatically merged.

On the spent v1.1 validation sample, used only as development diagnostics:

- Known multi-event rows removed: 11 of 35.
- Known wrong-date rows removed or reassigned: 8 of 33.
- Known wrong-district rows removed or reassigned: 4 of 20.
- Valid single-event rows removed: 10 of 99.
- Valid-date rows removed: 6 of 86 at canonical-row level.
- Valid-district rows removed: 18 of 118 at canonical-row level, primarily
  because the whole row was filtered rather than because its district changed.
- No audit-confirmed correct district was reassigned by the new extractor.

The in-memory representative-article replay isolates extractor behavior from
cluster removal and showed:

- Granularity accuracy rose from about 74% to 79.1% on the fresh diagnostic
  sample and to 79.4% on the prior applicable development set.
- Date repair changed 9 of 33 known wrong dates while changing 2 of 86 known
  correct dates.
- District repair changed 5 of 20 known wrong districts while changing 0 of
  118 known correct districts.

## Decision

Do not release or validate this diagnostic build yet. Pass 1 establishes a
working global repair path and materially improves precision, but too many
known multi-event, date, and location failures remain.

## Next pass

1. Add sentence-level decomposition or exclusion for the 24 retained known
   multi-event articles, especially road bulletins and district summaries.
2. Add explicit historical-date extraction for aid, recovery, reopening, and
   reconstruction reports that still retain publication-derived dates.
3. Add event-site resolution for direct district phrases and municipality
   aliases missed in road corridors, while preserving the zero-regression
   district result.
4. Reconcile the rebuilt pipeline with the validated v1.1 manual identity and
   attribute corrections.
5. Draw a new untouched probability sample excluding all prior audit event IDs
   and URLs only after the rebuilt candidate passes deterministic checks.
