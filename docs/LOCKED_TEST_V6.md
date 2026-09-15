# Locked test v6 — final expanded-population runbook

Locked v6 evaluates the final 8,235-article population after all validated
public archive expansions. It excludes locked v1–v5, development v1, labelled
manual-evaluation rows, and BIPAD-assisted articles. The manifest records zero
prior-evaluation overlap.

Label only:

`data/outputs/locked_test_set_v6_LABEL_HERE.csv`

The sample has 388 rows. The requested 400-row design has a documented 12-row
shortfall because only eight eligible `dropped_other` rows and no eligible
`no_extraction` rows remained. Scarce strata were censused rather than silently
reallocated. The sample includes 82 English OnlineKhabar articles.

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

Do not inspect `locked_test_set_v6_predictions.csv` while labeling, and do not
edit the reference labels or manifest. After scoring, v6 is spent and must not
be used for tuning.
