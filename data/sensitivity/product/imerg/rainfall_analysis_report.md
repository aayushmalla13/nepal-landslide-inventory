# Rainfall threshold analysis

Primary design: district-day matched case-control analysis. Cases require
`conf_date >= 0.78`. Controls are sampled in the same district,
calendar month, and year and are at least 7 days from every
reported event. Thresholds are selected only in data through 2022-12-31;
performance after that date is held out.

- Canonical events read: 2885
- Primary cases with complete rainfall windows: 1378
- Primary matched controls: 5624
- Cases without any eligible control: 181 (13.1%)
- Control rows repeating a district-day: 1054 (18.7%)
- Daily rainfall coverage: 100.000%
- Primary (concurrent, includes event day): R3 threshold 28.3 mm; temporal-test AUC 0.701, sensitivity 0.670, specificity 0.649
- Co-primary (strictly antecedent, excludes event day): R1 threshold 8.7 mm; temporal-test AUC 0.669, sensitivity 0.586, specificity 0.684
- Leave-one-year-out AUC, primary exposure: median 0.719 (range 0.620-0.761, SD 0.052)
- Secondary district-month Spearman rho: 0.31595795521023035

Read the single temporal-test AUC against the leave-one-year-out distribution,
and read the development/test contrast against
`inventory_reporting_composition.csv`, because the two periods draw on partly
different publishers. The threshold is an empirical research result, not an
operational warning threshold. See `rainfall_analysis_report.json` for design
details and caveats.
