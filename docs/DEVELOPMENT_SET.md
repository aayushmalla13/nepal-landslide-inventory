# Development Set Workflow

The development set is for diagnosing and improving pipeline rules. It is not a
held-out evaluation set, and metrics from it must not be reported as final
performance.

Generate it after the pipeline and locked-test evaluation are frozen:

```bash
PYTHONPATH=src .venv/bin/python -m landslide_inventory.run \
  --stage development_set --config config.yaml
```

The stage writes:

- `development_set_v1_LABEL_HERE.csv` — the only file opened during labeling;
- `development_set_v1_labels.csv` — untouched blank reference;
- `development_set_v1_predictions.csv` — hidden until labels are complete; and
- `development_set_v1_manifest.json` — seed, allocation, hashes, and exclusion audit.

## Contamination controls

Before sampling, the stage excludes:

1. every URL in any v1/v2 locked-test label artifact under `data/outputs` or
   `docs`;
2. every URL already used by an earlier development set;
3. rows with truth annotations in prior `manual_verification*.csv` files; and
4. all externally assisted BIPAD discoveries, because the common frame loader
   excludes `external_seed_bipad` methods.

Sampling is deterministic and balanced between available English and Nepali
rows within each pipeline-decision quota. The default 300-row allocation puts
the largest share in `dropped_specificity`, the principal recall-development
stratum.

## Labeling

Use `docs/ANNOTATION_RUBRIC.md`. Keep predictions closed until all development
labels are complete. Unlike a locked test set, these labels may be inspected
while designing fixes. Any tuned pipeline must eventually be evaluated on a
new, untouched locked test set such as v3.

The stage refuses to overwrite an existing manifest. To draw another
development batch, increment `validation.development_set.version` in
`config.yaml`.

## After labeling

Run the development-only diagnostic stage:

```bash
PYTHONPATH=src .venv/bin/python -m landslide_inventory.run \
  --stage score_development --config config.yaml
```

This validates every controlled field, verifies that protected article metadata
still matches the blank reference, accepts Excel's UTF-8 byte-order marker, and
then writes:

- `development_set_v1_labels_final.csv` — frozen completed labels;
- `development_set_v1_errors.csv` — joined disagreement rows for diagnosis; and
- `development_set_v1_diagnostics.json` — sample confusion and grouped error
  patterns.

The diagnostic stage intentionally emits no confidence interval or population
weight. Its sample metrics are not evaluation results. Use the error patterns to
develop rules, then measure the resulting pipeline once on a new untouched
locked test set.

## Post-tuning comparison

After rebuilding the pipeline, preserve the original prediction snapshot and
write a separate post-tuning file:

```bash
PYTHONPATH=src .venv/bin/python -m landslide_inventory.run \
  --stage refresh_development_predictions --config config.yaml
PYTHONPATH=src .venv/bin/python -m landslide_inventory.run \
  --stage score_development_tuned --config config.yaml
```

These stages write `development_set_v1_predictions_tuned.csv`,
`development_set_v1_errors_tuned.csv`, and
`development_set_v1_diagnostics_tuned.json`. The original
`development_set_v1_predictions.csv` remains the baseline.

For v1, the deterministic changes moved the 297 decidable development rows
from 41 TP / 27 FP / 46 FN / 183 TN to 77 TP / 22 FP / 10 FN / 188 TN. Sample
diagnostic precision rose from 0.603 to 0.778, recall from 0.471 to 0.885, and
F1 from 0.529 to 0.828. These are development-set diagnostics, not reportable
held-out performance; the next valid evaluation is a newly drawn locked v3.
