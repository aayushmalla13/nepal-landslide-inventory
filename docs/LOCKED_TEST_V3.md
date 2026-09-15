# Locked test v3 — labeling and scoring runbook

## Current state

`locked_test_set_v3` is the untouched post-development evaluation set. It was
drawn after classifier tuning and excludes every URL found in locked v1/v2,
development v1, labelled manual-evaluation files, and BIPAD-assisted discovery.
The manifest records zero overlap.

**Status: completed and spent on 2026-08-10.** The frozen score is precision
0.680, recall 0.851, and F1 0.756 (population-weighted). Do not revise these
labels or use v3 to tune the classifier; future classifier changes require v4.

The sample contains 386 unique articles. The requested allocation was 400, but
only 6 eligible `dropped_other` articles and no eligible `no_extraction`
articles remained. Those scarce strata were censused, leaving an explicit
14-row shortfall rather than silently changing the sampling design.

## Label this file only

`data/outputs/locked_test_set_v3_LABEL_HERE.csv`

Do not open `locked_test_set_v3_predictions.csv` while labeling. It contains
the frozen system output and would anchor the human judgements. Do not edit the
reference `locked_test_set_v3_labels.csv`, the predictions, or the manifest.

Fill all five controlled truth fields on every row:

- `is_landslide_event_true`
- `in_nepal_true`
- `hazard_type_true`
- `event_granularity_true`
- `article_role_true`

Use only the values listed in `docs/ANNOTATION_RUBRIC.md`. Use `unclear` for a
genuinely ambiguous controlled judgement; do not leave a controlled field blank.

The remaining event-specific fields may be blank when the article does not
state them or when no hazard event occurred: district, municipality, event
date, deaths, and trigger. Always fill `annotator`. The event date is not the
article publication date.

For a non-event article about an exhibition in Hetauda, for example, Hetauda
and Makwanpur are not hazard-event locations. Leave the location/date/casualty/
trigger fields blank, set the controlled fields to their appropriate non-event
values (normally `not_a_hazard`, `not_applicable`, and
`metaphor_or_nonevent`), and enter the annotator ID.

Save as UTF-8 CSV without changing row order, `row_id`, URL, title, or snippet.

## Validate and score

After every row is finished, run:

```bash
PYTHONPATH=src .venv/bin/python -m landslide_inventory.run \
  --stage check_labels --config config.yaml
```

Do not score until the checker says there is nothing blocking. Then run once:

```bash
PYTHONPATH=src .venv/bin/python -m landslide_inventory.run \
  --stage score_locked --config config.yaml
```

The scorer verifies the URL lock and prediction hash, freezes the completed
labels as `locked_test_set_v3_labels_final.csv`, and writes
`locked_test_set_v3_score.json`. After seeing this score, do not tune the
pipeline or revise labels against v3; any later model change requires v4.
