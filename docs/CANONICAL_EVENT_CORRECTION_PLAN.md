# Canonical event correction plan

## Purpose

The adjudicated 150-event audit has been converted into an evidence-bearing
candidate queue. These rows are review leads, not applied corrections. The
frozen v0.6.0 inventory and v0.8.0 rainfall release remain unchanged.

## Candidate inventory

- Audited rows: 150
- Rows with one or more candidate actions: 119
- Rows with no identified correction: 31
- P0 identity or linkage candidates: 90
- P1 attribute candidates: 27
- P2 uncertain candidates: 2
- Population-weighted share carrying any flag: 0.828

The weighted flagged share is not the invalid-record rate. It includes
attribute errors such as event type and deaths and allows multiple actions per
event. Strict usable-record precision remains the separately reported 0.402.

## Ordered work batches

| Batch | Rows | Why it comes in this order |
|---|---:|---|
| article mapping | 55 | exclusions, splits, and re-clustering can change event identity and membership |
| true-value review | 37 | dates and locations need structured replacement values from source evidence |
| structured attributes | 27 | type, hazard, and deaths can be applied only after event identity is stable |

The batch files are:

1. `data/outputs/canonical_event_correction_BATCH_ARTICLE_MAPPING.csv`
2. `data/outputs/canonical_event_correction_BATCH_TRUE_VALUE_REVIEW.csv`
3. `data/outputs/canonical_event_correction_BATCH_STRUCTURED_ATTRIBUTES.csv`

## Systematic failure priorities

| Failure family | Flagged rows | Pipeline area to investigate |
|---|---:|---|
| event type classification | 39 | road-obstruction versus landslide event typing |
| event granularity | 37 | multi-location and roundup articles represented as one event |
| event date resolution | 37 | retrospective dates, publication dates, and multi-date articles |
| casualty extraction | 27 | event-specific casualty attachment and zero/not-reported distinction |
| location role resolution | 25 | datelines, road endpoints, victim origins, and administrative references |
| scope or event specificity | 18 | generic, historical, metaphorical, foreign, and non-landslide mentions |
| deduplication | 17 | clusters spanning distinct dates, places, or physical failures |
| hazard type classification | 11 | debris flow and rockfall subtype assignment |

Action counts overlap and must not be summed as unique events.

## Application rules

1. Map every affected canonical event back to all source article URLs before
   excluding, splitting, or re-clustering it.
2. Record explicit replacement values and evidence for date, district, and
   municipality corrections; a `no` audit label alone is insufficient.
3. Apply corrections through a versioned layer with before/after state and
   reviewer provenance.
4. Convert recurring failure patterns into pipeline fixes and regression tests
   rather than correcting only sampled records.
5. Build a new inventory release and rerun rainfall linkage after identities,
   dates, and locations stabilize.
6. Validate the new release with a fresh locked sample; never reuse this audit
   as an unbiased post-correction precision estimate.
