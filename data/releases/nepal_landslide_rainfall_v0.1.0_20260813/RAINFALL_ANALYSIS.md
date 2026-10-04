# Rainfall-threshold analysis protocol

This is the second phase of the project. The frozen v0.4.0 media inventory is
the event source; the analysis does not alter its 3,114 canonical records.

## Inputs and provenance

- Rainfall: UCSB CHIRPS v2.0 Final, daily precipitation in mm/day at 0.05°,
  accessed through the public NASA SERVIR ClimateSERV API (`datatype=0`, daily
  interval, spatial average). Dataset documentation:
  https://developers.google.com/earth-engine/datasets/catalog/UCSB-CHG_CHIRPS_DAILY
- API documentation: https://climateserv.servirglobal.net/develop-api
- District boundaries: Open Knowledge Nepal LocalBoundaries, 77 districts,
  WGS84, CC BY 4.0. The file is
  `data/reference/nepal_districts_77.geojson`; downloaded from
  https://localboundries.oknp.org/data/district/nepal.geojson and pinned with
  SHA-256 `2c77e563c9df54270744f2e2b19a69f91dc5ca0ce7800025c0323d8b01c00c2f`.
- Canonical events: `data/outputs/canonical_events_final.csv`, generated from
  the active local SQLite database and frozen separately in the v0.4.0 release.

The downloader caches one raw result per district and can resume after a
network failure:

```bash
PYTHONPATH=src .venv/bin/python scripts/download_chirps_climateserv.py
```

## Primary design

The observational unit is a district-day. Primary cases are single-event media
records with a resolved district and `conf_date >= 0.78`; events explicitly
typed as earthquake- or anthropogenic-triggered are excluded. For each case,
rainfall is summed over 1, 3, 5, and 7 days ending on the reported event date.
Separate lagged windows ending the previous day are retained.

Multiple canonical events in the same district on the same day are collapsed
to one case-day. Their event IDs and contributing-event count remain in the
joined output, preventing heavily reported district-days from receiving extra
statistical weight.

Five non-event control days are sampled for each case within the same district,
calendar month, and year. Candidate controls within seven days of any reported
event in that district are excluded. The random seed is fixed.

Thresholds maximize Youden's J in a development period ending 2022-12-31.
Performance is then measured without retuning from 2023 onward. Reported
metrics include ROC AUC, sensitivity, specificity, precision, and balanced
accuracy, with 95% intervals from a district-clustered bootstrap. Threshold
uncertainty is bootstrapped from the development data. Precision reflects the
designed 1:5 matched sample and is not a population positive predictive value.

Sensitivity analyses include all dated events, dates with confidence at least
0.80, shifting primary event dates by minus or plus one day, including known
non-rainfall triggers, and excluding road-obstruction events. A
district-month Spearman correlation is retained only as a secondary association
analysis; it is not described as a rainfall threshold.

Run the analysis after the daily rainfall file exists:

```bash
PYTHONPATH=src .venv/bin/python -m landslide_inventory.run \
  --stage analysis --config config.yaml
```

## Outputs

- `rainfall_daily_quality.json`: date/district coverage and missingness
- `event_antecedent_rainfall.csv`: primary cases and R1/R3/R5/R7 rainfall
- `rainfall_controls.csv`: matched controls
- `rainfall_threshold_metrics.csv`: development and temporal-test results
- `rainfall_primary_test_roc.csv`: complete ROC coordinates for all four windows
- `rainfall_sensitivity_summary.csv`: development-selected sensitivity results
- `rainfall_results_figure.svg`: reproducible manuscript summary figure
- `district_month_rainfall_association.csv`: secondary aggregate table
- `rainfall_analysis_report.json` and `.md`: machine-readable and concise reports

These are empirical research thresholds at district scale, not operational
warning thresholds. CHIRPS grid-cell/district averaging smooths local extremes,
and media-derived event dates retain known uncertainty.
