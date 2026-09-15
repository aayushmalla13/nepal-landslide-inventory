# Canonical event-level audit guide

## Purpose

This is a new, blind evaluation of the frozen 2,885-event inventory release
`nepal_landslide_inventory_v0.6.0_v7_20260915`. It measures whether final
canonical records represent real, single physical landslide-family events and
whether their core fields are correct. It does not tune the extractor and does
not modify the frozen release.

The 150 rows are sampled reproducibly across title language, three periods,
event type, and single- versus multi-article cluster support. Population weights
correct for the unequal sampling fractions.

## Files to use

Open these beside each other:

- `data/outputs/canonical_event_audit_LABEL_HERE.csv`
- `data/outputs/canonical_event_audit_reading_pack.csv`

Do not edit or reorder the claim columns. Do not use pipeline confidence,
specificity, or location-consistency outputs while labelling. They were omitted
to reduce anchoring.

Save the completed label sheet as:

`data/outputs/canonical_event_audit_COMPLETED.csv`

## Labels

For every row, fill `event_really_happened` with `yes`, `no`, or `unclear`.

If it is `yes`, also fill:

- `one_physical_event`: whether the record represents one specific physical event.
- `district_correct`: whether the claimed event district is correct.
- `date_correct`: whether the claimed event date is correct.
- `municipality_correct`: required only when a municipality is claimed.
- `event_type_true`: `landslide`, `road_obstruction`, `other`, or `unclear`.
- `hazard_type_true`: `landslide`, `debris_flow`, `rockfall`, `other`, or `unclear`.
- `deaths_true`: an integer, `not_reported`, or `unclear`.
- `duplicate_merge_correct`: for clusters with more than one article, `yes`,
  `no`, or `unclear`; use `not_applicable` for one-article clusters.
- `annotator`: a stable reviewer name or initials.
- `notes`: short evidence or the reason for uncertainty.

When `event_really_happened` is `no` or `unclear`, leave conditional fields
blank and still fill `annotator` and `notes` where useful.

## Decision rules

Use `no` for event existence when the article is only a warning, forecast,
historical overview, metaphor, foreign event, victim-origin reference, traffic
destination, office/dateline reference, or an unrelated hazard.

Use `one_physical_event = no` for a roundup or aggregate record that combines
several distinct failures. Several articles about the same failure still count
as one physical event.

Judge the event date, not merely the publication date. A follow-up article can
support the correct earlier event date. For district and municipality, judge
where the failure occurred, not where victims lived or were transported.

For `duplicate_merge_correct`, read every article section in the reading pack.
Use `no` if the cluster has merged articles about different physical events.

## Score after completion

```bash
PYTHONPATH=src .venv/bin/python scripts/score_canonical_event_audit.py
```

The scorer validates row order and immutable claims against the manifest, then
writes:

- `data/outputs/canonical_event_audit_score.json`
- `data/outputs/canonical_event_audit_report.md`

The primary outputs are population-weighted event-existence precision and
usable-record precision. District, date, municipality, event type, hazard type,
deaths, and duplicate-merge accuracy are reported separately. Unclear labels
are excluded from point estimates but always reported, and confidence intervals
come from a stratified bootstrap.
