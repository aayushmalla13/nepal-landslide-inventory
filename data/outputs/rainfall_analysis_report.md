# Rainfall threshold analysis

Primary design: district-day matched case-control analysis. Cases require
`conf_date >= 0.78`. Controls are sampled in the same district,
calendar month, and year and are at least 7 days from every
reported event. Thresholds are selected only in data through 2022-12-31;
performance after that date is held out.

- Canonical events read: 2122
- Primary cases with complete rainfall windows: 1278
- Primary matched controls: 5460
- Cases without any eligible control: 131 (10.3%)
- Control rows repeating a district-day: 1087 (19.9%)
- Daily rainfall coverage: 100.000%
- Primary (concurrent, includes event day): R3 threshold 31.7 mm; temporal-test AUC 0.686, sensitivity 0.473, specificity 0.789
- Co-primary (strictly antecedent, excludes event day): R3 threshold 21.0 mm; temporal-test AUC 0.646, sensitivity 0.557, specificity 0.669
- Leave-one-year-out AUC, primary exposure: median 0.663 (range 0.576-0.711, SD 0.045)
- Secondary district-month Spearman rho: 0.26792740359914663

Read the single temporal-test AUC against the leave-one-year-out distribution,
and read the development/test contrast against
`inventory_reporting_composition.csv`, because the two periods draw on partly
different publishers. The threshold is an empirical research result, not an
operational warning threshold. See `rainfall_analysis_report.json` for design
details and caveats.
