# Post-correction article-mapping result

**Status:** validated, materialized, and unapplied

## Validated decisions

The 67-row mapping review is complete and valid. Reviewer
`reviewer_mapping_A` accounted for all 85 source-article memberships without
changing any frozen claim or evidence field.

| Final resolution | Old events |
|---|---:|
| exclude cluster | 31 |
| decompose source article | 18 |
| re-cluster and decompose | 7 |
| re-cluster articles | 4 |
| keep cluster | 4 |
| unclear | 3 |

The three unclear records remain unchanged as unresolved original events. They
describe multiple failures but do not contain enough separable location/date
evidence to create defensible physical-event identities.

## Materialized plan

- Resolved old events: 64
- Old events excluded entirely: 31
- Reconstructed or retained physical-event candidates: 93
- Excluded source-article memberships: 35
- Unresolved original events retained unchanged: 3
- Provisional event-count delta: +29

These outputs are an unapplied identity plan. The v0.7 candidate and production
database remain unchanged.

## Remaining identity gates

The 30-row date review is complete. One exact date was resolved and 29
unsupported candidates were excluded, leaving 64 dated candidates. See
`docs/POST_CORRECTION_DATE_RESOLUTION_RESULT.md`.

The required order is:

1. Adjudicate the 64-row candidate-versus-existing collision pack.
2. Run a final candidate-to-candidate collision screen.
3. Resolve every remaining collision as new event, merge, exclusion, or
   explicitly unresolved.
4. Only then assemble the new versioned identity layer.

## Reproducibility

- Completed decisions:
  `data/outputs/post_correction_article_mapping_DECISIONS_COMPLETED.csv`
- Validation:
  `data/outputs/post_correction_article_mapping_validation.json`
- Event groups: `data/outputs/post_correction_reconstruction_GROUPS.csv`
- Excluded memberships:
  `data/outputs/post_correction_reconstruction_EXCLUDED_ARTICLES.csv`
- Unresolved originals:
  `data/outputs/post_correction_reconstruction_UNRESOLVED.csv`
- Materialization manifest:
  `data/outputs/post_correction_reconstruction_manifest.json`
- Date-review template:
  `data/outputs/post_correction_reconstruction_DATE_REVIEW.csv`

The date-review instructions are in
`docs/POST_CORRECTION_DATE_REVIEW_GUIDE.md`.
