# Locked test v5 — final expanded-population runbook

Locked v5 evaluates the final 7,624-article population after the bounded
Deshsanchar and Rajdhani archive queues were completed. It excludes locked
v1–v4, development v1, labelled manual-evaluation rows, and BIPAD-assisted
articles. The manifest records zero prior-evaluation overlap.

Label only:

`data/outputs/locked_test_set_v5_LABEL_HERE.csv`

The sample has 383 rows. The requested 400-row design has a documented 17-row
shortfall because only three eligible `dropped_other` rows and no eligible
`no_extraction` rows remained. Scarce strata were censused rather than silently
reallocated. The sample contains 92 Deshsanchar and 53 Rajdhani articles.

Fill all five controlled truth fields and `annotator` on every row. Use only
the vocabularies in `docs/ANNOTATION_RUBRIC.md`. Event-specific district,
municipality, date, deaths, and trigger may be blank when unstated or when no
hazard event occurred.

Validate:

```bash
PYTHONPATH=src .venv/bin/python -m landslide_inventory.run \
  --stage check_labels --config config.yaml
```

When nothing is blocking, score exactly once:

```bash
PYTHONPATH=src .venv/bin/python -m landslide_inventory.run \
  --stage score_locked --config config.yaml
```

Do not inspect `locked_test_set_v5_predictions.csv` while labeling, and do not
edit the reference labels or manifest. After scoring, v5 is spent and must not
be used for tuning.
