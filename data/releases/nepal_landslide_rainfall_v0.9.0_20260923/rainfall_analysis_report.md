# Rainfall threshold analysis

Primary design: district-day matched case-control analysis. Cases require
`conf_date >= 0.78`. Controls are sampled in the same district,
calendar month, and year and are at least 7 days from every
reported event. Thresholds are selected only in data through 2022-12-31;
performance after that date is held out.

- Canonical events read: 2872
- Primary cases with complete rainfall windows: 1453
- Primary matched controls: 6059
- Cases without any eligible control: 173 (11.9%)
- Control rows repeating a district-day: 1170 (19.3%)
- Daily rainfall coverage: 100.000%
- Primary (concurrent, includes event day): R5 threshold 51.6 mm; temporal-test AUC 0.677, sensitivity 0.458, specificity 0.776
- Co-primary (strictly antecedent, excludes event day): R3 threshold 23.7 mm; temporal-test AUC 0.651, sensitivity 0.511, specificity 0.722
- Leave-one-year-out AUC, primary exposure: median 0.651 (range 0.566-0.711, SD 0.050)
- Secondary district-month Spearman rho: 0.2735759051465703

Read the single temporal-test AUC against the leave-one-year-out distribution,
and read the development/test contrast against
`inventory_reporting_composition.csv`, because the two periods draw on partly
different publishers. The threshold is an empirical research result, not an
operational warning threshold. See `rainfall_analysis_report.json` for design
details and caveats.
