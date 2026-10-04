# Rainfall threshold analysis

Primary design: district-day matched case-control analysis. Cases require
`conf_date >= 0.78`. Controls are sampled in the same district,
calendar month, and year and are at least 7 days from every
reported event. Thresholds are selected only in data through 2022-12-31;
performance after that date is held out.

- Canonical events read: 3114
- Primary cases with complete rainfall windows: 1514
- Primary matched controls: 6196
- Daily rainfall coverage: 100.000%
- Window selected in development, evaluated in holdout: R5 threshold 45.4 mm; temporal-test AUC 0.693, sensitivity 0.509, specificity 0.764
- Secondary district-month Spearman rho: 0.2748539362602834

The threshold is an empirical research result, not an operational warning
threshold. See `rainfall_analysis_report.json` for design details and caveats.
