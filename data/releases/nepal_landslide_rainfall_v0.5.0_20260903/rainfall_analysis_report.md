# Rainfall threshold analysis

Primary design: district-day matched case-control analysis. Cases require
`conf_date >= 0.78`. Controls are sampled in the same district,
calendar month, and year and are at least 7 days from every
reported event. Thresholds are selected only in data through 2022-12-31;
performance after that date is held out.

- Canonical events read: 2885
- Primary cases with complete rainfall windows: 1508
- Primary matched controls: 6164
- Cases without any eligible control: 200 (13.3%)
- Control rows repeating a district-day: 1159 (18.8%)
- Daily rainfall coverage: 100.000%
- Primary (concurrent, includes event day): R5 threshold 51.6 mm; temporal-test AUC 0.670, sensitivity 0.456, specificity 0.766
- Co-primary (strictly antecedent, excludes event day): R3 threshold 19.1 mm; temporal-test AUC 0.645, sensitivity 0.575, specificity 0.648
- Leave-one-year-out AUC, primary exposure: median 0.644 (range 0.544-0.702, SD 0.052)
- Secondary district-month Spearman rho: 0.27606268443269955

Read the single temporal-test AUC against the leave-one-year-out distribution,
and read the development/test contrast against
`inventory_reporting_composition.csv`, because the two periods draw on partly
different publishers. The threshold is an empirical research result, not an
operational warning threshold. See `rainfall_analysis_report.json` for design
details and caveats.
