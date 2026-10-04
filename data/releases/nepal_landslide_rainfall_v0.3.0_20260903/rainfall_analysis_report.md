# Rainfall threshold analysis

Primary design: district-day matched case-control analysis. Cases require
`conf_date >= 0.78`. Controls are sampled in the same district,
calendar month, and year and are at least 7 days from every
reported event. Thresholds are selected only in data through 2022-12-31;
performance after that date is held out.

- Canonical events read: 2950
- Primary cases with complete rainfall windows: 1471
- Primary matched controls: 6049
- Cases without any eligible control: 185 (12.6%)
- Control rows repeating a district-day: 1132 (18.7%)
- Daily rainfall coverage: 100.000%
- Primary (concurrent, includes event day): R5 threshold 51.6 mm; temporal-test AUC 0.676, sensitivity 0.447, specificity 0.785
- Co-primary (strictly antecedent, excludes event day): R3 threshold 20.0 mm; temporal-test AUC 0.652, sensitivity 0.556, specificity 0.685
- Leave-one-year-out AUC, primary exposure: median 0.638 (range 0.558-0.700, SD 0.046)
- Secondary district-month Spearman rho: 0.273592407721812

Read the single temporal-test AUC against the leave-one-year-out distribution,
and read the development/test contrast against
`inventory_reporting_composition.csv`, because the two periods draw on partly
different publishers. The threshold is an empirical research result, not an
operational warning threshold. See `rainfall_analysis_report.json` for design
details and caveats.
