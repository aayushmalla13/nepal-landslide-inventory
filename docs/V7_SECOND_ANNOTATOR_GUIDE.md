# Locked-v7 second-annotator guide

## Purpose

This 120-row exercise measures agreement between two independent human raters.
It does not tune the extraction pipeline and must not change the frozen v7
labels. The second annotator must be a different person from the first annotator
(`GS`).

## Open only these files

1. `data/outputs/locked_test_set_v7_second_annotator_LABEL_HERE.csv`
2. `data/outputs/locked_test_set_v7_second_annotator_reading_pack.csv`
3. `docs/ANNOTATION_RUBRIC.md`

Do not open any file containing `predictions`, `labels_final`, `score`, or the
first annotator's answers until the completed file has been frozen and scored.

## Fill every row

Use the article text, title, and snippet to fill:

- `is_landslide_event_true`
- `in_nepal_true`
- `hazard_type_true`
- `event_granularity_true`
- `article_role_true`
- `district_true`, when stated
- `municipality_true`, when stated
- `date_true`, when supported, in `YYYY-MM-DD` format
- `deaths_true`, when supported
- `trigger_true`
- `annotator`, using the second annotator's initials on every row
- `notes`, when a judgement needs explanation

The five controlled fields must never be blank. Use `unclear` when the evidence
does not support a decision. Optional extraction fields should remain blank when
the article does not provide them; do not guess.

Two selected rows (`v7-0359` and `v7-0373`) have no stored full article text.
Use the title and snippet, and choose `unclear` wherever those are insufficient.

## Save and score

Save the completed file, without reordering or renaming columns, as:

`data/outputs/locked_test_set_v7_second_annotator_COMPLETED.csv`

Then run:

```bash
python3 scripts/score_v7_interannotator.py
```

The scorer rejects changed metadata, missing controlled labels, invalid values,
row reordering, and reuse of the first annotator's ID. It writes:

- `data/outputs/locked_test_set_v7_interannotator_agreement.json`
- `data/outputs/locked_test_set_v7_interannotator_agreement.md`

Report headline and granularity Cohen's kappa as the primary inter-rater
results. District and event-date agreement are secondary because blank values
mean the article did not provide enough evidence.
