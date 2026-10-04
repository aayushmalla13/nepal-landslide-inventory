# v0.8 fresh locked validation result

## Decision

**Retain candidate status. Do not promote v0.8.**

The blinded 150-row validation file passed all structural and lock checks and
was scored using the decision rule frozen before labels existed. Four of six
prespecified checks failed. This is a substantive data-quality result rather
than a file, scoring, or threshold-selection problem.

Candidate: `nepal_landslide_inventory_v0.8.0_candidate_20260923`

## Design

The stratified probability sample was drawn from a 2,096-event eligible frame.
It excluded 333 previously reviewed event IDs and 1,376 article URLs exposed in
earlier manual gates. The 150 sampled events contain 215 source articles, with
zero prior-review overlap and zero unavailable local articles. One reviewer,
`reviewer_v08_fresh`, completed all rows.

## Results

| Metric | Weighted estimate | 95% stratified-bootstrap CI |
|---|---:|---:|
| Event-existence precision | 0.889 | 0.837-0.937 |
| Strict usable-record precision | 0.463 | 0.381-0.545 |
| Single-event accuracy | 0.744 | 0.671-0.814 |
| District accuracy | 0.865 | 0.805-0.921 |
| Date accuracy | 0.792 | 0.714-0.862 |
| Municipality accuracy | 0.926 | 0.866-0.975 |
| Event-type accuracy | 0.685 | 0.609-0.762 |
| Hazard-type accuracy | 0.927 | 0.879-0.971 |
| Deaths exact accuracy | 0.855 | 0.793-0.911 |
| Duplicate-merge accuracy | 0.700 | 0.479-0.893 |

Event-existence uncertainty was 2%, within the prespecified maximum. District
accuracy passed its point and lower-bound thresholds. Event-existence, strict
usable-record, single-event, and date checks failed their frozen thresholds.

The unweighted labels contain 15 confirmed non-events among 150 rows. Among
132 confirmed events, 35 fail the one-physical-event test, 16 have an incorrect
district, and 24 have an incorrect date. These defects explain the low
usable-record estimate and cannot be treated as harmless attribute noise.

## Failure pattern

Residual errors are distributed across years, languages, and sources, but
several actionable patterns recur:

- Preparedness, political commentary, risk mapping, development reporting, and
  retrospective stories are still admitted as current events.
- Articles describing several landslides or a continuing slope-failure episode
  are still collapsed into one canonical event.
- Publication dates, follow-up dates, and dates of earlier referenced disasters
  are still substituted for occurrence dates.
- Datelines, victim origins, destinations, and neighboring districts still
  override the physical failure location in some records.
- `rajdhanidaily.com` contributed 5 of the 15 sampled non-events and
  `deshsanchar.com` contributed 4. The identity/date defects are broader and
  require general parser and clustering changes rather than source exclusion
  alone.

## Next gate

Keep this audit and v0.8 immutable. Build a remediation queue from every `no`
or `unclear` core label, group the queue by root cause and source, implement
general parser/date/location/identity fixes with regression tests, and assemble
a v0.9 candidate. Any future promotion claim requires another independently
drawn sample that excludes all 150 rows and all 215 article URLs from this gate.

## Reproducibility

- Draw: `scripts/draw_v08_fresh_validation.py`
- Scorer: `scripts/score_v08_fresh_validation.py`
- Draw manifest: `data/outputs/v08_fresh_validation_manifest.json`
- Completed labels SHA-256:
  `03a58c6c55ec407e023c3cb05755063eb1f45c7cc012c9426e43914b0ba366c4`
- Machine-readable score SHA-256:
  `6e96cd7a5f587121197a2fdcaaac239e88c69cb4ff17f0e4cfdcf46432e5982d`
- Rendered report SHA-256:
  `f1f6046057bb11633cee43edfe685c25741aa0add11c77a2cd8896e4b0bb59d7`
