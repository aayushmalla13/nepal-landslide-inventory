# Rainfall threshold analysis

Primary design: district-day matched case-control analysis. Cases require
`conf_date >= 0.78`. Controls are sampled in the same district,
calendar month, and year and are at least 7 days from every
reported event. Thresholds are selected only in data through 2022-12-31;
performance after that date is held out.

- Canonical events read: 3114
- Primary cases with complete rainfall windows: 1514
- Primary matched controls: 6196
- Cases without any eligible control: 192 (12.7%)
- Control rows repeating a district-day: 1248 (20.1%)
- Daily rainfall coverage: 100.000%
- Primary (concurrent, includes event day): R5 threshold 45.4 mm; temporal-test AUC 0.693, sensitivity 0.509, specificity 0.764
- Co-primary (strictly antecedent, excludes event day): R3 threshold 19.1 mm; temporal-test AUC 0.664, sensitivity 0.564, specificity 0.685
- Leave-one-year-out AUC, primary exposure: median 0.652 (range 0.563-0.710, SD 0.053)
- Secondary district-month Spearman rho: 0.2748539362602834

Read the single temporal-test AUC against the leave-one-year-out distribution,
and read the development/test contrast against
`inventory_reporting_composition.csv`, because the two periods draw on partly
different publishers. The threshold is an empirical research result, not an
operational warning threshold. See `rainfall_analysis_report.json` for design
details and caveats.
