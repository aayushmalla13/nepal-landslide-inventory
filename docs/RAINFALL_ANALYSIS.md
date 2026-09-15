# Rainfall-threshold analysis protocol

This is the second phase of the project. The frozen v0.5.0 human-v7 media
inventory is the event source; the analysis does not alter its 2,885 canonical
records.

Analysis version 0.7.0 (2026-09-15). Versions 0.1.0 through 0.6.0 remain on disk
as historical baselines. Version 0.7.0 preserves the v0.6.0 numerical results
and corrects the named inventory-release linkage. See `RAINFALL_CHANGELOG.md`.

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
  the active local SQLite database and frozen separately in the v0.5.0/v7
  release. Its SHA-256 must match the inventory release manifest before a
  rainfall release can be created.

`rainfall_analysis_report.json` records both inputs as repository-relative paths
together with their SHA-256 digests, so a release can be verified on any
machine. Emitted numerics are rounded at a fixed precision so that bundle-lock
hashes reproduce across platforms despite floating-point summation order.

The downloader caches one raw result per district and can resume after a
network failure:

```bash
PYTHONPATH=src .venv/bin/python scripts/download_chirps_climateserv.py
```

## Analysis roles

Roles are fixed before the temporal test set is used, and every emitted row
carries its role.

| Role | Content |
|---|---|
| Primary | Concurrent accumulation, windows ending **on and including** the reported event day, variant `primary_conf_ge_0.78`, window chosen by development AUC |
| Co-primary | Strictly antecedent accumulation, windows ending **the day before** the reported event |
| Secondary | Conditional within-matched-set models, leave-one-year-out and spatial validation, season stratification, district-month aggregate correlation |
| Sensitivity | Date confidence, date shifts, trigger inclusion, road obstructions, balanced source panel, strict matched sets |
| Not reported | Absolute risk, probability calibration, decision-curve net benefit |

The last row is a deliberate exclusion, not an omission. Net benefit and
calibration both require the marginal probability of a landslide district-day.
A media-derived inventory has an unknown and time-varying detection probability,
and the analytic sample is 1:5 by design, so neither quantity is identifiable.
Conditional logistic regression is used instead: it reports an interpretable
slope (odds ratio) while conditioning the un-identifiable intercept away.

## Primary design

The observational unit is a district-day. Primary cases are single-event media
records with a resolved district and `conf_date >= 0.78`; events explicitly
typed as earthquake- or anthropogenic-triggered are excluded. For each case,
rainfall is summed over 1, 3, 5, and 7 days ending on the reported event date.

Multiple canonical events in the same district on the same day are collapsed
to one case-day. Their event IDs and contributing-event count remain in the
joined output, preventing heavily reported district-days from receiving extra
statistical weight.

Five non-event control days are sampled for each case within the same district,
calendar month, and year. Candidate controls within seven days of any reported
event in that district are excluded. The random seed is fixed.

Thresholds maximize Youden's J in a development period ending 2022-12-31.
Where two windows tie on development AUC the shorter window is taken, so the
choice never depends on iteration order. Performance is then measured without
retuning from 2023 onward. Reported metrics include ROC AUC, sensitivity,
specificity, precision, and balanced accuracy, with 95% intervals from a
district-clustered bootstrap. Threshold uncertainty is bootstrapped from the
development data and every emitted row records that provenance in
`threshold_ci_split`. Precision reflects the designed 1:5 matched sample and is
not a population positive predictive value.

## Co-primary design: strictly antecedent rainfall

CHIRPS reports a 24-hour total and media-derived event dates carry no time of
day, so a window that includes the reported event day can contain rain that fell
*after* the failure. The co-primary analysis repeats the primary design using
windows that end the day before the reported event. It selects its own window in
development data and is evaluated in the same untouched holdout. It is the
quantity that bounds what could in principle be known before a failure, and it
is reported next to the primary result rather than buried in a sensitivity
table.

This is a different question from the date-shift sensitivity analyses. Shifting
the event date moves the whole window and changes which case-days exist;
excluding the event day from a fixed window removes one specific day of possibly
post-failure rainfall.

## Design-faithful analysis of the matched sample

Pooling every row into one ROC ignores the matched structure, so the design's own
estimators are reported alongside it in `rainfall_conditional_models.csv`:

- **Conditional logistic regression**, 1:M, stratified by matched set. Stratum
  intercepts cancel, so district, calendar month and year — the matching
  variables — are removed by construction rather than by adjustment. Standard
  errors use a district-clustered sandwich, matching the bootstrap used
  elsewhere. The odds ratio is reported per 10 mm. A Wald *z* is reported
  alongside the p-value because the p-value underflows to zero.
- **Within-stratum concordance**, the probability that a case exceeds a control
  drawn from its own matched set. This is the matched analogue of AUC, with a
  district-clustered bootstrap interval in the holdout.

`rainfall_matching_diagnostics.json` reports two structural properties of the
sampling scheme that a pooled analysis would hide: cases for which no eligible
control existed, and control district-days reused across several cases. The
`strict_matched_sets` variant repeats the analysis on complete strata with each
control district-day used at most once.

## Resampled validation

A single development/test split gives one number and no sense of its
variability. `rainfall_resampled_validation.csv` refits the cutpoint

- without each calendar year, scoring that year (leave-one-year-out); and
- without each of five deterministic district groups, scoring that group
  (spatial holdout, round-robin over sorted district names, so it reproduces
  exactly and depends on no seed).

Neither scheme replaces the prespecified temporal holdout and no method choice
is ever made from them. They are reported so that a favourable or unfavourable
split cannot be mistaken for the whole picture.

## Sensitivity and secondary analyses

Prespecified variants: all dated events; date confidence at least 0.80; event
dates shifted by −1 or +1 day; inclusion of known non-rainfall triggers;
exclusion of road-obstruction events; a **balanced source panel**; and **strict
matched sets**. Each variant selects its own window and cutpoint in development
years before temporal testing, under both exposure definitions.

The balanced source panel restricts cases to publishers contributing at least
`balanced_panel_min_events` (default 30) canonical events on both sides of the
development cut-off. Media inventories change instrument over time — titles
start, stop, change beat or switch language — so this separates a genuine
temporal effect from a change in who was doing the reporting. The panel is
derived from the data at run time rather than hard-coded, so it stays correct if
the inventory is rebuilt. `inventory_reporting_composition.csv` records the full
publisher-by-year matrix behind it.

Season stratification (`rainfall_season_stratified.csv`) fits and evaluates
separately inside and outside the June–September monsoon. Matching on calendar
month already balances season, so this is not a confounding adjustment; it tests
whether a single national cutpoint is meaningful year-round.

A district-month Spearman correlation is retained only as a secondary
association analysis; it is not described as a rainfall threshold, and a
monsoon-only coefficient is reported beside it because the pooled value is
inflated by the contrast between wet and dry months.

## Running the analysis

```bash
PYTHONPATH=src .venv/bin/python -m landslide_inventory.run \
  --stage analysis --config config.yaml
PYTHONPATH=src .venv/bin/python -m landslide_inventory.run \
  --stage analysis_figures --config config.yaml
PYTHONPATH=src .venv/bin/python -m landslide_inventory.run \
  --stage analysis_release --config config.yaml
```

## Outputs

Core analysis

- `rainfall_daily_quality.json`: date/district coverage and missingness
- `rainfall_matching_diagnostics.json`: incomplete strata and control reuse
- `event_antecedent_rainfall.csv`: primary cases, R1/R3/R5/R7 and lagged windows
- `rainfall_controls.csv`: matched controls
- `rainfall_threshold_metrics.csv`: all variants × exposures × windows × splits
- `rainfall_sensitivity_summary.csv`: development-selected result per design
- `rainfall_primary_test_roc.csv`: complete ROC coordinates, both exposures
- `rainfall_conditional_models.csv`: odds ratios and within-stratum concordance
- `rainfall_resampled_validation.csv`: leave-one-year-out and spatial folds
- `rainfall_season_stratified.csv`: monsoon and non-monsoon results
- `rainfall_case_control_distributions.csv`: rainfall distributions by period
- `rainfall_analysis_report.json` and `.md`: machine-readable and concise reports

Inventory description

- `inventory_district_summary.csv`, `inventory_province_summary.csv`,
  `inventory_month_summary.csv`
- `inventory_reporting_composition.csv`: publisher coverage by year and period
- `district_month_rainfall_association.csv`: secondary aggregate table

Figures

- `rainfall_results_figure.svg`: ROC curves and sensitivity designs
- `inventory_map_figure.svg`: district choropleth and province summary
- `rainfall_distributions_figure.svg`: seasonality and case/control rainfall
- `rainfall_validation_figure.svg`: leave-one-year-out and spatial folds

These are empirical research thresholds at district scale, not operational
warning thresholds. CHIRPS grid-cell/district averaging smooths local extremes,
and media-derived event dates retain known uncertainty.
