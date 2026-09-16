# Canonical event reconstruction result

## Validated decisions

The 55-row article-mapping review is complete and valid. Reviewer `reviewer_D`
accounted for all 124 frozen source-article memberships with no unresolved
cluster decisions.

- Whole canonical events excluded: 26
- Original events reconstructed: 29
- Reconstructed physical-event candidates: 100
- Source-article memberships excluded: 29
- Provisional event-count delta within the reviewed set: +45

The 100 rows are correction candidates, not production canonical events.

## Remaining gates

Nine reconstructed candidates have an unclear event date and cannot enter an
event-date-dependent inventory or rainfall analysis. The dated candidates must
also be matched against the 2,830 unaffected frozen events before insertion;
otherwise reconstruction could duplicate events already represented elsewhere.

The required order is:

1. Resolve or exclude the nine unclear-date candidates.
2. Match all reconstruction candidates against unaffected frozen events using
   district, date windows, municipality, source-URL overlap, and event evidence.
3. Adjudicate possible collisions as new event, merge with existing event, or
   exclude duplicate.
4. Only then build the versioned correction layer and new inventory release.

## Reproducibility

Validated source decisions:

`data/outputs/canonical_event_article_mapping_DECISIONS_COMPLETED.csv`

Normalized outputs:

- `data/outputs/canonical_event_reconstruction_GROUPS.csv`
- `data/outputs/canonical_event_reconstruction_EXCLUDED_ARTICLES.csv`
- `data/outputs/canonical_event_reconstruction_manifest.json`

Run:

```bash
PYTHONPATH=src .venv/bin/python scripts/validate_canonical_event_article_mapping.py
PYTHONPATH=src .venv/bin/python scripts/materialize_canonical_event_reconstruction.py
```
